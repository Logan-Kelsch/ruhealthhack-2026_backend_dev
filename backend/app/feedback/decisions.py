"""Decision points (PRD L-03) and branch selection (L-04). Pure functions.

A decision point is a predicate over the tagged turns of one encounter. The result is
"yes", "no", or "unclear" (only low-confidence tags supported it), always with evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.schemas.case import Branch, DecisionPoint, Predicate, Visit


@dataclass
class TurnView:
    """The parts of a logged turn that predicates look at."""

    idx: int
    student_text: str
    topics: dict[str, tuple[str, str]]  # id -> (span, confidence)
    actions: dict[str, tuple[str, str]]
    maneuvers: dict[str, tuple[str, str]]
    orders: dict[str, tuple[str, str]]
    question_type: str
    disclosed: list[str] = field(default_factory=list)

    @classmethod
    def from_logged(cls, idx: int, student_text: str, intent: dict, engine: dict) -> "TurnView":
        def m(key: str) -> dict[str, tuple[str, str]]:
            return {h["id"]: (h["span"], h.get("confidence", "high")) for h in intent.get(key, [])}

        return cls(
            idx=idx,
            student_text=student_text,
            topics=m("topics"),
            actions=m("actions"),
            maneuvers=m("maneuvers"),
            orders=m("orders"),
            question_type=intent.get("question_type", "statement"),
            disclosed=[d["fact_id"] for d in engine.get("disclosures", [])],
        )


@dataclass
class Match:
    turns: list[int]
    spans: list[str]
    low_confidence: bool


def _leaf_matches(pred: dict[str, Any], turns: list[TurnView]) -> Match:
    hits: list[tuple[int, str, str]] = []
    for t in turns:
        for key, attr in (("topic", "topics"), ("action", "actions"), ("maneuver", "maneuvers"), ("order", "orders")):
            if key in pred and pred[key] in getattr(t, attr):
                span, conf = getattr(t, attr)[pred[key]]
                hits.append((t.idx, span, conf))
        if "fact_disclosed" in pred and pred["fact_disclosed"] in t.disclosed:
            hits.append((t.idx, t.student_text, "high"))
        if pred.get("open_question") and t.question_type == "open":
            hits.append((t.idx, t.student_text, "high"))
    return Match(
        turns=[h[0] for h in hits],
        spans=[h[1] for h in hits],
        low_confidence=bool(hits) and all(h[2] == "low" for h in hits),
    )


def evaluate_predicate(pred: Predicate | dict[str, Any], turns: list[TurnView]) -> tuple[bool, Match]:
    """Yes or no for one predicate. A saved model is read as the same operator object as a dict."""
    if isinstance(pred, Predicate):
        # Dumping here keeps the match order below unchanged for golden cases and unit tests.
        pred = pred.model_dump(by_alias=True, exclude_none=True)
    if "any" in pred:
        results = [evaluate_predicate(p, turns) for p in pred["any"]]
        good = [m for ok, m in results if ok]
        if not good:
            return False, Match([], [], False)
        return True, Match(sum((m.turns for m in good), []), sum((m.spans for m in good), []), all(m.low_confidence for m in good))
    if "all" in pred:
        results = [evaluate_predicate(p, turns) for p in pred["all"]]
        if not all(ok for ok, _ in results):
            return False, Match([], [], False)
        return True, Match(sum((m.turns for _, m in results), []), sum((m.spans for _, m in results), []), any(m.low_confidence for _, m in results))
    if "not" in pred:
        ok, m = evaluate_predicate(pred["not"], turns)
        return (not ok), Match([], [], ok and m.low_confidence)
    if "before" in pred:
        first, second = pred["before"]
        ok1, m1 = evaluate_predicate(first, turns)
        ok2, m2 = evaluate_predicate(second, turns)
        if not ok2:
            return False, Match([], [], False)
        first_second = min(m2.turns)
        earlier = [i for i in m1.turns if i < first_second] if ok1 else []
        if not earlier:
            return False, Match([first_second], m2.spans[:1], False)
        return True, Match(earlier[:1] + [first_second], [m1.spans[m1.turns.index(earlier[0])], m2.spans[0]], m1.low_confidence or m2.low_confidence)
    m = _leaf_matches(pred, turns)
    return bool(m.turns), m


def evaluate_decision_points(visit: Visit, turns: list[TurnView]) -> list[dict]:
    out = []
    for dp in visit.decision_points:
        ok, m = evaluate_predicate(dp.predicate, turns)
        result = "unclear" if m.low_confidence else ("yes" if ok else "no")
        out.append(
            {
                "id": dp.id,
                "label": dp.label,
                "affects": dp.affects,
                "result": result,
                "value": ok,
                "evidence": [{"turn": t, "quote": s} for t, s in zip(m.turns, m.spans)][:3],
                "feedback": dp.feedback_if_yes if ok else dp.feedback_if_no,
                "rubric_domain": dp.rubric_domain,
            }
        )
    return out


def select_branch(visit: Visit, results: list[dict], prior_branch_id: str | None = None) -> tuple[Branch | None, list[Branch]]:
    """First branch whose conditions all match wins. 'unclear' counts as its boolean value
    for path selection and is flagged for faculty review in the debrief."""
    values = {r["id"]: r["value"] for r in results}
    eligible = [b for b in visit.branches if not b.after_branches or prior_branch_id in b.after_branches]
    taken = None
    for b in eligible:
        if all(values.get(dp_id) == want for dp_id, want in b.when.items()):
            taken = b
            break
    ghosts = [b for b in eligible if taken is None or b.id != taken.id]
    return taken, ghosts


def decision_points_by_id(visit: Visit) -> dict[str, DecisionPoint]:
    return {d.id: d for d in visit.decision_points}
