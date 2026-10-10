"""Student-facing routes (PRD §12). These never return hidden case data such as facts,
trust thresholds or decision points; the full case document is only served by Studio."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import services
from app.db import get_session
from app.integrations import elevenlabs
from app.schemas.feedback import FeedbackOverrideRequest, FeedbackResponse
from app.schemas.http import ScribeToken
from app.schemas.student import EncounterList, PublicCase, PublicEncounter, TurnResult, WordTimestamp
from app.settings import get_settings
from app.student_view import public_case

router = APIRouter(prefix="/api", tags=["encounters"])


@router.post("/stt/token", response_model=ScribeToken)
def scribe_token() -> ScribeToken:
    """Issue one single-use Scribe token. Building the OpenAPI schema does not call this."""
    try:
        token = elevenlabs.create_scribe_token()
    except elevenlabs.MissingScribeConfig as exc:
        raise services.Conflict(str(exc)) from exc
    except elevenlabs.ScribeTokenError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ScribeToken(token=token)


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


@router.get("/encounters", response_model=EncounterList)
def list_encounters(
    case_id: str | None = None,
    student_name: str | None = None,
    limit: int = Query(default=200, ge=1, le=200),
    db: Session = Depends(get_session),
) -> EncounterList:
    """Saved encounters. total counts rows past the limit so a short page is not the whole history."""
    return services.list_encounters(db, case_id, student_name, limit)


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
    # Word times when Scribe sent them. Omitted words stay an empty list.
    words: list[WordTimestamp] = Field(default_factory=list)
    # How much patient audio was left when the student spoke over it, if any.
    barge_in_remaining_ms: int | None = None


@router.post("/encounters/{enc_id}/utterances", response_model=TurnResult)
def add_utterance(enc_id: str, body: Utterance, db: Session = Depends(get_session)) -> TurnResult:
    """Runs one committed utterance. The response is the reply and released rows, not the engine log."""
    return services.add_utterance(
        db,
        enc_id,
        body.text,
        body.start_ms,
        body.end_ms,
        body.barge_in_remaining_ms,
        [word.model_dump() for word in body.words],
    )


@router.post("/encounters/{enc_id}/end", response_model=PublicEncounter)
def end_encounter(enc_id: str, db: Session = Depends(get_session)) -> PublicEncounter:
    """Marks the encounter ended and returns the same saved view."""
    return services.encounter_view(db, services.end_encounter(db, enc_id))


class Documentation(BaseModel):
    fields: dict[str, str]


@router.post("/encounters/{enc_id}/documentation", response_model=FeedbackResponse)
def submit_documentation(enc_id: str, body: Documentation, db: Session = Depends(get_session)) -> dict:
    """Save the dictated note and return the debrief, including the fabrication check."""
    return services.submit_documentation(db, enc_id, body.fields)


@router.get("/encounters/{enc_id}/feedback", response_model=FeedbackResponse)
def get_feedback(enc_id: str, db: Session = Depends(get_session)) -> dict:
    """The saved debrief. A missing encounter is 404. An active visit is 409."""
    return services.get_feedback(db, enc_id)


@router.patch("/encounters/{enc_id}/feedback", response_model=FeedbackResponse)
def override_feedback(enc_id: str, body: FeedbackOverrideRequest, db: Session = Depends(get_session)) -> dict:
    """Save a faculty score or comment beside the generated debrief. The generated scores stay as they were."""
    return services.override_feedback(db, enc_id, body)


def _client_supplied_speech(raw: bytes) -> bool:
    """True when the body tries to choose the words. Only an empty body is accepted."""
    if not raw:
        return False
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return True
    return payload not in ({}, None)


@router.post(
    "/encounters/{enc_id}/turns/{turn}/speech",
    response_model=None,
    responses={
        200: {
            "description": "MPEG audio of the saved verified reply, streamed as chunks. This body is not JSON.",
            "content": {"audio/mpeg": {"schema": {"type": "string", "format": "binary"}}},
        },
        204: {"description": "No voice service is configured, so there is no audio."},
    },
)
async def speak_turn(enc_id: str, turn: int, request: Request, db: Session = Depends(get_session)) -> Response:
    """Stream the saved verified reply for one turn. Client text is not spoken."""
    if "text" in request.query_params or _client_supplied_speech(await request.body()):
        raise HTTPException(status_code=422, detail="Speech is taken from the saved verified reply.")
    reply, tags, case_voice = services.verified_speech(db, enc_id, turn)
    settings = get_settings()
    # The case voice wins. The default voice is only the backup when the case has none.
    voice = case_voice or settings.elevenlabs_default_voice_id
    if not settings.elevenlabs_api_key or not voice:
        return Response(status_code=204)
    try:
        opened = await elevenlabs.open_speech(reply, voice, tags)
    except elevenlabs.SpeechProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    async def release_when_the_client_leaves() -> None:
        """Close the vendor stream if the student cancels while a later chunk is still pending."""
        while True:
            message = await request.receive()
            if message["type"] == "http.disconnect":
                await opened.aclose()
                return

    async def chunks():
        """Send audio as it arrives, and close the vendor stream when the client stops."""
        watcher = asyncio.create_task(release_when_the_client_leaves())
        try:
            yield opened.first
            async for piece in opened.remaining():
                yield piece
        finally:
            await opened.aclose()
            watcher.cancel()
            try:
                await watcher
            except asyncio.CancelledError:
                pass

    return StreamingResponse(chunks(), media_type="audio/mpeg")


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
