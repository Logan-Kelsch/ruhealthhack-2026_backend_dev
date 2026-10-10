"""Database-backed operations used by the API and scripts. Pure logic lives in the
encounter/, feedback/ and studio/ packages; this module loads, calls and saves."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.encounter import engine
from app.encounter.pipeline import run_turn
from app.encounter.visit import resolve_visit
from app.feedback.debrief import build_debrief
from app.integrations.bedrock import llm_available
from app.models import CaseRow, EncounterRow, TurnRow
from app.schemas.case import Case
from app.schemas.feedback import FeedbackOverrideRequest, FeedbackOverrides
from app.schemas.student import EncounterList, EncounterSummary, TurnResult
from app.student_view import _encounter_status, public_encounter, public_turn
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


def encounter_view(db: Session, enc: EncounterRow):
    """Load the saved turns and return the student view. This does not start an encounter."""
    turns = list(db.scalars(select(TurnRow).where(TurnRow.encounter_id == enc.id).order_by(TurnRow.idx)))
    return public_encounter(enc, turns)


def add_utterance(
    db: Session,
    enc_id: str,
    text: str,
    start_ms: int | None,
    end_ms: int | None,
    barge_in_remaining_ms: int | None,
    words: list[dict] | None = None,
) -> TurnResult:
    """Save one turn and return the reply a student may see. The engine log stays on the turn row."""
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
        student_words=list(words or []),
        intent=out.intent.model_dump(), engine=out.engine.model_dump(), reply_text=out.reply_text,
        cited_fact_ids=out.cited_fact_ids, verifier=out.verifier, audio_tags=out.audio_tags,
        latency_ms=out.latency_ms, llm_calls=out.llm_calls,
    ))
    enc.state = {**out.state, "prior_branch_id": enc.state.get("prior_branch_id")}
    enc.fallback_used = enc.fallback_used or out.fallback_used
    db.commit()
    # The student receives the reply and released rows. Intent tags and trust stay on the turn row.
    return public_turn(
        case,
        turn=idx,
        reply_text=out.reply_text,
        audio_tags=out.audio_tags,
        chart_releases=[item.model_dump() for item in out.engine.chart_releases],
        exam_results=[item.model_dump() for item in out.engine.exam_results],
        notices=[item.model_dump() for item in out.engine.notices],
        mode=out.verifier["mode"],
        latency_ms=out.latency_ms,
    )


def verified_speech(db: Session, enc_id: str, turn: int) -> tuple[str, list[str], str | None]:
    """The saved reply, the tags the engine chose, and the case voice.

    Client text never reaches this function. A reply that did not pass verification
    is refused so an unchecked phrasing cannot be spoken.
    """
    enc = get_encounter(db, enc_id)
    row = db.scalars(select(TurnRow).where(TurnRow.encounter_id == enc.id, TurnRow.idx == turn)).first()
    if row is None:
        raise NotFound(f"turn {turn} not found")
    if row.verifier.get("passed") is not True:
        raise Conflict("This reply was not verified and will not be spoken.")
    case = Case.model_validate(enc.visit_doc)
    return row.reply_text, list(row.audio_tags or []), case.profile.voice_id


def end_encounter(db: Session, enc_id: str) -> EncounterRow:
    """Mark the visit ended. A second end leaves the saved row as it is."""
    enc = get_encounter(db, enc_id)
    if enc.status == "active":
        enc.status, enc.ended_at = "ended", _now()
        db.commit()
    return enc


def _reply_mode(verifier: dict) -> str:
    """The debrief only reports template or llm. Anything else was the template path."""
    mode = verifier.get("mode")
    if mode == "llm":
        return "llm"
    return "template"


def build_feedback(db: Session, enc: EncounterRow) -> dict:
    """Score the saved encounter and store the debrief. This does not start a new encounter."""
    case = Case.model_validate(enc.visit_doc)
    visit = case.visit(enc.visit_id)
    turns = _turn_dicts(db, enc.id)
    debrief, calls = build_debrief(case, visit, turns, enc.state, enc.documentation, llm_available(), enc.state.get("prior_branch_id"))
    debrief["transcript"] = [
        {"turn": t["idx"], "student": t["student_text"], "patient": t["reply_text"], "mode": _reply_mode(t["verifier"])}
        for t in turns
    ]
    debrief["llm_calls"] = calls
    debrief["fallback_used"] = enc.fallback_used
    debrief["generated_at"] = _now().isoformat()
    enc.feedback = debrief
    enc.status = "complete"
    db.commit()
    return debrief


def submit_documentation(db: Session, enc_id: str, fields: dict[str, str]) -> dict:
    """Save the dictated note, then build the debrief from that note and the disclosure log."""
    enc = get_encounter(db, enc_id)
    if enc.status == "active":
        end_encounter(db, enc_id)
    enc.documentation = {k: str(v) for k, v in fields.items()}
    db.commit()
    return build_feedback(db, enc)


def _saved_overrides(raw: dict | None) -> dict | None:
    """Turn the stored override into the response shape. An empty column means faculty have not changed anything."""
    if not raw:
        return None
    return FeedbackOverrides.model_validate(raw).model_dump()


def get_feedback(db: Session, enc_id: str) -> dict:
    """Return the saved debrief. An active visit has none yet, and this does not create an encounter."""
    enc = get_encounter(db, enc_id)
    if enc.status == "active":
        raise Conflict("end the encounter first")
    fb = enc.feedback or build_feedback(db, enc)
    # The generated debrief stays intact. Faculty changes are a sibling field.
    return {**fb, "overrides": _saved_overrides(enc.feedback_overrides)}


def override_feedback(db: Session, enc_id: str, body: FeedbackOverrideRequest) -> dict:
    """Store a score or comment next to the generated debrief, then return both."""
    enc = get_encounter(db, enc_id)
    if enc.status == "active":
        raise Conflict("end the encounter first")
    if not enc.feedback:
        # Ended visits are scored on first read. The override is not itself a score.
        build_feedback(db, enc)
        enc = get_encounter(db, enc_id)
    current = FeedbackOverrides.model_validate(enc.feedback_overrides) if enc.feedback_overrides else None
    # A later change replaces only the domain or comment it names. Earlier faculty changes stay.
    scores = {item.domain: item for item in (current.scores if current else [])}
    for item in body.scores:
        scores[item.domain] = item
    comments = {(item.domain, item.field): item for item in (current.comments if current else [])}
    for item in body.comments:
        comments[(item.domain, item.field)] = item
    saved = FeedbackOverrides(
        scores=list(scores.values()),
        comments=list(comments.values()),
        updated_at=_now().isoformat(),
    )
    enc.feedback_overrides = saved.model_dump()
    # The generated feedback column is not written here.
    db.commit()
    return get_feedback(db, enc_id)


def _summary_names(enc: EncounterRow) -> tuple[str, str, str]:
    """Patient, title, and visit label from the saved snapshot. A bad snapshot still leaves the ids on the row."""
    try:
        case = Case.model_validate(enc.visit_doc)
    except ValidationError:
        return "", "", ""
    visit = case.visit(enc.visit_id)
    return case.profile.name, case.title, visit.label if visit else ""


def list_encounters(
    db: Session,
    case_id: str | None = None,
    student_name: str | None = None,
    limit: int = 200,
) -> EncounterList:
    """Saved encounters for one case, one student, or every saved visit. Hidden state stays off the row."""
    clauses = []
    if case_id:
        clauses.append(EncounterRow.case_id == case_id)
    if student_name is not None:
        clauses.append(EncounterRow.student_name == student_name)
    count_query = select(func.count()).select_from(EncounterRow)
    rows = select(EncounterRow).order_by(EncounterRow.started_at.desc())
    for clause in clauses:
        count_query = count_query.where(clause)
        rows = rows.where(clause)
    total = int(db.scalar(count_query) or 0)
    out: list[EncounterSummary] = []
    for enc in db.scalars(rows.limit(limit)):
        rubric = (enc.feedback or {}).get("rubric") or {}
        rubric_total = rubric.get("total")
        patient_name, case_title, visit_label = _summary_names(enc)
        out.append(
            EncounterSummary(
                encounter_id=enc.id,
                case_id=enc.case_id,
                visit_id=enc.visit_id,
                student_name=enc.student_name,
                status=_encounter_status(enc.status),
                started_at=enc.started_at,
                rubric_total=rubric_total if isinstance(rubric_total, int) else None,
                review_flag=bool(rubric.get("review_flag", False)),
                previous_encounter_id=enc.previous_encounter_id,
                patient_name=patient_name,
                case_title=case_title,
                visit_label=visit_label,
            )
        )
    return EncounterList(encounters=out, total=total, limit=limit)
