"""HTTP bodies around the case document.

FastAPI turns these models into the OpenAPI schema. The case document itself
stays in case.py so there is still one case format. Studio responses embed that
case rather than defining a second one.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.case import Case


class HealthResponse(BaseModel):
    """Liveness. True means this process can answer; it does not check the database."""

    ok: bool


class PublicConfig(BaseModel):
    """Voice settings the browser may see. The long-lived key is not a field on this object."""

    llm: bool
    tts: bool
    stt_provider: Literal["elevenlabs"]
    stt_model_id: str
    voice_id: str | None = None
    tts_model_id: str
    vad_silence_secs: float
    vad_threshold: float
    commit_strategy: Literal["vad"]
    include_timestamps: bool


class ScribeToken(BaseModel):
    """One single-use Scribe token. It expires at the provider and is not the API key."""

    token: str


class StudioCaseSummary(BaseModel):
    """One saved case as the Case Library lists it. Hidden facts stay out of this object."""

    case_id: str
    version: int
    status: Literal["draft", "published", "archived"]
    title: str
    golden: bool
    patient: str
    updated_at: str | None
    blockers: list[str] = Field(default_factory=list)


class IntakeGap(BaseModel):
    """One guided question still open. The list is what remains, not a history of answers."""

    id: str
    question: str
    kind: Literal["field", "facts", "objectives", "autofill"]
    blocking: bool


class LlmCallRecord(BaseModel):
    """One logged model call. Offline drafting and intake leave the list empty."""

    purpose: str
    model: str
    prompt: str
    prompt_version: str
    latency_ms: int
    ok: bool
    error: str | None = None


class StudioCaseDetail(BaseModel):
    """A saved case in the authoritative case format, with its remaining gaps and blockers."""

    case: Case
    status: Literal["draft", "published", "archived"]
    gaps: list[IntakeGap]
    blockers: list[str]


class StudioDraftResult(BaseModel):
    """Draft creation and intake. Same case view, plus any model calls used to produce it."""

    case: Case
    status: Literal["draft", "published", "archived"]
    gaps: list[IntakeGap]
    blockers: list[str]
    llm_calls: list[LlmCallRecord]


class VhsImportResponse(BaseModel):
    """Drafts saved from the bundled sponsor sample set. count is how many drafts were saved."""

    count: int
    cases: list[StudioCaseSummary]


class AutofillAdded(BaseModel):
    """Lab ids and vital keys this auto-fill run proposed. Faculty entries are not listed."""

    labs: list[str]
    vitals: list[str]


class StudioAutofillResult(BaseModel):
    """The saved case after auto-fill, plus the notes and which values were proposed."""

    case: Case
    status: Literal["draft", "published", "archived"]
    gaps: list[IntakeGap]
    blockers: list[str]
    added: AutofillAdded
    notes: list[str]


class Icd10Match(BaseModel):
    """One diagnosis from the existing lookup. code and display are what faculty store."""

    code: str
    display: str


class StudioVocabLabel(BaseModel):
    """A topic or action the editor can offer. The id is what a fact or objective stores."""

    id: str
    description: str


class StudioVocabManeuver(BaseModel):
    """An exam maneuver. normal is the catalog sentence, not a finding invented for this patient."""

    id: str
    label: str
    normal: str


class StudioVocab(BaseModel):
    """Closed lists for the studio. The values come from the vocab files and the lab catalog."""

    topics: list[StudioVocabLabel]
    actions: list[StudioVocabLabel]
    maneuvers: list[StudioVocabManeuver]
    lab_panels: list[str]


class ErrorItem(BaseModel):
    """One validation problem. loc is the same path FastAPI already reported, such as ["body", "description"]."""

    loc: list[str | int] = Field(default_factory=list)
    msg: str
    type: str | None = None


class ErrorResponse(BaseModel):
    """One error body for validation failures and application failures. The HTTP status stays on the response."""

    message: str
    errors: list[ErrorItem] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
