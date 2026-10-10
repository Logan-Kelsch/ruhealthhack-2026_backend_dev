"""Checks authored visits before they are stored.

The decision evaluator only understands the supported operators, and it applies
the first matching outcome. A save that names an unknown label, skips a yes/no
result, or leaves a dangling id would make that choice point at nothing.
"""

from __future__ import annotations

from app import catalogs
from app.schemas.case import Branch, Case, Predicate, Visit, VisitChanges
from app.schemas.http import ErrorItem


def authored_visit_errors(case: Case) -> list[ErrorItem]:
    """Problems that should reject the save. An empty list means the tree can be stored."""
    errors: list[ErrorItem] = []
    seen_visits: set[str] = set()
    previous_day = None
    for index, visit in enumerate(case.visits):
        # A repeated id would make a later visit overwrite the earlier one in lookups.
        if visit.id in seen_visits:
            errors.append(_error(visit.id, f"Visit id {visit.id} is used more than once."))
        seen_visits.add(visit.id)
        if not visit.label.strip():
            errors.append(_error(visit.id, "Write a label for each visit."))
        if previous_day is not None and visit.day < previous_day:
            errors.append(_error(visit.id, f"Visit {visit.label} starts before the previous visit."))
        previous_day = visit.day
        errors.extend(_visit_errors(case, index, visit))
    return errors


def apply_review_status(changes: VisitChanges, status: str) -> None:
    """Copy a faculty approval onto the clinical changes inside a visit or outcome.

    Saving the tree does not do this. A draft stays a draft until this runs.
    """
    for fact in changes.add_facts:
        fact.status = status
    for patch in changes.update_facts.values():
        patch.status = status
    for vital in changes.vitals:
        vital.status = status
    for lab in changes.labs:
        lab.status = status
    for finding in changes.exam:
        finding.status = status
    for artifact in changes.artifacts:
        artifact.status = status
    for medication in changes.medications or []:
        medication.status = status


def _visit_errors(case: Case, index: int, visit: Visit) -> list[ErrorItem]:
    """Count, reference, and coverage problems for one visit."""
    errors: list[ErrorItem] = []
    count = len(visit.decision_points)
    # Zero means the visit is not branched yet. One, or more than four, is not the authored model.
    if count not in (0, 2, 3, 4):
        errors.append(_error(visit.id, f"Visit {visit.label} needs 2 to 4 decision points."))

    point_ids: list[str] = []
    for point in visit.decision_points:
        if point.id in point_ids:
            errors.append(_error(visit.id, f"Decision point {point.id} is used more than once on {visit.label}."))
        point_ids.append(point.id)
        if not point.label.strip():
            errors.append(_error(visit.id, "Write a label for each decision point."))
        _predicate_errors(point.predicate, case, visit, errors)

    branch_ids: list[str] = []
    for branch in visit.branches:
        if branch.id in branch_ids:
            errors.append(_error(visit.id, f"Outcome {branch.id} is used more than once on {visit.label}."))
        branch_ids.append(branch.id)
        if not branch.label.strip() or not branch.summary.strip():
            errors.append(_error(visit.id, "Write what happens for each outcome."))
        for dp_id in branch.when:
            if dp_id not in point_ids:
                errors.append(
                    _error(
                        visit.id,
                        f"Outcome {branch.id} depends on decision point {dp_id}, which is not on visit {visit.id}.",
                    )
                )
        errors.extend(_prior_errors(case, index, visit, branch))
        _change_errors(branch.changes, case, f"Outcome {branch.label}", visit.id, errors)

    _change_errors(visit.changes, case, f"Visit {visit.label}", visit.id, errors)
    # Coverage is reported after reference errors so a dangling id is the message faculty see first.
    if not any(item.type == "visit_authoring" and item.loc[-1:] == [visit.id] for item in errors):
        errors.extend(_coverage_errors(case, index, visit))
    return errors


def _prior_errors(case: Case, index: int, visit: Visit, branch: Branch) -> list[ErrorItem]:
    """after_branches may name only outcomes from the previous visit."""
    if not branch.after_branches:
        return []
    if index == 0:
        return [
            _error(
                visit.id,
                f"Outcome {branch.id} follows branch {branch.after_branches[0]}, which is not on the previous visit.",
            )
        ]
    previous_ids = {item.id for item in case.visits[index - 1].branches}
    found: list[ErrorItem] = []
    for prior_id in branch.after_branches:
        if prior_id not in previous_ids:
            found.append(
                _error(
                    visit.id,
                    f"Outcome {branch.id} follows branch {prior_id}, which is not on the previous visit.",
                )
            )
    return found


def _known_fact_ids(case: Case) -> set[str]:
    """Facts a predicate may name: the chart, plus facts a visit or outcome adds."""
    ids = {fact.id for fact in case.facts}
    for visit in case.visits:
        ids.update(fact.id for fact in visit.changes.add_facts)
        for branch in visit.branches:
            ids.update(fact.id for fact in branch.changes.add_facts)
    return ids


def _predicate_errors(predicate: Predicate, case: Case, visit: Visit, errors: list[ErrorItem]) -> None:
    """Reject labels outside the closed vocabularies, including inside any, all, not, and before."""
    topics = set(catalogs.topics()) | {item.id for item in case.topics}
    actions = set(catalogs.actions()) | {item.id for item in case.actions}
    maneuvers = set(catalogs.maneuvers())
    panels = {lab.get("panel") for lab in catalogs.lab_catalog()["labs"] if lab.get("panel")}
    facts = _known_fact_ids(case)
    _walk_predicate(predicate, visit, topics, actions, maneuvers, panels, facts, errors)


def _walk_predicate(
    predicate: Predicate,
    visit: Visit,
    topics: set[str],
    actions: set[str],
    maneuvers: set[str],
    panels: set[str],
    facts: set[str],
    errors: list[ErrorItem],
) -> None:
    """Check this operator, then the operators nested inside it."""
    if predicate.topic is not None and predicate.topic not in topics:
        errors.append(_error(visit.id, f"Decision point uses topic {predicate.topic}, which is not in the vocabulary."))
    if predicate.action is not None and predicate.action not in actions:
        errors.append(_error(visit.id, f"Decision point uses action {predicate.action}, which is not in the vocabulary."))
    if predicate.maneuver is not None and predicate.maneuver not in maneuvers:
        errors.append(
            _error(visit.id, f"Decision point uses maneuver {predicate.maneuver}, which is not in the vocabulary.")
        )
    if predicate.order is not None and predicate.order not in panels:
        errors.append(_error(visit.id, f"Decision point uses order {predicate.order}, which is not in the vocabulary."))
    if predicate.fact_disclosed is not None and predicate.fact_disclosed not in facts:
        errors.append(
            _error(visit.id, f"Decision point checks fact {predicate.fact_disclosed}, which is not on this case.")
        )
    for child in predicate.any or []:
        _walk_predicate(child, visit, topics, actions, maneuvers, panels, facts, errors)
    for child in predicate.all or []:
        _walk_predicate(child, visit, topics, actions, maneuvers, panels, facts, errors)
    if predicate.not_ is not None:
        _walk_predicate(predicate.not_, visit, topics, actions, maneuvers, panels, facts, errors)
    for child in predicate.before or []:
        _walk_predicate(child, visit, topics, actions, maneuvers, panels, facts, errors)


def _change_errors(changes: VisitChanges, case: Case, where: str, visit_id: str, errors: list[ErrorItem]) -> None:
    """Fact ids and exam maneuvers in a change list have to be ones the case already allows."""
    facts = _known_fact_ids(case)
    maneuvers = set(catalogs.maneuvers())
    for fact_id in changes.remove_facts:
        if fact_id not in facts:
            errors.append(_error(visit_id, f"{where} removes fact {fact_id}, which is not on this case."))
    for fact_id in changes.update_facts:
        if fact_id not in facts:
            errors.append(_error(visit_id, f"{where} updates fact {fact_id}, which is not on this case."))
    for finding in changes.exam:
        if finding.maneuver not in maneuvers:
            errors.append(_error(visit_id, f"{where} uses maneuver {finding.maneuver}, which is not in the vocabulary."))


def _coverage_errors(case: Case, index: int, visit: Visit) -> list[ErrorItem]:
    """Every yes/no result that can change the next visit needs one faculty-written outcome.

    The last visit may list decision points and no outcomes. Nothing is generated to fill a gap.
    """
    result_ids = _result_ids(visit)
    if not result_ids:
        return []
    # No outcomes and no later visit: there is no next state to invent.
    if not visit.branches and index == len(case.visits) - 1:
        return []
    missing = _uncovered(case, index, visit, result_ids)
    if not missing:
        return []
    return [_error(visit.id, f"Visit {visit.label} does not cover every yes or no result.")]


def _result_ids(visit: Visit) -> list[str]:
    """Decision points that choose an outcome: patient changes, plus any id an outcome names."""
    ids: list[str] = []
    for point in visit.decision_points:
        if point.affects == "patient" and point.id not in ids:
            ids.append(point.id)
    for branch in visit.branches:
        for dp_id in branch.when:
            if dp_id not in ids:
                ids.append(dp_id)
    return ids


def _uncovered(case: Case, index: int, visit: Visit, result_ids: list[str]) -> list[dict[str, bool]]:
    """Assignments the first-match rule would leave without an outcome, for each prior path."""
    priors = _prior_paths(case, index)
    missing: list[dict[str, bool]] = []
    for prior in priors:
        for assignment in _assignments(result_ids):
            if not _matched(visit, assignment, prior):
                missing.append(assignment)
    return missing


def _prior_paths(case: Case, index: int) -> list[str | None]:
    """The first visit has no prior outcome. A later visit is reached through the previous outcomes."""
    if index == 0:
        return [None]
    previous = case.visits[index - 1].branches
    if not previous:
        return [None]
    return [branch.id for branch in previous]


def _assignments(ids: list[str]) -> list[dict[str, bool]]:
    """Each yes/no combination. The list is at most four ids, so this stays small."""
    rows: list[dict[str, bool]] = []
    for mask in range(1 << len(ids)):
        rows.append({ids[i]: bool(mask >> i & 1) for i in range(len(ids))})
    return rows


def _matched(visit: Visit, assignment: dict[str, bool], prior: str | None) -> bool:
    """Same first-match rule as branch selection: eligible order, then every named result."""
    for branch in visit.branches:
        if branch.after_branches and prior not in branch.after_branches:
            continue
        if all(assignment.get(dp_id) == want for dp_id, want in branch.when.items()):
            return True
    return False


def _error(visit_id: str, message: str) -> ErrorItem:
    """One save error. loc names the visit so the editor can show the sentence with that visit."""
    return ErrorItem(loc=["visits", visit_id], msg=message, type="visit_authoring")
