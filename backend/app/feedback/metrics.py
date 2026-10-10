"""Countable communication metrics from the intent tags (PRD F-03), plus the
elicited-versus-missed list (F-02), trust timeline (F-04) and safety items (F-07)."""
from __future__ import annotations

from app import catalogs
from app.encounter.phraser import fact_line
from app.schemas.case import Case


def communication_metrics(turns: list[dict]) -> dict:
    n = len(turns)
    open_q = sum(1 for t in turns if t["intent"].get("question_type") == "open")
    closed_q = sum(1 for t in turns if t["intent"].get("question_type") == "closed")
    reflections = sum(1 for t in turns if any(h["id"] == "reflection" for h in t["intent"].get("empathy", [])))
    validations = sum(1 for t in turns if any(h["id"] == "validation" for h in t["intent"].get("empathy", [])))
    questions = open_q + closed_q
    jargon = [j for t in turns for j in t["intent"].get("jargon", []) if not j.get("explained")]
    interruptions = sum(1 for t in turns for e in t["engine"].get("trust_events", []) if e["event"] == "interrupted")
    student_words = sum(len(t["student_text"].split()) for t in turns)
    patient_words = sum(len(t["reply_text"].split()) for t in turns)
    total_words = student_words + patient_words
    return {
        "turns": n,
        "open_questions": open_q,
        "closed_questions": closed_q,
        "percent_open": round(100 * open_q / questions) if questions else None,
        "reflections": reflections,
        "validations": validations,
        # MITI-style reflection-to-question ratio; 1.0 or more is a common target in MI coding.
        "reflection_to_question_ratio": round(reflections / questions, 2) if questions else None,
        "unexplained_jargon": [{"term": j["term"], "quote": j["span"]} for j in jargon],
        "interruptions": interruptions,
        "student_talk_share": round(100 * student_words / total_words) if total_words else None,
    }


def elicited_vs_missed(case: Case, turns: list[dict]) -> list[dict]:
    disclosed_at: dict[str, int] = {}
    for t in turns:
        for d in t["engine"].get("disclosures", []):
            disclosed_at.setdefault(d["fact_id"], t["idx"])
    topic_labels = {**{k: v.description for k, v in catalogs.topics().items()}, **{t.id: t.description for t in case.topics}}
    out = []
    for obj in case.objectives:
        found, missed = [], []
        for fid in obj.expected_discoveries:
            f = case.fact(fid)
            if f is None:
                continue
            if fid in disclosed_at:
                found.append({"fact_id": fid, "text": f.text, "turn": disclosed_at[fid]})
            else:
                hint_topic = f.unlock.topics[0] if f.unlock.topics else None
                hint = topic_labels.get(hint_topic, "") if hint_topic else ""
                tier_note = " The patient shares this only after trust is built." if f.tier in ("reluctant", "hidden") else ""
                missed.append({"fact_id": fid, "text": f.text, "suggestion": f"Ask about: {hint.lower()}.{tier_note}" if hint else tier_note.strip()})
        done_actions = {h["id"] for t in turns for h in t["intent"].get("actions", [])}
        actions = [{"action": a, "done": a in done_actions} for a in obj.expected_actions]
        out.append({"objective_id": obj.id, "objective": obj.text, "found": found, "missed": missed, "actions": actions})
    return out


def trust_timeline(case: Case, turns: list[dict]) -> list[dict]:
    trust = case.trust.start
    points = [{"turn": 0, "trust": trust, "events": []}]
    for t in turns:
        events = t["engine"].get("trust_events", [])
        trust += sum(e["delta"] for e in events)
        points.append({"turn": t["idx"], "trust": trust, "events": events})
    return points


def safety_items(case: Case, turns: list[dict]) -> list[dict]:
    disclosed = {d["fact_id"] for t in turns for d in t["engine"].get("disclosures", [])}
    done_actions = {h["id"] for t in turns for h in t["intent"].get("actions", [])}
    out = []
    for f in case.facts:
        if not f.safety:
            continue
        related_actions = [a for obj in case.objectives if f.id in obj.expected_discoveries for a in obj.expected_actions]
        out.append(
            {
                "fact_id": f.id,
                "text": f.text,
                "discovered": f.id in disclosed,
                "addressed": any(a in done_actions for a in related_actions) if related_actions else None,
                "patient_words": fact_line(f),
            }
        )
    return out
