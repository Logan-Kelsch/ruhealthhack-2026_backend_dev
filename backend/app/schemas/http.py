"""HTTP bodies that are not the case document.

FastAPI turns these models into the OpenAPI schema. The case document itself
stays in case.py so there is still one case format.
"""

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness. True means this process can answer; it does not check the database."""

    ok: bool


class PublicConfig(BaseModel):
    """Voice settings the browser may see. Model ids, keys, and account values stay off this object."""

    llm: bool
    tts: bool
    stt_provider: str
    stt_commit_silence_ms: int


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


class VhsImportResponse(BaseModel):
    """Drafts saved from the bundled sponsor sample set. count is how many drafts were saved."""

    count: int
    cases: list[StudioCaseSummary]


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
