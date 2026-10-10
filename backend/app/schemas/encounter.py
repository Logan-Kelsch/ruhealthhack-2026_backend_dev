"""Shapes for one encounter turn: the classifier's intent tags and the engine's output."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Hit(BaseModel):
    """One label with the exact words that justify it. No span, no label."""

    id: str
    span: str
    confidence: Literal["high", "low"] = "high"


class JargonHit(BaseModel):
    term: str
    span: str
    explained: bool = False


class Intent(BaseModel):
    topics: list[Hit] = Field(default_factory=list)
    actions: list[Hit] = Field(default_factory=list)
    maneuvers: list[Hit] = Field(default_factory=list)
    orders: list[Hit] = Field(default_factory=list)  # id = lab panel key
    empathy: list[Hit] = Field(default_factory=list)  # id in {reflection, validation}
    jargon: list[JargonHit] = Field(default_factory=list)
    question_type: Literal["open", "closed", "statement"] = "statement"
    source: Literal["llm", "keywords"] = "keywords"

    def topic_ids(self) -> set[str]:
        return {h.id for h in self.topics}

    def action_ids(self) -> set[str]:
        return {h.id for h in self.actions}


class TrustEvent(BaseModel):
    event: str
    delta: int
    span: str
    turn: int
    note: str | None = None


class Disclosure(BaseModel):
    fact_id: str
    turn: int
    condition: str  # which rule released it, for example "topic:otc_medications"
    trust_at: int


class Withheld(BaseModel):
    fact_id: str
    reason: str  # for example "trust 1 < 2 (reluctant)"


class ChartRelease(BaseModel):
    kind: Literal["vital", "lab", "exam", "artifact", "diagnosis", "medication", "allergy", "fact"]
    ref: str
    label: str
    value: str | None = None
    flag: str | None = None
    section: str | None = None
    source_fact: str | None = None


class Notice(BaseModel):
    kind: Literal["exam_unavailable", "order_unavailable", "fallback", "info"]
    text: str


class EngineResult(BaseModel):
    allowed_fact_ids: list[str] = Field(default_factory=list)  # newly allowed this turn
    repeat_fact_ids: list[str] = Field(default_factory=list)  # asked again, already disclosed
    withheld: list[Withheld] = Field(default_factory=list)
    disclosures: list[Disclosure] = Field(default_factory=list)
    trust_events: list[TrustEvent] = Field(default_factory=list)
    trust_after: int = 0
    chart_releases: list[ChartRelease] = Field(default_factory=list)
    exam_results: list[ChartRelease] = Field(default_factory=list)
    notices: list[Notice] = Field(default_factory=list)
    is_repeat: bool = False
    deflect: bool = False
    exam_only: bool = False
    audio_tags: list[str] = Field(default_factory=list)
    mood: str = "neutral"
