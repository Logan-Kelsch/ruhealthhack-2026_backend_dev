"""Patient Studio routes (PRD S-01 to S-09). Faculty only: these return the full case
document, including hidden facts. There is no login in V1 (PRD §15)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import catalogs, services
from app.db import get_session
from app.integrations.bedrock import llm_available
from app.integrations.nlm_tables import search_icd10
from app.models import CaseRow
from app.schemas.case import Case, ConsistencyFinding, Visit
from app.schemas.http import (
    AutofillAdded,
    Icd10Match,
    IntakeGap,
    LlmCallRecord,
    PreviewFallback,
    PreviewRun,
    StudioAutofillResult,
    StudioCaseDetail,
    StudioCaseSummary,
    StudioDraftResult,
    StudioVocab,
    StudioVocabLabel,
    StudioVocabManeuver,
    VhsImportResponse,
)
from app.studio import consistency, drafting, intake, preview, publish, vhs_import
from app.studio.autofill import autofill_labs, autofill_vitals
from app.studio.fact_refs import dropped_fact_errors
from app.studio.visit_authoring import apply_review_status, authored_visit_errors

router = APIRouter(prefix="/api/studio", tags=["studio"])


def _summary(row) -> StudioCaseSummary:
    """Case Library row. Publish blockers are included for a draft so faculty can see why it is held."""
    case = services.load_case(row)
    return StudioCaseSummary(
        case_id=row.case_id,
        version=row.version,
        status=row.status,
        title=row.title,
        golden=case.golden,
        patient=case.profile.name,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
        blockers=publish.blockers(case) if row.status == "draft" else [],
    )


def _saved_status(value: str) -> Literal["draft", "published", "archived"]:
    """Use only a status the case contract names. Anything else is a bad saved row."""
    if value == "draft" or value == "published" or value == "archived":
        return value
    raise HTTPException(500, "Saved case has an unknown status")


def _detail(row: CaseRow) -> StudioCaseDetail:
    """Build the case view from the saved row. Gaps come from the intake rules, not a new guess."""
    case = services.load_case(row)
    return StudioCaseDetail(
        case=case,
        status=_saved_status(row.status),
        gaps=[IntakeGap.model_validate(gap) for gap in intake.gaps(case)],
        blockers=publish.blockers(case),
    )


def _result(row: CaseRow, calls: list[dict]) -> StudioDraftResult:
    """Case view plus the model calls for a create or intake response. Offline, that list is empty."""
    detail = _detail(row)
    return StudioDraftResult(
        case=detail.case,
        status=detail.status,
        gaps=detail.gaps,
        blockers=detail.blockers,
        llm_calls=[LlmCallRecord.model_validate(call) for call in calls],
    )


def _draft(db: Session, case_id: str) -> Case:
    """Load the latest saved case so an edit starts from what was stored."""
    return services.load_case(services.get_case_row(db, case_id))


@router.get("/cases", response_model=list[StudioCaseSummary])
def list_cases(db: Session = Depends(get_session)) -> list[StudioCaseSummary]:
    """Newest saved version of each case, for the faculty Case Library."""
    return [_summary(r) for r in services.latest_rows(db)]


class NewDraft(BaseModel):
    description: str = Field(min_length=10, max_length=8000)
    faculty: str | None = None


@router.post("/drafts", status_code=201, response_model=StudioDraftResult)
def new_draft(body: NewDraft, db: Session = Depends(get_session)) -> StudioDraftResult:
    """Save one draft from the faculty description. The drafting service chooses the content."""
    case, calls = drafting.draft_case(body.description, body.faculty, llm_available())
    row = services.create_case(db, case)
    return _result(row, calls)


@router.get("/cases/{case_id}", response_model=StudioCaseDetail, response_model_exclude_none=True)
def get_case(case_id: str, version: int | None = None, db: Session = Depends(get_session)) -> StudioCaseDetail:
    """Return one saved version. Reading the case does not create another one."""
    return _detail(services.get_case_row(db, case_id, version))


@router.put("/cases/{case_id}", response_model=StudioCaseDetail, response_model_exclude_none=True)
def save_case(case_id: str, case: Case, db: Session = Depends(get_session)) -> StudioCaseDetail:
    """Store faculty edits on the draft. The body is the same case a refresh loads."""
    if case.case_id != case_id:
        raise HTTPException(422, "case_id in the body does not match the URL")
    # Compare with the saved case so a dropped fact cannot leave an objective or rule pointing at it.
    current = _draft(db, case_id)
    blocked = dropped_fact_errors(current, case)
    if blocked:
        raise HTTPException(
            409,
            {
                "message": "A fact is still referenced. Remove those references before deleting it.",
                "errors": [item.model_dump() for item in blocked],
            },
        )
    # Shape is already checked. This rejects unknown labels, dangling ids, and uncovered results.
    problems = authored_visit_errors(case)
    if problems:
        raise HTTPException(
            422,
            {
                "message": problems[0].msg,
                "errors": [item.model_dump() for item in problems],
            },
        )
    return _detail(services.save_draft(db, case))


class IntakeAnswer(BaseModel):
    gap_id: str
    text: str = Field(min_length=1, max_length=4000)
    faculty: str | None = None


@router.post("/cases/{case_id}/intake", response_model=StudioDraftResult)
def intake_answer(case_id: str, body: IntakeAnswer, db: Session = Depends(get_session)) -> StudioDraftResult:
    """Apply one answer to its gap and save that same draft. Intake rules decide what changes."""
    case, calls = intake.answer(_draft(db, case_id), body.gap_id, body.text, body.faculty, llm_available())
    return _result(services.save_draft(db, case), calls)


# Group name -> (case attribute, the field that identifies one item).
APPROVABLE = {
    "facts": ("facts", "id"), "vitals": ("vitals", "key"), "labs": ("labs", "id"), "exam": ("exam", "maneuver"),
    "artifacts": ("artifacts", "id"), "diagnoses": ("diagnoses", "name"), "medications": ("medications", "name"),
    "allergies": ("allergies", "substance"), "objectives": ("objectives", "id"),
}


class Approve(BaseModel):
    """Which saved items change review state. keys limits the change to those ids."""

    group: Literal[
        "facts",
        "vitals",
        "labs",
        "exam",
        "artifacts",
        "diagnoses",
        "medications",
        "allergies",
        "objectives",
        "branches",
        "visit_changes",
    ]
    keys: list[str] | None = None  # None approves the whole group
    status: Literal["approved", "draft"] = "approved"


@router.post("/cases/{case_id}/approve", response_model=StudioCaseDetail)
def approve(case_id: str, body: Approve, db: Session = Depends(get_session)) -> StudioCaseDetail:
    """Set review state on saved items. The returned case is what a refresh loads."""
    case = _draft(db, case_id)
    if body.group == "branches":
        items = [(b, b.id) for v in case.visits for b in v.branches]
    elif body.group == "visit_changes":
        items = [(v, v.id) for v in case.visits]
    elif body.group in APPROVABLE:
        attr, key = APPROVABLE[body.group]
        items = [(i, str(getattr(i, key))) for i in getattr(case, attr)]
    else:
        raise HTTPException(422, f"unknown group {body.group}")
    wanted = set(body.keys) if body.keys is not None else None
    for item, key in items:
        if wanted is not None and key not in wanted:
            continue
        # Outcomes and the clinical changes inside them stay draft until this approval.
        if body.group == "branches":
            item.status = body.status
            apply_review_status(item.changes, body.status)
        elif body.group == "visit_changes":
            apply_review_status(item.changes, body.status)
        else:
            item.status = body.status
    return _detail(services.save_draft(db, case))


class Autofill(BaseModel):
    panels: list[str] = Field(default_factory=lambda: ["bmp"])
    vitals: bool = True


@router.post("/cases/{case_id}/autofill", response_model=StudioAutofillResult)
def autofill(case_id: str, body: Autofill, db: Session = Depends(get_session)) -> StudioAutofillResult:
    """Add proposed values as drafts. Faculty-set labs and vitals are left as they were."""
    case = _draft(db, case_id)
    labs, notes = autofill_labs(case, body.panels)
    case.labs += labs
    added_vitals = []
    if body.vitals:
        added_vitals, vnotes = autofill_vitals(case)
        case.vitals += added_vitals
        notes += vnotes
    detail = _detail(services.save_draft(db, case))
    return StudioAutofillResult(
        case=detail.case,
        status=detail.status,
        gaps=detail.gaps,
        blockers=detail.blockers,
        added=AutofillAdded(labs=[lab.id for lab in labs], vitals=[vital.key for vital in added_vitals]),
        notes=notes,
    )


@router.get("/cases/{case_id}/consistency", response_model=list[ConsistencyFinding])
def consistency_check(case_id: str, db: Session = Depends(get_session)) -> list[ConsistencyFinding]:
    """Recompute findings and mark the ones faculty already dismissed. Ids are not stored as the source of truth."""
    case = _draft(db, case_id)
    dismissed = {f.message for f in case.consistency_findings if f.dismissed}
    # The same message stays dismissed after a refresh, even when the check assigns a new id.
    return [finding.model_copy(update={"dismissed": finding.message in dismissed}) for finding in consistency.check(case)]


@router.post("/cases/{case_id}/consistency/{finding_id}/dismiss", response_model=StudioCaseDetail)
def dismiss_finding(case_id: str, finding_id: str, db: Session = Depends(get_session)) -> StudioCaseDetail:
    """Faculty marks a finding as intended. Stored by message, since ids are recomputed on each check."""
    case = _draft(db, case_id)
    finding = next((f for f in consistency.check(case) if f.id == finding_id), None)
    if finding is None:
        raise HTTPException(404, "finding not found; run the check again")
    marked = False
    for stored in case.consistency_findings:
        # Import and an earlier save can already hold this finding with dismissed false.
        if stored.message == finding.message:
            stored.dismissed = True
            marked = True
    if not marked:
        case.consistency_findings.append(finding.model_copy(update={"dismissed": True}))
    return _detail(services.save_draft(db, case))


class Preview(BaseModel):
    level: Literal["novice", "competent", "expert", "adversarial"] = "competent"
    driver: Literal["scripted", "llm"] = "scripted"
    visit_id: str | None = None


def _preview_visit(case: Case, visit_id: str | None) -> Visit:
    """The visit faculty selected. With no selection, the first visit is the one that runs."""
    if visit_id:
        visit = case.visit(visit_id)
        if visit is None:
            raise HTTPException(404, f"visit {visit_id} not found")
        return visit
    if not case.visits:
        raise HTTPException(404, "visit not found")
    return case.visits[0]


def _preview_driver(requested: Literal["scripted", "llm"]) -> tuple[Literal["scripted", "llm"], PreviewFallback | None]:
    """Keep the requested driver when it can run. Otherwise say the scripted student ran instead."""
    if requested == "llm" and not llm_available():
        return (
            "scripted",
            PreviewFallback(
                requested="llm",
                used="scripted",
                reason="The language model is not available, so the scripted test student ran instead.",
            ),
        )
    return requested, None


@router.post("/cases/{case_id}/preview", response_model=PreviewRun)
def preview_case(case_id: str, body: Preview, db: Session = Depends(get_session)) -> PreviewRun:
    """Runs a test student through the draft. This does not save an encounter."""
    case = _draft(db, case_id)
    visit = _preview_visit(case, body.visit_id)
    driver, fallback = _preview_driver(body.driver)
    raw = preview.run_test_student(case, body.level, driver=driver, visit_id=visit.id)
    return PreviewRun.model_validate(
        {
            "level": body.level,
            "driver": driver,
            "visit_id": visit.id,
            "fallback": None if fallback is None else fallback.model_dump(),
            "transcript": raw["transcript"],
            "discoveries": raw["discoveries"],
            "blocked_replies": raw["blocked_replies"],
            "feedback": raw["feedback"],
            "replies_failing_audit": raw["replies_failing_audit"],
        }
    )


@router.post("/cases/{case_id}/publish", response_model=StudioCaseDetail)
def publish_case(case_id: str, db: Session = Depends(get_session)) -> StudioCaseDetail:
    """Publish the latest draft when every check passes. The response is the version that was saved."""
    row, blockers = services.publish_case(db, case_id)
    if row is None:
        raise HTTPException(409, {"message": "This case is not ready to publish.", "blockers": blockers})
    return _detail(row)


@router.post("/import/vhs", status_code=201, response_model=VhsImportResponse)
def import_vhs(db: Session = Depends(get_session)) -> VhsImportResponse:
    """Imports the full sponsor sample set as drafts. Each saved case stays in review until faculty approve it."""
    # The sample file is the whole set. This route does not take a profile id or an upload.
    try:
        drafted = vhs_import.import_all()
    except vhs_import.VhsImportError as exc:
        # A failed read is not a completed import. Nothing has been saved yet.
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    try:
        # One commit for the set. A failure here rolls back, so a partial import is not saved.
        rows = [services.create_case(db, case, commit=False) for case in drafted]
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="The sponsor sample set could not be imported.") from exc
    saved = [_summary(row) for row in rows]
    return VhsImportResponse(count=len(saved), cases=saved)


@router.get("/lookup/icd10", response_model=list[Icd10Match])
def lookup_icd10(q: str) -> list[Icd10Match]:
    """Diagnosis matches from the existing lookup. A one-character query is too broad to search."""
    query = q.strip()
    if len(query) < 2:
        return []
    return [Icd10Match.model_validate(row) for row in search_icd10(query)]


@router.get("/vocab", response_model=StudioVocab)
def vocab() -> StudioVocab:
    """Closed label sets the editor offers. Maneuver normals come from the exam catalog."""
    labs = catalogs.lab_catalog()["labs"]
    return StudioVocab(
        topics=[StudioVocabLabel(id=key, description=label.description) for key, label in catalogs.topics().items()],
        actions=[StudioVocabLabel(id=key, description=label.description) for key, label in catalogs.actions().items()],
        maneuvers=[
            StudioVocabManeuver(id=key, label=str(row.get("label", key)), normal=str(row.get("normal", "")))
            for key, row in catalogs.maneuvers().items()
        ],
        lab_panels=sorted({lab["panel"] for lab in labs if lab.get("panel")}),
    )
