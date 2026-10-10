"""Authored encounter/debrief fixtures; no learner labels or faculty rubric grades.

The shared debrief computes provisional scores internally. This adapter deliberately
exports only source-anchored suggestions with ``faculty_score=None``. A missing
action is a closed-window observation, never a positive student-skill label.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from app import catalogs
from app.encounter.visit import resolve_visit
from app.feedback.debrief import build_debrief
from app.feedback import decisions, documentation, rubric
from app.schemas.case import Case
from app.schemas.encounter import Hit, Intent
from backend_kelsch.app.patient_environment.runner import ScriptTurn, run_script, case_source

ROOT = Path(__file__).resolve().parents[3]
CASES = ("walter_greene", "alina_reyes", "eli_brooks")
RUBRIC_SOURCE = "backend/app/data/rubric_shp_v1.json"


def authored_turn(text: str, *, topic: str | None = None, action: str | None = None,
                  confidence: str = "high", empathy: bool = False) -> ScriptTurn:
    return ScriptTurn(text, Intent(topics=[Hit(id=topic, span=text, confidence=confidence)] if topic else [],
        actions=[Hit(id=action, span=text, confidence=confidence)] if action else [],
        empathy=[Hit(id="validation", span=text)] if empathy else [],
        question_type="closed" if topic else "statement"))


def scenarios(case_id: str) -> dict[str, list[ScriptTurn]]:
    """Explicit fixture intents, never extracted or reviewed performance labels."""
    intro = authored_turn("Hello, I'm a student clinician.")
    if case_id == "walter_greene":
        return {
            "authored": [intro, authored_turn("What brings you in?", topic="chief_complaint"),
                authored_turn("Which over-the-counter medicines are you taking?", topic="otc_medications"),
                authored_turn("Let's discuss the risks of ibuprofen.", action="counsel_nsaid_risk")],
            "absent": [intro],
            "low_confidence": [authored_turn("Which over-the-counter medicines are you taking?", topic="otc_medications"),
                authored_turn("Maybe avoid those tablets.", action="counsel_nsaid_risk", confidence="low")],
        }
    if case_id == "alina_reyes":
        return {"authored": [intro, authored_turn("How has your mood been?", topic="mood"),
            authored_turn("Have you had periods of little sleep and unusually high energy?", topic="mania_history"),
            authored_turn("Have you had thoughts of suicide?", topic="suicidal_ideation"),
            authored_turn("That sounds hard.", empathy=True)]}
    if case_id == "eli_brooks":
        return {
            "authored": [intro, authored_turn("What brings you in?", topic="chief_complaint"),
                authored_turn("I would explain why antibiotics aren't indicated.", action="decline_antibiotics_explain"),
                authored_turn("Please return if symptoms worsen.", action="safety_netting")],
            "conflicting": [authored_turn("I would prescribe an antibiotic.", action="prescribe_antibiotic"),
                authored_turn("I would explain why antibiotics aren't indicated.", action="decline_antibiotics_explain")],
        }
    raise KeyError(case_id)


def span_ref(turn: int, speaker: str, text: str, quote: str) -> dict:
    """Use character offsets so duplicate phrases still have a concrete anchor."""
    if not quote or quote not in text:
        raise ValueError(f"unanchored {speaker} quote at turn {turn}: {quote!r}")
    start = text.index(quote)
    return {"kind": "transcript_span", "turn": turn, "speaker": speaker,
            "start": start, "end": start + len(quote), "quote": quote}


def fact_ref(case: Case, source: dict, fact_id: str) -> dict:
    fact = case.fact(fact_id)
    if not fact or not fact.source:
        raise ValueError(f"unknown or unsourced fact: {fact_id}")
    return {"kind": "source_fact", "fact_id": fact_id, "case_path": source["path"],
            "case_sha256": source["sha256"], "case_version": case.version,
            "source": fact.source.model_dump()}


def note_ref(note: dict[str, str], quote: str) -> dict:
    for field, value in note.items():
        if quote in value:
            start = value.index(quote)
            return {"kind": "note_span", "field": field, "start": start,
                    "end": start + len(quote), "quote": quote}
    raise ValueError(f"unanchored note quote: {quote!r}")


def audit_claims(claims: list[dict], turns: list[dict], note: dict[str, str], case: Case, source: dict) -> int:
    """Reject every asserted claim without an exact transcript, note or case-fact anchor."""
    by_idx = {t["idx"]: t for t in turns}
    count = 0
    for claim in claims:
        if not claim.get("evidence"):
            raise ValueError(f"claim without evidence: {claim['kind']}")
        for ref in claim["evidence"]:
            kind = ref["kind"]
            if kind == "transcript_span":
                field = {"student": "student_text", "patient": "reply_text"}.get(ref["speaker"])
                if not field or ref["turn"] not in by_idx:
                    raise ValueError("unknown transcript speaker/turn")
                value = by_idx[ref["turn"]][field]
            elif kind == "note_span":
                value = note[ref["field"]]
            elif kind == "source_fact":
                if ref != fact_ref(case, source, ref["fact_id"]):
                    raise ValueError("fact reference/source changed")
                count += 1
                continue
            else:
                raise ValueError(f"unknown evidence kind {kind}")
            if value[ref["start"]:ref["end"]] != ref["quote"] or not ref["quote"]:
                raise ValueError("span does not match source text")
            count += 1
    return count


def _logged(trace: dict) -> list[dict]:
    return [{"idx": t["turn"], "student_text": t["utterance"], "reply_text": t["reply"],
             "intent": t["intent"], "engine": {"disclosures": t["disclosures"],
                "trust_events": t["trust_events"]}} for t in trace["turns"]]


def _doc_claims(case: Case, source: dict, note: dict, doc: dict) -> list[dict]:
    claims = []
    for item in doc.get("missing", []):
        if not case.fact(item["id"]):
            continue  # Chart-only omission has no case fact anchor in this schema.
        claims.append({"kind": "documentation_missing", "text": "Disclosed key finding absent from note (heuristic)",
            "review_status": "pending", "evidence": [fact_ref(case, source, item["id"])]})
    for item in doc.get("unsupported", []):
        statement = item["statement"]
        # The shared fallback includes field headings; anchor the concrete note text.
        quote = statement.split(": ", 1)[-1] if ": " in statement else statement
        claims.append({"kind": "documentation_unbacked_number", "text": item["reason"],
            "review_status": "pending", "evidence": [note_ref(note, quote)]})
    return claims


def _suggestions(case: Case, source: dict, turns: list[dict], raw: dict) -> list[dict]:
    """Only quote-bearing prompts; no numeric grade leaves this boundary."""
    out = []
    action_ids = {h["id"] for t in turns for h in t["intent"]["actions"]}
    conflict = {"prescribe_antibiotic", "decline_antibiotics_explain"} <= action_ids
    for domain in raw["rubric"]["domains"]:
        refs = []
        for ev in domain["evidence"]:
            t = next(x for x in turns if x["idx"] == ev["turn"])
            if any(h["span"] == ev["quote"] and h["confidence"] == "low"
                   for kind in ("topics", "actions", "empathy") for h in t["intent"][kind]):
                continue
            if conflict and any(h["span"] == ev["quote"] for h in t["intent"]["actions"]):
                continue
            speaker = "student" if ev["quote"] in t["student_text"] else "patient"
            refs.append(span_ref(ev["turn"], speaker, t[f"{speaker}_text" if speaker == "student" else "reply_text"], ev["quote"]))
        if refs:
            out.append({"kind": "rubric_suggestion", "domain_id": domain["id"],
                "domain_key": domain["key"], "rubric_source": RUBRIC_SOURCE,
                "text": f"Review this evidence for {domain['name']}.", "evidence": refs,
                "faculty_score": None, "review_status": "pending"})
    return out


def evaluate_scenario(case_id: str, scenario_id: str, *, note: dict[str, str] | None = None) -> dict:
    path = ROOT / "cases" / f"{case_id}.json"
    case = Case.model_validate_json(path.read_text())
    source = {**case_source(path), "path": str(path.relative_to(ROOT))}
    trace = run_script(case, scenarios(case_id)[scenario_id], source=source)
    turns = _logged(trace)
    note = note if note is not None else {"assessment": "Blood pressure was 98765."}
    raw, calls = build_debrief(case, case.visit("v1"), turns, trace["final_state"], note, False)
    assert not calls
    claims = []
    for t in turns:
        for h in t["intent"]["actions"]:
            claims.append({"kind": "explicit_fixture_action", "label": h["id"],
                "label_origin": "authored_fixture", "confidence": h["confidence"],
                "review_status": "pending" if h["confidence"] == "high" else "low_confidence_review",
                "evidence": [span_ref(t["idx"], "student", t["student_text"], h["span"])]})
        for e in t["engine"]["trust_events"]:
            claims.append({"kind": "trust_event", "label": e["event"], "delta": e["delta"],
                "evidence": [span_ref(t["idx"], "student", t["student_text"], e["span"])]})
        for d in t["engine"]["disclosures"]:
            claims.append({"kind": "disclosed_source_fact", "label": d["fact_id"],
                "evidence": [fact_ref(case, source, d["fact_id"])]})
    claims += _doc_claims(case, source, note, raw["documentation"] or {})
    claims += _suggestions(case, source, turns, raw)
    # The shared fallback can issue provisional numeric grades; they are never
    # serialized here. A domain-6/7 score-1 trigger only opens a faculty queue.
    review_ids = set(catalogs.rubric(case.rubric_id)["scoring"]["review_trigger_domain_ids"])
    safety_flags = []
    for d in raw["rubric"]["domains"]:
        if d["id"] in review_ids and d["score"] == 1:
            source_facts = [f for f in case.facts if f.safety]
            refs = [fact_ref(case, source, source_facts[0].id)] if source_facts else []
            refs += [c["evidence"][0] for c in claims if c["kind"] == "rubric_suggestion" and c["domain_id"] == d["id"]][:1]
            if refs:
                claims.append({"kind": "faculty_safety_review_flag", "domain_id": d["id"],
                    "rubric_source": RUBRIC_SOURCE, "review_status": "pending", "faculty_score": None,
                    "evidence": refs})
                safety_flags.append(d["id"])
    evidence_count = audit_claims(claims, turns, note, case, source)
    decisions_out = raw["decision_points"]
    # Shared decision evaluator treats low-confidence hits as boolean for branch
    # selection; refuse to call that branch clinically established.
    uncertain = [d["id"] for d in decisions_out if d["result"] == "unclear"]
    taken = raw["decision_path"]["taken"]
    next_case = resolve_visit(case, "v2", next((b for b in case.visit("v1").branches if taken and b.id == taken["id"]), None)) if case.visit("v2") else None
    next_case_again = resolve_visit(case, "v2", next((b for b in case.visit("v1").branches if taken and b.id == taken["id"]), None)) if next_case else None
    branch_replay = next_case.model_dump() == next_case_again.model_dump() if next_case else None
    conflict = {"prescribe_antibiotic", "decline_antibiotics_explain"} <= {c.get("label") for c in claims if c["kind"] == "explicit_fixture_action"}
    if conflict:
        # These are conflicting fixture actions, not a reliable skill judgement.
        uncertain.append("conflicting_antibiotic_actions")
    return {"case_id": case_id, "scenario": scenario_id, "case_version": case.version,
        "case_source": source, "intent_origin": "authored_fixture", "transcript": turns,
        "note": note, "claims": claims, "evidence_refs_checked": evidence_count,
        "documentation_method": raw["documentation"]["method"] if raw["documentation"] else None,
        "decision_points": decisions_out,
        "branch": {"taken_id": taken["id"] if taken else None,
            "authored_branch_status": taken["status"] if taken else None,
            "predicate_source": f"{source['path']}:/visits/0/decision_points",
            "next_visit_id": "v2" if next_case else None,
            "next_visit_sha256": sha256(json.dumps(next_case.model_dump(), sort_keys=True).encode()).hexdigest() if next_case else None,
            "replay_match": branch_replay, "uncertain_predicates": uncertain,
            "clinical_outcome_status": "NOT EVALUABLE"},
        "safety_review_domain_ids": safety_flags,
        "faculty_approved_scores": None, "review_status": "pending"}


def na_probe() -> dict:
    """Exercise shared N/A rule on an empty hypothetical signal fixture."""
    case = Case.model_validate_json((ROOT / "cases/eli_brooks.json").read_text())
    signals = {"elicited": [], "metrics": {"unexplained_jargon": []},
               "decision_points": [], "safety": []}
    value = rubric.rule_based_scores(case, [], signals)["clinical_reasoning_and_synthesis"]["score"]
    return {"domain_id": 6, "observed": value, "expected": "N/A",
            "fixture": "empty hypothetical signals", "faculty_score": None}


def run_all() -> tuple[dict, list[dict]]:
    records = [evaluate_scenario(case_id, scenario_id)
               for case_id in CASES for scenario_id in scenarios(case_id)]
    counts = Counter()
    for record in records:
        counts["claims"] += len(record["claims"])
        counts["evidence_refs"] += record["evidence_refs_checked"]
        counts["branches_replayed"] += bool(record["branch"]["replay_match"])
        counts["branches_with_next_visit"] += record["branch"]["next_visit_id"] is not None
        counts["uncertain_branches"] += bool(record["branch"]["uncertain_predicates"])
        counts["safety_flags"] += len(record["safety_review_domain_ids"])
        counts["document_discrepancies"] += sum(c["kind"].startswith("documentation_") for c in record["claims"])
    na = na_probe()
    mechanics_ok = counts["branches_replayed"] == counts["branches_with_next_visit"] and na["observed"] == "N/A"
    report = {"stage": "Notebook 05", "method": "authored fixture intents and deterministic debrief; no measured learner outcomes",
        "sources": ["AGENTS.md", "context.md §14", "PRD.md F-01–F-10 and L-03–L-04",
            "backend/app/feedback/", RUBRIC_SOURCE, "cases/{walter_greene,alina_reyes,eli_brooks}.json",
            "backend_kelsch/docs/validation/{action_data,patient_environment,grounding_eval}.json"],
        "counts": {**counts, "cases": len(CASES), "authored_scenarios": len(records),
            "branch_replay_denominator": counts["branches_with_next_visit"],
            "evidence_audit_denominator": counts["evidence_refs"]},
        "na_probe": na,
        "gates": {"evidence_linkage_and_replay": "PASS" if mechanics_ok else "FAIL",
            "faculty_feedback_accuracy": "NOT EVALUABLE", "faculty_rubric_scoring": "NOT EVALUABLE",
            "trained_action_extraction": "NOT EVALUABLE", "clinical_disclosure_accuracy": "NOT EVALUABLE",
            "semantic_grounding": "NOT EVALUABLE", "difficulty_calibration": "NOT EVALUABLE",
            "student_learning": "NOT EVALUABLE"},
        "limitations": ["Authored intents are test inputs, not reviewed student performance labels.",
            "Shared rubric provisional numeric outputs are intentionally discarded; no faculty scores are produced.",
            "Shared documentation fallback detects new numbers and uses lexical overlap for omissions; it cannot certify prose semantics.",
            "Shared decision selection treats unclear as boolean; uncertain branches are flagged and need faculty review.",
            "No independent faculty reviews or observed learner sample imported; prior blocked gates remain blocked."]}
    return report, records


def review_queue(records: list[dict]) -> list[dict]:
    """Pending claim checks, never expectations copied from generated outputs."""
    return [{"case_id": r["case_id"], "scenario": r["scenario"], "case_version": r["case_version"],
        "case_sha256": r["case_source"]["sha256"], "claim_index": i,
        "claim": claim, "expected_supported": None, "review_status": "pending",
        "author_id": "notebook05_fixture", "reviewer_role": None,
        "reviewer_id": None, "reviewed_at": None}
        for r in records for i, claim in enumerate(r["claims"])]


def import_reviews(path: Path, records: list[dict]) -> dict:
    """Reject partial or unverified imports as evidence of feedback accuracy."""
    queue = review_queue(records)
    index = {(r["case_id"], r["scenario"], r["claim_index"]): r for r in queue}
    accepted = {}
    for line_no, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        key = (row.get("case_id"), row.get("scenario"), row.get("claim_index"))
        reference = index.get(key)
        if reference is None or key in accepted:
            raise ValueError(f"unknown or repeated claim review at line {line_no}")
        if (row.get("case_sha256") != reference["case_sha256"] or
            row.get("case_version") != reference["case_version"] or
            row.get("claim") != reference["claim"]):
            raise ValueError("review case/claim source mismatch")
        if (row.get("review_status") != "approved" or row.get("reviewer_role") != "faculty" or
            not row.get("reviewer_id") or row["reviewer_id"] == reference["author_id"] or
            not row.get("reviewed_at") or not isinstance(row.get("expected_supported"), bool)):
            raise ValueError("independent faculty label, identity and timestamp required")
        accepted[key] = row["expected_supported"]
    complete = len(accepted) == len(queue)
    return {"reviewed_claims": len(accepted), "total_claims": len(queue),
            "complete": complete, "feedback_accuracy":
            sum(accepted.values()) / len(queue) if complete and queue else None}
