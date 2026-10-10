"""ElevenLabs speech (PRD E-02, E-03).

Speech-to-text runs in the browser against Scribe v2 Realtime. This module only
mints the single-use token and, when a key is configured, synthesizes speech.
The long-lived key never leaves the server.
"""
from __future__ import annotations

import logging
import re

import httpx

from app.settings import get_settings

log = logging.getLogger(__name__)
API = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
# Client-side Scribe uses this token type so the browser never sees the API key.
SCRIBE_TOKEN_URL = "https://api.elevenlabs.io/v1/single-use-token/realtime_scribe"
TAG_RE = re.compile(r"\[[a-z ]{2,30}\]\s*", re.IGNORECASE)


class MissingScribeConfig(Exception):
    """No API key is configured, so a single-use token cannot be issued."""


class ScribeTokenError(Exception):
    """ElevenLabs did not return a usable single-use token."""


def create_scribe_token() -> str:
    """Ask ElevenLabs for one realtime token. The API key stays in this process."""
    settings = get_settings()
    if not settings.elevenlabs_api_key:
        raise MissingScribeConfig("Speech transcription is not configured.")
    try:
        response = httpx.post(
            SCRIBE_TOKEN_URL,
            headers={"xi-api-key": settings.elevenlabs_api_key},
            timeout=10,
        )
        response.raise_for_status()
        token = response.json().get("token")
    except httpx.HTTPError as exc:
        # The warning names the failure, not the key.
        log.warning("Scribe token request failed: %s", exc)
        raise ScribeTokenError("The transcription service did not provide a token.") from exc
    if not isinstance(token, str) or not token or token == settings.elevenlabs_api_key:
        raise ScribeTokenError("The transcription service did not provide a token.")
    return token


def tts_available() -> bool:
    """True when a key and a voice id are both configured. The client uses this to pick a voice path."""
    s = get_settings()
    return bool(s.elevenlabs_api_key and s.elevenlabs_default_voice_id)


def prepare_text(text: str, audio_tags: list[str]) -> str:
    """Audio tags such as [sighs] are only sent to models that support them."""
    clean = TAG_RE.sub("", text).strip()
    if get_settings().elevenlabs_audio_tags and audio_tags:
        return " ".join(f"[{t}]" for t in audio_tags) + " " + clean
    return clean


def synthesize(text: str, voice_id: str | None = None, audio_tags: list[str] | None = None) -> bytes | None:
    """Return spoken audio, or None when the voice service is not configured or the request fails."""
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
