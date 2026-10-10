"""ElevenLabs speech (PRD E-02, E-03, E-04).

Speech-to-text runs in the browser against Scribe v2 Realtime. This module
mints the single-use token and streams speech for a reply the encounter already
verified. The long-lived key never leaves the server.
"""
from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator, Awaitable, Callable

import httpx

from app.settings import get_settings

log = logging.getLogger(__name__)
API = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
STREAM_API = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
# Client-side Scribe uses this token type so the browser never sees the API key.
SCRIBE_TOKEN_URL = "https://api.elevenlabs.io/v1/single-use-token/realtime_scribe"
TAG_RE = re.compile(r"\[[a-z ]{2,30}\]\s*", re.IGNORECASE)


class MissingScribeConfig(Exception):
    """No API key is configured, so a single-use token cannot be issued."""


class ScribeTokenError(Exception):
    """ElevenLabs did not return a usable single-use token."""


class SpeechProviderError(Exception):
    """The speech vendor failed, or it returned no audio. The message is safe to show."""


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


class OpenedSpeech:
    """A vendor stream that has already produced its first audio chunk."""

    def __init__(self, first: bytes, iterator: AsyncIterator[bytes], close: Callable[[], Awaitable[None]]) -> None:
        self.first = first
        self._iterator = iterator
        self._close = close
        self._closed = False

    async def remaining(self) -> AsyncIterator[bytes]:
        """Yield chunks after the first. Playback can start before this finishes."""
        async for chunk in self._iterator:
            if chunk:
                yield chunk

    async def aclose(self) -> None:
        """Release the vendor connection. Safe to call when the client leaves early."""
        if self._closed:
            return
        self._closed = True
        await self._close()


async def _first_audio_chunk(iterator: AsyncIterator[bytes]) -> bytes:
    """Read until the first bytes, leaving later chunks on the same iterator."""
    while True:
        try:
            chunk = await anext(iterator)
        except StopAsyncIteration:
            return b""
        if chunk:
            return chunk


async def open_speech(text: str, voice_id: str, audio_tags: list[str]) -> OpenedSpeech:
    """Open a streaming synthesis call and return when the first audio chunk arrives.

    The text is the saved reply plus engine-selected tags. Cancelling the caller
    must still close this stream, which `OpenedSpeech.aclose` does.
    """
    settings = get_settings()
    client = httpx.AsyncClient(timeout=httpx.Timeout(20.0, read=None))
    try:
        opened = await _open_vendor_stream(client, settings.elevenlabs_api_key or "", voice_id, prepare_text(text, audio_tags), settings.elevenlabs_tts_model_live)
    except Exception:
        await client.aclose()
        raise
    return opened


async def _open_vendor_stream(client: httpx.AsyncClient, api_key: str, voice_id: str, spoken: str, model_id: str) -> OpenedSpeech:
    """Send one stream request. The client stays open until the returned stream is closed."""
    try:
        stream_cm = client.stream(
            "POST",
            STREAM_API.format(voice_id=voice_id),
            headers={"xi-api-key": api_key, "accept": "audio/mpeg"},
            json={"text": spoken, "model_id": model_id},
        )
        response = await stream_cm.__aenter__()
    except httpx.HTTPError as exc:
        log.warning("ElevenLabs speech stream failed: %s", exc)
        raise SpeechProviderError("The speech service could not be reached.") from exc

    try:
        response.raise_for_status()
        iterator = response.aiter_bytes()
        first = await _first_audio_chunk(iterator)
        if not first:
            raise SpeechProviderError("The speech service returned no audio.")
    except SpeechProviderError:
        await stream_cm.__aexit__(None, None, None)
        raise
    except httpx.HTTPError as exc:
        await stream_cm.__aexit__(None, None, None)
        log.warning("ElevenLabs speech stream failed: %s", exc)
        raise SpeechProviderError("The speech service could not be reached.") from exc

    async def close() -> None:
        # Closing the vendor response unblocks a read that is still waiting on a later chunk.
        await stream_cm.__aexit__(None, None, None)
        await client.aclose()

    return OpenedSpeech(first, iterator, close)


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
