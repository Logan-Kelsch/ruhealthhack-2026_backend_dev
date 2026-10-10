"""Student-facing routes (PRD §12). These never return hidden case data such as facts,
trust thresholds or decision points; the full case document is only served by Studio."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import services
from app.db import get_session
from app.integrations import elevenlabs

router = APIRouter(prefix="/api", tags=["encounters"])


def _case_card(row) -> dict:
    case = services.load_case(row)
    return {
        "case_id": case.case_id, "version": case.version, "title": case.title, "golden": case.golden,
        "patient": {"name": case.profile.name, "age": case.profile.age, "sex": case.profile.sex, "portrait": case.profile.portrait,
                    "speaker": case.profile.speaker},
        "briefing": case.briefing.model_dump(),
        "visits": [{"id": v.id, "label": v.label, "day": v.day} for v in case.visits],
    }


@router.get("/cases")
def list_cases(db: Session = Depends(get_session)) -> list[dict]:
    return [_case_card(r) for r in services.latest_rows(db, status="published")]


@router.get("/cases/{case_id}")
def get_case(case_id: str, db: Session = Depends(get_session)) -> dict:
    return _case_card(services.get_case_row(db, case_id, status="published"))


class StartEncounter(BaseModel):
    case_id: str
    version: int | None = None
    visit_id: str | None = None
    student_name: str = ""
    # Set to continue a longitudinal case: starts the next visit with the branch the
    # previous encounter took.
    previous_encounter_id: str | None = None


@router.post("/encounters", status_code=201)
def start_encounter(body: StartEncounter, db: Session = Depends(get_session)) -> dict:
    enc = services.start_encounter(db, case_id=body.case_id, version=body.version, visit_id=body.visit_id,
                                   student_name=body.student_name, previous_encounter_id=body.previous_encounter_id)
    return services.encounter_view(enc)


@router.get("/encounters")
def list_encounters(case_id: str | None = None, db: Session = Depends(get_session)) -> list[dict]:
    return services.list_encounters(db, case_id)


@router.get("/encounters/{enc_id}")
def get_encounter(enc_id: str, db: Session = Depends(get_session)) -> dict:
    return services.encounter_view(services.get_encounter(db, enc_id))


class Utterance(BaseModel):
    # Final transcript of one spoken turn. Also used by test students and scripts; the
    # student UI never offers a text box (AGENTS.md rule 7).
    text: str = Field(min_length=1, max_length=2000)
    start_ms: int | None = None
    end_ms: int | None = None
    # How much patient audio was left when the student spoke over it, if any.
    barge_in_remaining_ms: int | None = None


@router.post("/encounters/{enc_id}/utterances")
def add_utterance(enc_id: str, body: Utterance, db: Session = Depends(get_session)) -> dict:
    return services.add_utterance(db, enc_id, body.text, body.start_ms, body.end_ms, body.barge_in_remaining_ms)


@router.post("/encounters/{enc_id}/end")
def end_encounter(enc_id: str, db: Session = Depends(get_session)) -> dict:
    return services.encounter_view(services.end_encounter(db, enc_id))


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
