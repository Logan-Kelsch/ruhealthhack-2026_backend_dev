"""Database-backed operations used by the API and scripts. Pure logic lives in the
encounter/, feedback/ and studio/ packages; this module loads, calls and saves."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import catalogs
from app.encounter import engine
from app.encounter.pipeline import run_turn
from app.encounter.visit import resolve_visit
from app.feedback.debrief import build_debrief
from app.integrations.bedrock import llm_available
from app.models import CaseRow, EncounterRow, TurnRow
from app.schemas.case import Case
from app.studio import publish as publish_rules


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- cases

def latest_rows(db: Session, status: str | None = None) -> list[CaseRow]:
    sub = select(CaseRow.case_id, func.max(CaseRow.version).label("v"))
    if status:
        sub = sub.where(CaseRow.status == status)
    sub = sub.group_by(CaseRow.case_id).subquery()
    q = select(CaseRow).join(sub, (CaseRow.case_id == sub.c.case_id) & (CaseRow.version == sub.c.v)).order_by(CaseRow.title)
    return list(db.scalars(q))


def get_case_row(db: Session, case_id: str, version: int | None = None, status: str | None = None) -> CaseRow:
    q = select(CaseRow).where(CaseRow.case_id == case_id)
    if version is not None:
        q = q.where(CaseRow.version == version)
    if status:
        q = q.where(CaseRow.status == status)
    row = db.scalars(q.order_by(CaseRow.version.desc()).limit(1)).first()
    if row is None:
        raise NotFound(f"case {case_id} not found")
    return row


def load_case(row: CaseRow) -> Case:
    return Case.model_validate(row.doc)


def _unique_case_id(db: Session, base: str) -> str:
    cid, n = base, 2
    while db.scalars(select(CaseRow.id).where(CaseRow.case_id == cid)).first() is not None:
        cid, n = f"{base}_{n}", n + 1
    return cid


def create_case(db: Session, case: Case, *, new_id: bool = True, commit: bool = True) -> CaseRow:
    """Save a new draft. Pass commit=False when several drafts must succeed or fail together."""
    if new_id:
        case.case_id = _unique_case_id(db, case.case_id)
    case.status = "draft"
    row = CaseRow(case_id=case.case_id, version=case.version, status="draft", title=case.title, doc=case.model_dump(mode="json"))
    db.add(row)
    if commit:
        db.commit()
    else:
        # Keep the row in this transaction so a later failure can still roll the set back.
        db.flush()
    return row


def save_draft(db: Session, case: Case) -> CaseRow:
    """Edits always go to a draft. Editing a published case starts the next version."""
    row = get_case_row(db, case.case_id)
    if row.status == "draft":
        case.version, case.status = row.version, "draft"
        row.doc, row.title = case.model_dump(mode="json"), case.title
        db.commit()
        return row
    case.version, case.status = row.version + 1, "draft"
    new = CaseRow(case_id=case.case_id, version=case.version, status="draft", title=case.title, doc=case.model_dump(mode="json"))
    db.add(new)
    db.commit()
    return new


def publish_case(db: Session, case_id: str) -> tuple[CaseRow | None, list[str]]:
    row = get_case_row(db, case_id)
    if row.status == "published":
        return row, []
    case = load_case(row)
    blockers = publish_rules.blockers(case)
    if blockers:
        return None, blockers
    case.status = "published"
    row.doc, row.status, row.published_at = case.model_dump(mode="json"), "published", _now()
    db.commit()
    return row, []


def upsert_golden(db: Session, case: Case) -> CaseRow:
    """Seed or refresh a golden case as published, keeping its case_id."""
    existing = db.scalars(select(CaseRow).where(CaseRow.case_id == case.case_id, CaseRow.version == case.version)).first()
    doc = case.model_dump(mode="json")
    if existing:
        existing.doc, existing.status, existing.title = doc, "published", case.title
        existing.published_at = existing.published_at or _now()
        db.commit()
        return existing
    row = CaseRow(case_id=case.case_id, version=case.version, status="published", title=case.title, doc=doc, published_at=_now())
    db.add(row)
    db.commit()
    return row


# ---------------------------------------------------------------- encounters

def _turn_dicts(db: Session, enc_id: str) -> list[dict]:
    rows = db.scalars(select(TurnRow).where(TurnRow.encounter_id == enc_id).order_by(TurnRow.idx)).all()
    return [{"idx": r.idx, "student_text": r.student_text, "reply_text": r.reply_text, "intent": r.intent, "engine": r.engine,
             "cited_fact_ids": r.cited_fact_ids, "verifier": r.verifier, "latency_ms": r.latency_ms} for r in rows]


def get_encounter(db: Session, enc_id: str) -> EncounterRow:
    enc = db.get(EncounterRow, enc_id)
    if enc is None:
        raise NotFound(f"encounter {enc_id} not found")
    return enc


def start_encounter(db: Session, *, case_id: str, version: int | None, visit_id: str | None, student_name: str, previous_encounter_id: str | None) -> EncounterRow:
    prior_branch = None
    if previous_encounter_id:
        prev = get_encounter(db, previous_encounter_id)
        if prev.feedback is None:
            raise Conflict("finish the previous visit's debrief first")
        case_row = get_case_row(db, prev.case_id, prev.case_version)
        case = load_case(case_row)
        ids = [v.id for v in case.visits]
        i = ids.index(prev.visit_id)
        if i + 1 >= len(ids):
            raise Conflict("this case has no further visits")
        visit_id = ids[i + 1]
        taken = (prev.feedback.get("decision_path") or {}).get("taken")
        if taken:
            prior_branch = next((b for b in case.visit(prev.visit_id).branches if b.id == taken["id"]), None)
    else:
        case_row = get_case_row(db, case_id, version, status="published")
        case = load_case(case_row)
        visit_id = visit_id or case.visits[0].id
        if case.visit(visit_id) is None:
            raise NotFound(f"visit {visit_id} not found in {case.case_id}")
    resolved = resolve_visit(case, visit_id, prior_branch)
    state = engine.new_state(resolved)
    state["prior_branch_id"] = prior_branch.id if prior_branch else None
    state["chart"] = [r.model_dump() for r in engine.visit_start_releases(resolved)]
    enc = EncounterRow(
        id=uuid.uuid4().hex[:16], case_id=case.case_id, case_version=case_row.version, visit_id=visit_id,
        student_name=student_name, status="active", visit_doc=resolved.model_dump(mode="json"), state=state,
        previous_encounter_id=previous_encounter_id,
    )
    db.add(enc)
    db.commit()
    return enc


def encounter_view(enc: EncounterRow) -> dict:
    case = Case.model_validate(enc.visit_doc)
    visit = case.visit(enc.visit_id)
    tmpl = catalogs.documentation_templates()[case.documentation_template]
    return {
        "encounter_id": enc.id, "status": enc.status, "case_id": enc.case_id, "case_version": enc.case_version,
        "visit_id": enc.visit_id, "visit_label": visit.label if visit else enc.visit_id,
        "has_next_visit": bool(case.visits and case.visits[-1].id != enc.visit_id),
        "patient": {"name": case.profile.name, "age": case.profile.age, "sex": case.profile.sex, "pronouns": case.profile.pronouns,
                    "portrait": case.profile.portrait, "speaker": case.profile.speaker, "voice_id": case.profile.voice_id},
        "briefing": case.briefing.model_dump(),
        "chart": enc.state.get("chart", []),
        "documentation_template": {"id": case.documentation_template, **tmpl},
    }


def add_utterance(db: Session, enc_id: str, text: str, start_ms: int | None, end_ms: int | None, barge_in_remaining_ms: int | None) -> dict:
    enc = get_encounter(db, enc_id)
    if enc.status != "active":
        raise Conflict("this encounter has ended")
    text = text.strip()
    if not text:
        raise Conflict("empty utterance")
    case = Case.model_validate(enc.visit_doc)
    turns = _turn_dicts(db, enc_id)
    history = [(t["student_text"], t["reply_text"]) for t in turns]
    out = run_turn(case, enc.state, text, history, barge_in_remaining_ms)
    idx = out.state["turn"]
    db.add(TurnRow(
        encounter_id=enc.id, idx=idx, student_text=text, student_start_ms=start_ms, student_end_ms=end_ms,
        intent=out.intent.model_dump(), engine=out.engine.model_dump(), reply_text=out.reply_text,
        cited_fact_ids=out.cited_fact_ids, verifier=out.verifier, audio_tags=out.audio_tags,
        latency_ms=out.latency_ms, llm_calls=out.llm_calls,
    ))
    enc.state = {**out.state, "prior_branch_id": enc.state.get("prior_branch_id")}
    enc.fallback_used = enc.fallback_used or out.fallback_used
    db.commit()
    return {
        "turn": idx, "reply_text": out.reply_text, "speaker": case.profile.speaker or case.profile.name,
        "audio_tags": out.audio_tags, "chart_releases": [r.model_dump() for r in out.engine.chart_releases],
        "exam_results": [r.model_dump() for r in out.engine.exam_results], "notices": [n.model_dump() for n in out.engine.notices],
        "mode": out.verifier["mode"], "latency_ms": out.latency_ms,
    }


def end_encounter(db: Session, enc_id: str) -> EncounterRow:
    enc = get_encounter(db, enc_id)
    if enc.status == "active":
        enc.status, enc.ended_at = "ended", _now()
        db.commit()
    return enc


def build_feedback(db: Session, enc: EncounterRow) -> dict:
    case = Case.model_validate(enc.visit_doc)
    visit = case.visit(enc.visit_id)
    turns = _turn_dicts(db, enc.id)
    debrief, calls = build_debrief(case, visit, turns, enc.state, enc.documentation, llm_available(), enc.state.get("prior_branch_id"))
    debrief["transcript"] = [{"turn": t["idx"], "student": t["student_text"], "patient": t["reply_text"], "mode": t["verifier"].get("mode")} for t in turns]
    debrief["llm_calls"] = calls
    debrief["fallback_used"] = enc.fallback_used
    debrief["generated_at"] = _now().isoformat()
    enc.feedback = debrief
    enc.status = "complete"
    db.commit()
    return debrief


def submit_documentation(db: Session, enc_id: str, fields: dict[str, str]) -> dict:
    enc = get_encounter(db, enc_id)
    if enc.status == "active":
        end_encounter(db, enc_id)
    enc.documentation = {k: str(v) for k, v in fields.items()}
    db.commit()
    return build_feedback(db, enc)


def get_feedback(db: Session, enc_id: str) -> dict:
    enc = get_encounter(db, enc_id)
    if enc.status == "active":
        raise Conflict("end the encounter first")
    fb = enc.feedback or build_feedback(db, enc)
    return {**fb, "overrides": enc.feedback_overrides or {}}


def override_feedback(db: Session, enc_id: str, overrides: dict) -> dict:
    enc = get_encounter(db, enc_id)
    enc.feedback_overrides = {**(enc.feedback_overrides or {}), **overrides, "updated_at": _now().isoformat()}
    db.commit()
    return enc.feedback_overrides


def list_encounters(db: Session, case_id: str | None = None) -> list[dict]:
    q = select(EncounterRow).order_by(EncounterRow.started_at.desc())
    if case_id:
        q = q.where(EncounterRow.case_id == case_id)
    out = []
    for e in db.scalars(q.limit(200)):
        total = ((e.feedback or {}).get("rubric") or {}).get("total")
        out.append({"encounter_id": e.id, "case_id": e.case_id, "visit_id": e.visit_id, "student_name": e.student_name, "status": e.status,
                    "started_at": e.started_at.isoformat() if e.started_at else None, "rubric_total": total,
                    "review_flag": ((e.feedback or {}).get("rubric") or {}).get("review_flag", False),
                    "previous_encounter_id": e.previous_encounter_id})
    return out
