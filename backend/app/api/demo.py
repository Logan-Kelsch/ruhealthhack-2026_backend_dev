"""Opt-in presenter rehearsal API. Production encounter routes remain separate."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_session
from app.demo import service
from app.schemas.demo import (PrepareRequest, Preparation, StartRequest, DemoSession,
                             DemoTurnRequest, DemoTurnResult, DemoDebrief, EducatorScenario)
from app.schemas.http import ErrorResponse
from app.settings import get_settings

def enabled() -> None:
    if not get_settings().scripted_demo_enabled:
        raise HTTPException(404, "Scripted demo is disabled")

router = APIRouter(prefix="/api/demo", tags=["scripted-demo"], dependencies=[Depends(enabled)],
                   responses={404:{"model":ErrorResponse},409:{"model":ErrorResponse}})

@router.get("/educator/scenarios", response_model=list[EducatorScenario])
def scenarios():
    return service.educator_scenarios()

@router.post("/educator/preparations", status_code=201, response_model=Preparation)
def prepare(body: PrepareRequest, db: Session=Depends(get_session)):
    return service.prepare(db,body.scenario_id,body.description)

@router.post("/sessions", response_model=DemoSession)
def start(body: StartRequest, db: Session=Depends(get_session)):
    return service.start(db,body.preparation_id)

@router.get("/sessions/{sid}", response_model=DemoSession)
def read(sid: str, db: Session=Depends(get_session)):
    return service.view(db,sid)

@router.post("/sessions/{sid}/turns", response_model=DemoTurnResult)
def turn(sid: str, body: DemoTurnRequest, db: Session=Depends(get_session)):
    return service.turn(db,sid,body.expected_step,body.request_id,body.text)

@router.post("/sessions/{sid}/end", response_model=DemoSession)
def end(sid: str, db: Session=Depends(get_session)):
    return service.end(db,sid)

@router.get("/sessions/{sid}/debrief", response_model=DemoDebrief)
def debrief(sid: str, db: Session=Depends(get_session)):
    return service.debrief(db,sid)
