"""ElevenLabs text-to-speech (PRD E-02).

If no API key is configured, synthesize() returns None and the frontend speaks with the
browser's built-in voice instead. Speech-to-text is in the browser for V1; see
frontend/src/voice/speechInput.ts for the provider interface used to swap in ElevenLabs
Scribe or AWS Transcribe later.
"""
from __future__ import annotations

import logging
import re

import httpx

from app.settings import get_settings

log = logging.getLogger(__name__)
API = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
TAG_RE = re.compile(r"\[[a-z ]{2,30}\]\s*", re.IGNORECASE)


def tts_available() -> bool:
    s = get_settings()
    return bool(s.elevenlabs_api_key and s.elevenlabs_default_voice_id)


def prepare_text(text: str, audio_tags: list[str]) -> str:
    """Audio tags such as [sighs] are only sent to models that support them."""
    clean = TAG_RE.sub("", text).strip()
    if get_settings().elevenlabs_audio_tags and audio_tags:
        return " ".join(f"[{t}]" for t in audio_tags) + " " + clean
    return clean


def synthesize(text: str, voice_id: str | None = None, audio_tags: list[str] | None = None) -> bytes | None:
    s = get_settings()
    voice = voice_id or s.elevenlabs_default_voice_id
    if not s.elevenlabs_api_key or not voice:
        return None
    try:
        r = httpx.post(
            API.format(voice_id=voice),
            headers={"xi-api-key": s.elevenlabs_api_key, "accept": "audio/mpeg"},
            json={"text": prepare_text(text, audio_tags or []), "model_id": s.elevenlabs_tts_model_live},
            timeout=20,
        )
        r.raise_for_status()
        return r.content
    except httpx.HTTPError as exc:
        log.warning("ElevenLabs TTS failed, browser voice will be used: %s", exc)
        return None
