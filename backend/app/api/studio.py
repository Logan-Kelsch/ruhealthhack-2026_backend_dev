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
from app.schemas.case import Case, ConsistencyFinding
from app.schemas.http import StudioCaseSummary, VhsImportResponse
from app.studio import consistency, drafting, intake, preview, publish, vhs_import
from app.studio.autofill import autofill_labs, autofill_vitals

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


def _full(row) -> dict:
    case = services.load_case(row)
    return {"case": case.model_dump(mode="json"), "status": row.status, "gaps": intake.gaps(case), "blockers": publish.blockers(case)}


def _draft(db: Session, case_id: str) -> Case:
    return services.load_case(services.get_case_row(db, case_id))


@router.get("/cases", response_model=list[StudioCaseSummary])
def list_cases(db: Session = Depends(get_session)) -> list[StudioCaseSummary]:
    """Newest saved version of each case, for the faculty Case Library."""
    return [_summary(r) for r in services.latest_rows(db)]


class NewDraft(BaseModel):
    description: str = Field(min_length=10, max_length=8000)
    faculty: str | None = None


@router.post("/drafts", status_code=201)
def new_draft(body: NewDraft, db: Session = Depends(get_session)) -> dict:
    case, calls = drafting.draft_case(body.description, body.faculty, llm_available())
    row = services.create_case(db, case)
    return {**_full(row), "llm_calls": calls}


@router.get("/cases/{case_id}")
def get_case(case_id: str, version: int | None = None, db: Session = Depends(get_session)) -> dict:
    return _full(services.get_case_row(db, case_id, version))


@router.put("/cases/{case_id}")
def save_case(case_id: str, case: Case, db: Session = Depends(get_session)) -> dict:
    if case.case_id != case_id:
        raise HTTPException(422, "case_id in the body does not match the URL")
    return _full(services.save_draft(db, case))


class IntakeAnswer(BaseModel):
    gap_id: str
    text: str = Field(min_length=1, max_length=4000)
    faculty: str | None = None


@router.post("/cases/{case_id}/intake")
def intake_answer(case_id: str, body: IntakeAnswer, db: Session = Depends(get_session)) -> dict:
    case, calls = intake.answer(_draft(db, case_id), body.gap_id, body.text, body.faculty, llm_available())
    return {**_full(services.save_draft(db, case)), "llm_calls": calls}


# Group name -> (case attribute, the field that identifies one item).
APPROVABLE = {
    "facts": ("facts", "id"), "vitals": ("vitals", "key"), "labs": ("labs", "id"), "exam": ("exam", "maneuver"),
    "artifacts": ("artifacts", "id"), "diagnoses": ("diagnoses", "name"), "medications": ("medications", "name"),
    "allergies": ("allergies", "substance"), "objectives": ("objectives", "id"),
}


class Approve(BaseModel):
    group: str  # a key of APPROVABLE, or "branches"
    keys: list[str] | None = None  # None approves the whole group
    status: Literal["approved", "draft"] = "approved"


@router.post("/cases/{case_id}/approve")
def approve(case_id: str, body: Approve, db: Session = Depends(get_session)) -> dict:
    case = _draft(db, case_id)
    if body.group == "branches":
        items = [(b, b.id) for v in case.visits for b in v.branches]
    elif body.group in APPROVABLE:
        attr, key = APPROVABLE[body.group]
        items = [(i, str(getattr(i, key))) for i in getattr(case, attr)]
    else:
        raise HTTPException(422, f"unknown group {body.group}")
    wanted = set(body.keys) if body.keys is not None else None
    for item, key in items:
        if wanted is None or key in wanted:
            item.status = body.status
    return _full(services.save_draft(db, case))


class Autofill(BaseModel):
    panels: list[str] = Field(default_factory=lambda: ["bmp"])
    vitals: bool = True


@router.post("/cases/{case_id}/autofill")
def autofill(case_id: str, body: Autofill, db: Session = Depends(get_session)) -> dict:
    """Adds proposed values as drafts. Each value records where it came from."""
    case = _draft(db, case_id)
    labs, notes = autofill_labs(case, body.panels)
    case.labs += labs
    added_vitals = []
    if body.vitals:
        added_vitals, vnotes = autofill_vitals(case)
        case.vitals += added_vitals
        notes += vnotes
    full = _full(services.save_draft(db, case))
    return {**full, "added": {"labs": [lab.id for lab in labs], "vitals": [v.key for v in added_vitals]}, "notes": notes}


@router.get("/cases/{case_id}/consistency")
def consistency_check(case_id: str, db: Session = Depends(get_session)) -> list[dict]:
    case = _draft(db, case_id)
    dismissed = {f.message for f in case.consistency_findings if f.dismissed}
    return [{**f.model_dump(), "dismissed": f.message in dismissed} for f in consistency.check(case)]


@router.post("/cases/{case_id}/consistency/{finding_id}/dismiss")
def dismiss_finding(case_id: str, finding_id: str, db: Session = Depends(get_session)) -> dict:
    """Faculty marks a finding as intended. Stored by message, since ids are recomputed on each check."""
    case = _draft(db, case_id)
    finding = next((f for f in consistency.check(case) if f.id == finding_id), None)
    if finding is None:
        raise HTTPException(404, "finding not found; run the check again")
    if not any(f.message == finding.message for f in case.consistency_findings):
        case.consistency_findings.append(ConsistencyFinding(**{**finding.model_dump(), "dismissed": True}))
    return _full(services.save_draft(db, case))


class Preview(BaseModel):
    level: Literal["novice", "competent", "expert", "adversarial"] = "competent"
    driver: Literal["scripted", "llm"] = "scripted"
    visit_id: str | None = None


@router.post("/cases/{case_id}/preview")
def preview_case(case_id: str, body: Preview, db: Session = Depends(get_session)) -> dict:
    """Runs a test student through the case without saving an encounter."""
    case = _draft(db, case_id)
    if body.visit_id and case.visit(body.visit_id) is None:
        raise HTTPException(404, f"visit {body.visit_id} not found")
    driver = body.driver if llm_available() else "scripted"
    return preview.run_test_student(case, body.level, driver=driver, visit_id=body.visit_id)


@router.post("/cases/{case_id}/publish")
def publish_case(case_id: str, db: Session = Depends(get_session)) -> dict:
    row, blockers = services.publish_case(db, case_id)
    if row is None:
        raise HTTPException(409, {"message": "This case is not ready to publish.", "blockers": blockers})
    return _full(row)


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


@router.get("/lookup/icd10")
def lookup_icd10(q: str) -> list[dict]:
    return list(search_icd10(q.strip())) if len(q.strip()) >= 2 else []


@router.get("/vocab")
def vocab() -> dict:
    """Closed label sets the editor offers (topics, actions, exam maneuvers, lab panels)."""
    labs = catalogs.lab_catalog()["labs"]
    return {
        "topics": [{"id": k, "description": v.description} for k, v in catalogs.topics().items()],
        "actions": [{"id": k, "description": v.description} for k, v in catalogs.actions().items()],
        "maneuvers": [{"id": k, "label": v.get("label", k)} for k, v in catalogs.maneuvers().items()],
        "lab_panels": sorted({lab["panel"] for lab in labs if lab.get("panel")}),
    }
