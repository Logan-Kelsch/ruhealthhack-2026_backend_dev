"""Three tables. The case is one validated JSON document; an encounter keeps its
engine state and outputs as JSON; each turn keeps everything needed for replay."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, JSONType


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CaseRow(Base):
    __tablename__ = "cases"
    __table_args__ = (UniqueConstraint("case_id", "version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[str] = mapped_column(String(120), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))  # draft | published | archived
    title: Mapped[str] = mapped_column(String(300), default="")
    doc: Mapped[dict] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EncounterRow(Base):
    __tablename__ = "encounters"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(120), index=True)
    case_version: Mapped[int] = mapped_column(Integer)
    visit_id: Mapped[str] = mapped_column(String(60))
    student_name: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | ended | complete
    # Resolved visit snapshot (case + visit changes + branch from the previous visit).
    visit_doc: Mapped[dict] = mapped_column(JSONType)
    state: Mapped[dict] = mapped_column(JSONType)
    previous_encounter_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    documentation: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    feedback: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    feedback_overrides: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TurnRow(Base):
    __tablename__ = "turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    encounter_id: Mapped[str] = mapped_column(ForeignKey("encounters.id", ondelete="CASCADE"), index=True)
    idx: Mapped[int] = mapped_column(Integer)
    student_text: Mapped[str] = mapped_column(Text)
    student_start_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    student_end_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    intent: Mapped[dict] = mapped_column(JSONType)
    engine: Mapped[dict] = mapped_column(JSONType)
    reply_text: Mapped[str] = mapped_column(Text)
    cited_fact_ids: Mapped[list] = mapped_column(JSONType)
    verifier: Mapped[dict] = mapped_column(JSONType)
    audio_tags: Mapped[list] = mapped_column(JSONType)
    latency_ms: Mapped[dict] = mapped_column(JSONType)
    llm_calls: Mapped[list] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
