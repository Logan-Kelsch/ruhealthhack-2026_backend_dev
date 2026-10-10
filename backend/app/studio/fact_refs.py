"""Places a fact is still named.

A delete that leaves an objective, a release rule, or a visit change pointing at a
missing fact would make later review and disclosure look at nothing. These functions
list those uses so the save can refuse.
"""

from __future__ import annotations

from app.schemas.case import Case, VisitChanges
from app.schemas.http import ErrorItem


def dropped_fact_errors(saved: Case, incoming: Case) -> list[ErrorItem]:
    """References that would dangle if the incoming case replaced the saved one.

    A fact that is still in the incoming case is an edit, not a delete. A fact that
    is gone is allowed only when the incoming case also stops naming it.
    """
    kept = {fact.id for fact in incoming.facts}
    errors: list[ErrorItem] = []
    for fact in saved.facts:
        if fact.id in kept:
            continue
        # Look at the case that would be stored, which is where a dangling id would live.
        errors.extend(fact_reference_errors(incoming, fact.id))
    return errors


def fact_reference_errors(case: Case, fact_id: str) -> list[ErrorItem]:
    """Every remaining use of this fact. An empty list means nothing else names it."""
    found: list[ErrorItem] = []
    for objective in case.objectives:
        if fact_id in objective.expected_discoveries:
            found.append(_ref(fact_id, f"Learning objective {objective.id} still expects this fact."))
    for other in case.facts:
        # A fact does not count as a reference to itself.
        if other.id != fact_id and fact_id in other.unlock.requires_facts:
            found.append(_ref(fact_id, f"Fact {other.id} is withheld until this fact is disclosed."))
    for lab in case.labs:
        if lab.release.fact_id == fact_id:
            found.append(_ref(fact_id, f"Lab {lab.name} is released when this fact is disclosed."))
    for diagnosis in case.diagnoses:
        if diagnosis.release.fact_id == fact_id:
            found.append(_ref(fact_id, f"Diagnosis {diagnosis.name} is released when this fact is disclosed."))
    for medication in case.medications:
        if medication.release.fact_id == fact_id:
            found.append(_ref(fact_id, f"Medication {medication.name} is released when this fact is disclosed."))
    for allergy in case.allergies:
        if allergy.release.fact_id == fact_id:
            found.append(_ref(fact_id, f"Allergy {allergy.substance} is released when this fact is disclosed."))
    for artifact in case.artifacts:
        if artifact.release.fact_id == fact_id:
            found.append(_ref(fact_id, f"File {artifact.title} is released when this fact is disclosed."))
    for visit in case.visits:
        found.extend(_change_errors(visit.label, visit.changes, fact_id))
        for point in visit.decision_points:
            if _predicate_mentions(point.predicate, fact_id):
                found.append(
                    _ref(
                        fact_id,
                        f"Visit {visit.label} decision point {point.id} checks whether this fact was disclosed.",
                    )
                )
        for branch in visit.branches:
            found.extend(_change_errors(f"{visit.label}, {branch.label}", branch.changes, fact_id))
    return found


def _ref(fact_id: str, message: str) -> ErrorItem:
    """One error the client can show next to that fact."""
    return ErrorItem(loc=["facts", fact_id], msg=message, type="fact_referenced")


def _change_errors(where: str, changes: VisitChanges, fact_id: str) -> list[ErrorItem]:
    """Uses of the fact inside one visit or branch change list. where is the label faculty see."""
    found: list[ErrorItem] = []
    if fact_id in changes.remove_facts:
        found.append(_ref(fact_id, f"{where} still removes this fact."))
    if fact_id in changes.update_facts:
        found.append(_ref(fact_id, f"{where} still updates this fact."))
    for lab in changes.labs:
        if lab.release.fact_id == fact_id:
            found.append(_ref(fact_id, f"{where} releases lab {lab.name} when this fact is disclosed."))
    for artifact in changes.artifacts:
        if artifact.release.fact_id == fact_id:
            found.append(_ref(fact_id, f"{where} releases file {artifact.title} when this fact is disclosed."))
    for medication in changes.medications or []:
        if medication.release.fact_id == fact_id:
            found.append(_ref(fact_id, f"{where} releases medication {medication.name} when this fact is disclosed."))
    return found


def _predicate_mentions(predicate: object, fact_id: str) -> bool:
    """True when a decision predicate names this fact, including any/all/not/before groups."""
    if not isinstance(predicate, dict):
        return False
    if predicate.get("fact_disclosed") == fact_id:
        return True
    for value in predicate.values():
        if isinstance(value, dict) and _predicate_mentions(value, fact_id):
            return True
        if isinstance(value, list):
            for item in value:
                if _predicate_mentions(item, fact_id):
                    return True
    return False
