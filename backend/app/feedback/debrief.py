"""Builds the whole debrief for one finished encounter (PRD F-01 to F-10).

Order matters: measurable signals first (code), then the rubric (LLM with evidence,
rule-based fallback), then the documentation check, then the decision path.
"""
from __future__ import annotations

from app.feedback import decisions, documentation, metrics, rubric
from app.schemas.case import Case, Visit


def communication_notes(turns: list[dict], state: dict) -> list[str]:
    notes = []
    si_turn = state.get("first_si_turn")
    if si_turn is not None and not state.get("open_before_si"):
        notes.append(
            "You asked about suicidal thoughts, which is always the right thing to do. "
            "Next time, ask at least one open question first (for example, \"How have things been for you lately?\") so the patient has room to talk before the direct question."
        )
    return notes


def build_debrief(
    case: Case, visit: Visit, turns: list[dict], state: dict, note: dict[str, str] | None, use_llm: bool, prior_branch_id: str | None = None
) -> tuple[dict, list[dict]]:
    views = [decisions.TurnView.from_logged(t["idx"], t["student_text"], t["intent"], t["engine"]) for t in turns]
    dp_results = decisions.evaluate_decision_points(visit, views)
    taken, ghosts = decisions.select_branch(visit, dp_results, prior_branch_id)
    signals = {
        "metrics": metrics.communication_metrics(turns),
        "elicited": metrics.elicited_vs_missed(case, turns),
        "trust_timeline": metrics.trust_timeline(case, turns),
        "safety": metrics.safety_items(case, turns),
        "decision_points": dp_results,
        "communication_notes": communication_notes(turns, state),
    }
    rub, calls = rubric.score_rubric(case, turns, signals, use_llm)
    doc, doc_calls = documentation.check_documentation(case, note, turns, state.get("chart", []), use_llm)
    unclear = [r for r in dp_results if r["result"] == "unclear"]
    debrief = {
        "rubric": rub,
        **signals,
        "documentation": doc,
        "decision_path": {
            "visit_id": visit.id,
            "taken": taken.model_dump() if taken else None,
            "ghosts": [g.model_dump() for g in ghosts],
            "needs_faculty_review": [r["label"] for r in unclear],
        },
    }
    return debrief, calls + doc_calls
