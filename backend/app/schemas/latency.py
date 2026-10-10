"""Timing samples a developer can save for one turn.

These fields are how a report tells transcription, inference, synthesis, and playback
apart. A missing mark stays null. First audio bytes are not a playback time.
"""

from typing import Literal

from pydantic import BaseModel, Field


class TurnTimingCapture(BaseModel):
    """Offsets in milliseconds from the committed utterance. Omit a mark that was not observed."""

    verified_reply_arrival_ms: int | None = None
    speech_request_ms: int | None = None
    first_audio_bytes_ms: int | None = None
    first_playback_ms: int | None = None
    # live is a real encounter clock. fixture is a controlled clock, not vendor performance.
    origin: Literal["live", "fixture"]
    error: str | None = None
    speech_path: Literal["vendor", "browser", "none"] | None = None


class TurnTimingSample(BaseModel):
    """The saved sample. pipeline_ms is the existing per-step breakdown, unchanged."""

    encounter_id: str
    turn_id: int
    verified_reply_arrival_ms: int | None = None
    speech_request_ms: int | None = None
    first_audio_bytes_ms: int | None = None
    first_playback_ms: int | None = None
    pipeline_ms: dict[str, int] = Field(default_factory=dict)
    retries: int = 0
    fallback: bool = False
    fallback_kinds: list[Literal["template", "browser_voice"]] = Field(default_factory=list)
    error: str | None = None
    speech_path: Literal["vendor", "browser", "none"] | None = None
    unavailable: list[str] = Field(default_factory=list)
    origin: Literal["live", "fixture"]
