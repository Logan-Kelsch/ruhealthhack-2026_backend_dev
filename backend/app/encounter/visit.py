"""Builds the exact patient state for one visit: the case, plus that visit's changes,
plus the faculty-written branch selected by the student's previous visit.

The LLM never extrapolates the next state; it only comes from authored changes.
"""
from __future__ import annotations

from app.schemas.case import Branch, Case, Fact, VisitChanges


def _replace_by(items: list, new_items: list, key: str) -> list:
    out = {getattr(i, key): i for i in items}
    for n in new_items:
        out[getattr(n, key)] = n
    return list(out.values())


def apply_changes(case: Case, changes: VisitChanges) -> Case:
    c = case.model_copy(deep=True)
    removed = set(changes.remove_facts)
    facts: list[Fact] = [f for f in c.facts if f.id not in removed]
    for fact_id, patch in changes.update_facts.items():
        for i, f in enumerate(facts):
            if f.id == fact_id:
                facts[i] = Fact.model_validate({**f.model_dump(), **patch})
    facts = _replace_by(facts, changes.add_facts, "id")
    c.facts = facts
    c.vitals = _replace_by(c.vitals, changes.vitals, "key")
    c.labs = _replace_by(c.labs, changes.labs, "key")
    c.exam = _replace_by(c.exam, changes.exam, "maneuver")
    c.artifacts = _replace_by(c.artifacts, changes.artifacts, "id")
    if changes.medications is not None:
        c.medications = list(changes.medications)
    if changes.briefing is not None:
        merged = c.briefing.model_dump()
        merged.update({k: v for k, v in changes.briefing.model_dump().items() if v not in ("", None)})
        c.briefing = c.briefing.model_validate(merged)
    if changes.mood:
        c.profile.personality.mood = changes.mood
    return c


def resolve_visit(case: Case, visit_id: str, branch: Branch | None = None) -> Case:
    visit = case.visit(visit_id)
    if visit is None:
        raise KeyError(f"visit {visit_id} not in case {case.case_id}")
    resolved = apply_changes(case, visit.changes)
    if branch is not None:
        resolved = apply_changes(resolved, branch.changes)
    return resolved


def previous_visit(case: Case, visit_id: str):
    ids = [v.id for v in case.visits]
    i = ids.index(visit_id)
    return case.visits[i - 1] if i > 0 else None
