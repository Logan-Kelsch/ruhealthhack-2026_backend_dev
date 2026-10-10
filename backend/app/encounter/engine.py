"""Deterministic disclosure engine (PRD 9.1 step 3). Pure code, no LLM.

Given the resolved visit, the engine state and the intent tags, it decides which facts
the patient may say this turn, what the chart releases, exam results, and trust events.
Same inputs, same outputs.
"""
from __future__ import annotations

from app import catalogs
from app.encounter.trust import sensitive_topic_ids, trust_events_for_turn
from app.schemas.case import Case, Fact
from app.schemas.encounter import ChartRelease, Disclosure, EngineResult, Intent, Notice, Withheld

OPENER_TOPICS = {"chief_complaint", "anything_else", "patient_expectations"}
NO_THRESHOLD = -10_000


def new_state(case: Case) -> dict:
    return {
        "trust": case.trust.start,
        "turn": 0,
        "disclosed": {},
        "asked": {},
        "actions": {},
        "pending_cues": [],
        "introduced": False,
        "chart": [],
        "exam_done": {},
        "orders_done": {},
        "open_questions": 0,
        "first_si_turn": None,
        "open_before_si": None,
        "trust_log": [],
        "events": [],
    }


def tier_threshold(case: Case, fact: Fact) -> int:
    if fact.unlock.min_trust is not None:
        return fact.unlock.min_trust
    if fact.tier in ("reluctant", "hidden"):
        return case.trust.thresholds.get(fact.tier, NO_THRESHOLD)
    return case.trust.thresholds.get(fact.tier, NO_THRESHOLD)


def mood_for(case: Case, trust: int) -> str:
    th = case.trust.thresholds
    if trust <= -2:
        return "irritated and closed off"
    if trust < th.get("reluctant", 2):
        return "guarded"
    if trust < th.get("hidden", 4):
        return "warming up"
    return "open and trusting"


def _fmt_lab(lab) -> str:
    v = lab.value
    return f"{v} {lab.unit}".strip()


def visit_start_releases(case: Case) -> list[ChartRelease]:
    out: list[ChartRelease] = []
    if case.briefing.show_doorway_vitals:
        for v in case.vitals:
            out.append(ChartRelease(kind="vital", ref=v.key, label=v.label, value=f"{v.value} {v.unit}".strip(), section="Vitals"))
    for d in case.diagnoses:
        if d.release.on == "visit_start":
            out.append(ChartRelease(kind="diagnosis", ref=d.name, label=d.name, section="Problem list"))
    for m in case.medications:
        if m.release.on == "visit_start":
            label = " ".join(x for x in [m.name, m.dose, m.frequency] if x)
            out.append(ChartRelease(kind="medication", ref=m.name, label=label, section="Medications"))
    for a in case.allergies:
        if a.release.on == "visit_start":
            out.append(ChartRelease(kind="allergy", ref=a.substance, label=f"{a.substance}" + (f" ({a.reaction})" if a.reaction else ""), section="Allergies"))
    for lab in case.labs:
        if lab.release.on == "visit_start":
            out.append(ChartRelease(kind="lab", ref=lab.key, label=lab.name, value=_fmt_lab(lab), flag=lab.flag(), section="Labs"))
    for art in case.artifacts:
        if art.release.on == "visit_start":
            out.append(ChartRelease(kind="artifact", ref=art.id, label=art.title, section="Documents"))
    return out


def _releases_for_fact(case: Case, fact: Fact) -> list[ChartRelease]:
    out: list[ChartRelease] = []
    if fact.chart_section:
        out.append(ChartRelease(kind="fact", ref=fact.id, label=fact.text, section=fact.chart_section, source_fact=fact.id))
    for d in case.diagnoses:
        if d.release.on == "fact" and d.release.fact_id == fact.id:
            out.append(ChartRelease(kind="diagnosis", ref=d.name, label=d.name, section="Problem list", source_fact=fact.id))
    for m in case.medications:
        if m.release.on == "fact" and m.release.fact_id == fact.id:
            label = " ".join(x for x in [m.name, m.dose, m.frequency] if x)
            out.append(ChartRelease(kind="medication", ref=m.name, label=label, section="Medications", source_fact=fact.id))
    for a in case.allergies:
        if a.release.on == "fact" and a.release.fact_id == fact.id:
            out.append(ChartRelease(kind="allergy", ref=a.substance, label=a.substance + (f" ({a.reaction})" if a.reaction else ""), section="Allergies", source_fact=fact.id))
    for lab in case.labs:
        if lab.release.on == "fact" and lab.release.fact_id == fact.id:
            out.append(ChartRelease(kind="lab", ref=lab.key, label=lab.name, value=_fmt_lab(lab), flag=lab.flag(), section="Labs", source_fact=fact.id))
    for art in case.artifacts:
        if art.release.on == "fact" and art.release.fact_id == fact.id:
            out.append(ChartRelease(kind="artifact", ref=art.id, label=art.title, section="Documents", source_fact=fact.id))
    return out


def _max_new_facts(case: Case) -> int:
    verbosity = case.profile.personality.traits.get("verbosity", 0.5)
    return 4 if verbosity >= 0.7 else 3


def process_turn(
    case: Case,
    state: dict,
    intent: Intent,
    utterance: str,
    barge_in_remaining_ms: int | None = None,
) -> tuple[EngineResult, dict]:
    """Return (result, new_state). Does not mutate the input state."""
    st = {k: (v.copy() if isinstance(v, (dict, list)) else v) for k, v in state.items()}
    st["pending_cues"] = [dict(c) for c in state.get("pending_cues", [])]
    turn = st["turn"] + 1
    st["turn"] = turn
    res = EngineResult()

    topic_ids = intent.topic_ids()
    case_sensitive = sensitive_topic_ids()

    # 1. Trust events first, so empathy in this turn counts toward this turn's disclosure.
    events, resolved_cues = trust_events_for_turn(
        intent=intent, utterance=utterance, turn=turn, state=st, sensitive_topics=case_sensitive, barge_in_remaining_ms=barge_in_remaining_ms
    )
    for e in events:
        st["trust"] += e.delta
        st["trust_log"].append(e.model_dump())
        if e.event == "introduced_self":
            st["introduced"] = True
    st["pending_cues"] = [c for c in st["pending_cues"] if c["fact_id"] not in resolved_cues]
    res.trust_events = events
    trust = st["trust"]

    # Suicide screening sequencing note (communication note only, never a deduction).
    if "suicidal_ideation" in topic_ids and st["first_si_turn"] is None:
        st["first_si_turn"] = turn
        st["open_before_si"] = st["open_questions"] > 0
    if intent.question_type == "open":
        st["open_questions"] += 1

    # 2. Which facts does this turn touch?
    disclosed: dict = st["disclosed"]
    matched: list[Fact] = []
    for f in case.facts:
        if f.status != "approved":
            continue
        if topic_ids & set(f.unlock.topics):
            matched.append(f)
    if not matched and (topic_ids & OPENER_TOPICS or (not topic_ids and intent.question_type == "open" and not intent.maneuvers and not intent.orders)):
        nxt = next((f for f in case.facts if f.status == "approved" and f.tier == "initial" and f.id not in disclosed), None)
        if nxt:
            matched.append(nxt)

    new_allowed: list[Fact] = []
    repeats: list[str] = []
    for f in matched:
        if f.id in disclosed:
            repeats.append(f.id)
            continue
        threshold = tier_threshold(case, f) if f.tier != "initial" else NO_THRESHOLD
        missing = [r for r in f.unlock.requires_facts if r not in disclosed]
        if trust < threshold:
            res.withheld.append(Withheld(fact_id=f.id, reason=f"trust {trust} < {threshold} ({f.tier})"))
        elif missing:
            res.withheld.append(Withheld(fact_id=f.id, reason=f"requires {', '.join(missing)}"))
        else:
            new_allowed.append(f)
    # Patients do not dump everything at once; the rest stays available for the next ask.
    limit = _max_new_facts(case)
    tier_order = {"initial": 0, "discoverable": 1, "reluctant": 2, "hidden": 3}
    new_allowed.sort(key=lambda f: tier_order[f.tier])
    new_allowed = new_allowed[:limit]

    asked_before = any(st["asked"].get(t) for t in topic_ids)
    for t in topic_ids:
        st["asked"].setdefault(t, []).append(turn)
    for a in intent.action_ids():
        st["actions"].setdefault(a, []).append(turn)

    for f in new_allowed:
        disclosed[f.id] = turn
        cond = next((f"topic:{t}" for t in f.unlock.topics if t in topic_ids), "opener")
        res.disclosures.append(Disclosure(fact_id=f.id, turn=turn, condition=cond, trust_at=trust))
        res.chart_releases.extend(_releases_for_fact(case, f))
        if f.cue:
            st["pending_cues"].append({"fact_id": f.id, "turn": turn, "topics": [t for t in f.unlock.topics] + ["hobbies_personal"]})
    res.allowed_fact_ids = [f.id for f in new_allowed]
    res.repeat_fact_ids = repeats
    # A statement that mentions a topic (the student explaining) is not a repeated question.
    res.is_repeat = bool(repeats) and not new_allowed and asked_before and intent.question_type != "statement"
    res.deflect = bool(res.withheld) and not new_allowed

    # 3. Chart releases by topic.
    for lab in case.labs:
        if lab.release.on == "topic" and topic_ids & set(lab.release.topics):
            res.chart_releases.append(ChartRelease(kind="lab", ref=lab.key, label=lab.name, value=_fmt_lab(lab), flag=lab.flag(), section="Labs"))
    for art in case.artifacts:
        if art.release.on == "topic" and topic_ids & set(art.release.topics):
            res.chart_releases.append(ChartRelease(kind="artifact", ref=art.id, label=art.title, section="Documents"))

    # 4. Physical exam: the faculty finding, or the catalog's normal default.
    catalog = catalogs.maneuvers()
    for hit in intent.maneuvers:
        m = catalog.get(hit.id)
        if m is None:
            res.notices.append(Notice(kind="exam_unavailable", text="That exam isn't available in this case."))
            continue
        found = next((e for e in case.exam if e.maneuver == hit.id), None)
        text = found.finding if found else m["normal"]
        st["exam_done"][hit.id] = turn
        res.exam_results.append(
            ChartRelease(kind="exam", ref=hit.id, label=m["label"], value=text, flag="abnormal" if (found and found.abnormal) else None, section="Exam")
        )

    # 5. Orders: release results whose rule is "on order".
    panels = catalogs.lab_catalog()["panels"]
    for hit in intent.orders:
        labs = [lab for lab in case.labs if lab.panel == hit.id and lab.release.on == "order"]
        already = [lab for lab in case.labs if lab.panel == hit.id and lab.release.on == "visit_start"]
        if labs:
            st["orders_done"][hit.id] = turn
            for lab in labs:
                res.chart_releases.append(ChartRelease(kind="lab", ref=lab.key, label=lab.name, value=_fmt_lab(lab), flag=lab.flag(), section="Labs"))
        elif already:
            res.notices.append(Notice(kind="info", text=f"{panels[hit.id]['label']} results are already in the chart."))
        else:
            res.notices.append(Notice(kind="order_unavailable", text=f"{panels.get(hit.id, {}).get('label', hit.id)} isn't available in this case."))

    res.exam_only = bool(res.exam_results) and not new_allowed and not repeats and not res.withheld
    st["chart"] = st["chart"] + [r.model_dump() for r in res.chart_releases + res.exam_results]
    res.trust_after = trust
    res.mood = mood_for(case, trust)

    # 6. Audio tags are chosen here from state, never by the LLM.
    traits = case.profile.personality.traits
    if res.deflect:
        res.audio_tags = ["hesitates"]
    elif res.is_repeat:
        res.audio_tags = ["sighs"]
    elif any(e.delta > 0 for e in events) and traits.get("humor", 0) >= 0.5:
        res.audio_tags = ["chuckles"]
    elif trust <= -1 and traits.get("irritability", 0) >= 0.6:
        res.audio_tags = ["sarcastic"]
    return res, st
