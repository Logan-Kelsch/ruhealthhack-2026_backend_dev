"""Student-facing routes (PRD §12). These never return hidden case data such as facts,
trust thresholds or decision points; the full case document is only served by Studio."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import services
from app.db import get_session
from app.integrations import elevenlabs
from app.schemas.student import EncounterSummary, PublicCase, PublicEncounter, TurnResult
from app.student_view import public_case

router = APIRouter(prefix="/api", tags=["encounters"])


@router.get("/cases", response_model=list[PublicCase])
def list_cases(db: Session = Depends(get_session)) -> list[PublicCase]:
    """Published cases a student can open. Drafts and hidden facts are left out."""
    return [public_case(services.load_case(row)) for row in services.latest_rows(db, status="published")]


@router.get("/cases/{case_id}", response_model=PublicCase)
def get_case(
    case_id: str,
    version: int | None = None,
    visit_id: str | None = None,
    db: Session = Depends(get_session),
) -> PublicCase:
    """Briefing for one published visit. This is not the Studio case."""
    case = services.load_case(services.get_case_row(db, case_id, version, status="published"))
    chosen = visit_id or (case.visits[0].id if case.visits else None)
    if chosen is not None and case.visit(chosen) is None:
        raise services.NotFound(f"visit {chosen} not found in {case.case_id}")
    return public_case(case, chosen)


class StartEncounter(BaseModel):
    case_id: str
    version: int | None = None
    visit_id: str | None = None
    student_name: str = ""
    # Set to continue a longitudinal case: starts the next visit with the branch the
    # previous encounter took.
    previous_encounter_id: str | None = None


@router.post("/encounters", status_code=201, response_model=PublicEncounter)
def start_encounter(body: StartEncounter, db: Session = Depends(get_session)) -> PublicEncounter:
    """Saves a new encounter. Refresh must call the encounter read, not this route."""
    enc = services.start_encounter(db, case_id=body.case_id, version=body.version, visit_id=body.visit_id,
                                   student_name=body.student_name, previous_encounter_id=body.previous_encounter_id)
    return services.encounter_view(db, enc)


@router.get("/encounters", response_model=list[EncounterSummary])
def list_encounters(case_id: str | None = None, db: Session = Depends(get_session)) -> list[EncounterSummary]:
    """Saved encounters. The list does not include the transcript or hidden engine state."""
    return services.list_encounters(db, case_id)


@router.get("/encounters/{enc_id}", response_model=PublicEncounter)
def get_encounter(enc_id: str, db: Session = Depends(get_session)) -> PublicEncounter:
    """The saved encounter, with its transcript and released chart. Does not create one."""
    return services.encounter_view(db, services.get_encounter(db, enc_id))


class Utterance(BaseModel):
    # Final transcript of one spoken turn. Also used by test students and scripts; the
    # student UI never offers a text box (AGENTS.md rule 7).
    text: str = Field(min_length=1, max_length=2000)
    start_ms: int | None = None
    end_ms: int | None = None
    # How much patient audio was left when the student spoke over it, if any.
    barge_in_remaining_ms: int | None = None


@router.post("/encounters/{enc_id}/utterances", response_model=TurnResult)
def add_utterance(enc_id: str, body: Utterance, db: Session = Depends(get_session)) -> TurnResult:
    """Runs one committed utterance. The response is the reply and released rows, not the engine log."""
    return services.add_utterance(db, enc_id, body.text, body.start_ms, body.end_ms, body.barge_in_remaining_ms)


@router.post("/encounters/{enc_id}/end", response_model=PublicEncounter)
def end_encounter(enc_id: str, db: Session = Depends(get_session)) -> PublicEncounter:
    """Marks the encounter ended and returns the same saved view."""
    return services.encounter_view(db, services.end_encounter(db, enc_id))


class Documentation(BaseModel):
    fields: dict[str, str]


@router.post("/encounters/{enc_id}/documentation")
def submit_documentation(enc_id: str, body: Documentation, db: Session = Depends(get_session)) -> dict:
    return services.submit_documentation(db, enc_id, body.fields)


@router.get("/encounters/{enc_id}/feedback")
def get_feedback(enc_id: str, db: Session = Depends(get_session)) -> dict:
    return services.get_feedback(db, enc_id)


@router.patch("/encounters/{enc_id}/feedback")
def override_feedback(enc_id: str, overrides: dict, db: Session = Depends(get_session)) -> dict:
    """Faculty overrides (score changes, review notes). Kept beside the generated feedback, never merged into it."""
    return services.override_feedback(db, enc_id, overrides)


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1500)
    voice_id: str | None = None
    audio_tags: list[str] = Field(default_factory=list)


@router.post("/tts", responses={200: {"content": {"audio/mpeg": {}}}, 204: {"description": "No voice service; the browser voice is used instead."}})
def tts(body: TTSRequest) -> Response:
    audio = elevenlabs.synthesize(body.text, body.voice_id, body.audio_tags)
    if audio is None:
        return Response(status_code=204)
    return Response(content=audio, media_type="audio/mpeg")
