"""Student-facing HTTP bodies.

These models are the contract for briefing and encounter recovery. They list
the fields a student may see. Hidden facts, trust, and branch rules stay in
the case document and are not fields here.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.case import SourceKind


class PublicSource(BaseModel):
    """Where a released value came from, so the chart can show its citation."""

    kind: SourceKind
    ref: str | None = None


class PublicPatient(BaseModel):
    """The person on the briefing card. Faculty notes and voice settings are not included."""

    name: str
    age: int
    sex: Literal["male", "female", "other"]
    pronouns: str | None = None
    portrait: str | None = None
    speaker: str | None = None


class PublicBriefing(BaseModel):
    """What the student reads before starting. This is the doorway card, not the chart."""

    setting: str = ""
    reason_for_visit: str = ""
    goal: str = ""
    student_role: str = ""
    show_doorway_vitals: bool = True


class PublicVisitSummary(BaseModel):
    """A visit the student can choose. Decision points and branch changes are not on it."""

    id: str
    label: str
    day: int


class PublicDoorwayVital(BaseModel):
    """A vital shown before the visit starts, with the source faculty recorded."""

    key: str
    label: str
    value: str
    unit: str = ""
    source: PublicSource


class PublicCase(BaseModel):
    """One published case as a student lists or opens it."""

    case_id: str
    version: int
    title: str
    golden: bool
    patient: PublicPatient
    briefing: PublicBriefing
    visits: list[PublicVisitSummary]
    doorway_vitals: list[PublicDoorwayVital] = Field(default_factory=list)


class PublicChartEntry(BaseModel):
    """One released chart or exam row. source_fact cites the fact that released it, when one did."""

    kind: Literal["vital", "lab", "exam", "artifact", "diagnosis", "medication", "allergy", "fact"]
    ref: str
    label: str
    value: str | None = None
    flag: str | None = None
    section: str | None = None
    source_fact: str | None = None
    source: PublicSource | None = None
    # Document text for a released artifact. Unreleased notes are never copied here.
    body: str | None = None


class WordTimestamp(BaseModel):
    """One recognized word and when it was spoken. Times are milliseconds from the start of capture."""

    text: str
    start_ms: int
    end_ms: int


class TranscriptEntry(BaseModel):
    """One saved exchange. is_last marks the newest turn so refresh can show where the visit stopped."""

    turn: int
    student_text: str
    reply_text: str
    student_start_ms: int | None = None
    student_end_ms: int | None = None
    words: list[WordTimestamp] = Field(default_factory=list)
    # template means the reply used the approved phrasing because the model path did not pass.
    mode: Literal["template", "llm"] = "template"
    is_last: bool = False


class PublicEncounter(BaseModel):
    """The encounter a refresh restores. Trust and engine state are not fields on this object."""

    encounter_id: str
    status: Literal["active", "ended", "complete"]
    case_id: str
    case_version: int
    visit_id: str
    visit_label: str
    has_next_visit: bool
    previous_encounter_id: str | None = None
    patient: PublicPatient
    briefing: PublicBriefing
    chart: list[PublicChartEntry] = Field(default_factory=list)
    transcript: list[TranscriptEntry] = Field(default_factory=list)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    last_turn: int | None = None


class EncounterSummary(BaseModel):
    """One saved encounter in a list. The transcript stays on the encounter view."""

    encounter_id: str
    case_id: str
    visit_id: str
    student_name: str
    status: Literal["active", "ended", "complete"]
    started_at: datetime | None = None
    rubric_total: int | None = None
    review_flag: bool = False
    previous_encounter_id: str | None = None


class PublicNotice(BaseModel):
    """A short note the student can read, such as an exam that this case does not include."""

    kind: Literal["exam_unavailable", "order_unavailable", "fallback", "info"]
    text: str


class TurnResult(BaseModel):
    """The verified reply and the chart rows that turn released. The engine log stays stored."""

    turn: int
    reply_text: str
    speaker: str
    audio_tags: list[str] = Field(default_factory=list)
    chart_releases: list[PublicChartEntry] = Field(default_factory=list)
    exam_results: list[PublicChartEntry] = Field(default_factory=list)
    notices: list[PublicNotice] = Field(default_factory=list)
    mode: Literal["template", "llm"]
    latency_ms: dict[str, int] = Field(default_factory=dict)
