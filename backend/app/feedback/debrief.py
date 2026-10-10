"""Builds the whole debrief for one finished encounter (PRD F-01 to F-10).

Order matters: measurable signals first (code), then the rubric (LLM with evidence,
rule-based fallback), then the documentation check, then the decision path.
"""
from __future__ import annotations

from app.feedback import decisions, documentation, metrics, rubric
from app.schemas.case import Branch, Case, Visit


def _outcome_evidence(branch: Branch, results: list[dict]) -> list[dict]:
    """Quotes for the decision points that name this outcome. The condition itself is left out."""
    seen: set[tuple[int, str]] = set()
    quotes: list[dict] = []
    for decision_id in branch.when:
        result = next((item for item in results if item["id"] == decision_id), None)
        if result is None:
            continue
        # A quote supports this outcome only when the decision landed on the value the outcome requires.
        if bool(result["value"]) != branch.when[decision_id]:
            continue
        for span in result["evidence"]:
            key = (span["turn"], span["quote"])
            if key in seen:
                continue
            seen.add(key)
            quotes.append({"turn": span["turn"], "quote": span["quote"]})
    return quotes


def _public_outcome(branch: Branch, results: list[dict]) -> dict:
    """Label and summary only. Branch edits, predicates, and common/rare tags stay off the debrief."""
    return {
        "id": branch.id,
        "label": branch.label,
        "summary": branch.summary,
        "evidence": _outcome_evidence(branch, results),
    }


def _public_decisions(results: list[dict]) -> list[dict]:
    """The yes/no results with their quotes. Students use these to see why a path was selected."""
    public: list[dict] = []
    for item in results:
        public.append(
            {
                "id": item["id"],
                "label": item["label"],
                "result": item["result"],
                "evidence": [{"turn": span["turn"], "quote": span["quote"]} for span in item["evidence"]],
                "feedback": item["feedback"] or "",
            }
        )
    return public


def communication_notes(turns: list[dict], state: dict) -> list[str]:
    """Notes that are not score deductions. Asking about suicidal thoughts is never one of those."""
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
    """Score the saved visit and attach the public path. This does not choose the next visit's facts."""
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
            "taken": _public_outcome(taken, dp_results) if taken else None,
            "ghosts": [_public_outcome(branch, dp_results) for branch in ghosts],
            "decisions": _public_decisions(dp_results),
            "needs_faculty_review": [r["label"] for r in unclear],
        },
    }
    return debrief, calls + doc_calls
