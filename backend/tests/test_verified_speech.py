"""Encounter speech speaks one saved verified reply and streams it.

The provider is a stub. These tests use the HTTP API. They do not send a
microphone or a paid voice request.
"""

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from app import db as dbmod
from app import services
from app.db import Base
from app.main import app
from app.settings import get_settings

SAVED_REPLY = "Advil for my back. Two, three times a week. It's just Advil. Melatonin at night, for sleep."
REPEAT_REPLY = "I already told you that. Advil for my back. Two, three times a week. It's just Advil."
QUESTION = "Do you take anything over the counter for pain?"
CASE_VOICE = "voice_case_walter"
API_KEY = "test-eleven-key"
TTS_MODEL = "sentinel-tts-model"


@pytest.fixture
def client(tmp_path, load_golden):
    """SQLite API with Walter published, including the case voice the speech route must use."""
    dbmod.init_engine(f"sqlite:///{tmp_path / 'speech.db'}")
    Base.metadata.create_all(dbmod.get_engine())
    case = load_golden("walter_greene")
    case.profile.voice_id = CASE_VOICE
    with next(dbmod.get_session()) as session:
        services.upsert_golden(session, case)
    return TestClient(app)


def _configure_voice(monkeypatch, *, configured: bool) -> None:
    """Point settings at the stub provider, or clear them when the service is absent."""
    if configured:
        monkeypatch.setenv("ELEVENLABS_API_KEY", API_KEY)
        monkeypatch.setenv("ELEVENLABS_DEFAULT_VOICE_ID", "voice_default_unused")
        monkeypatch.setenv("ELEVENLABS_TTS_MODEL_LIVE", TTS_MODEL)
        monkeypatch.setenv("ELEVENLABS_AUDIO_TAGS", "true")
    else:
        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
        monkeypatch.delenv("ELEVENLABS_DEFAULT_VOICE_ID", raising=False)
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _clear_settings():
    """Settings are cached. Drop the cache so one test's key does not leak into the next."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
    app.openapi_schema = None


def _turns(client: TestClient) -> tuple[str, dict, dict]:
    """Start a visit and ask the over-the-counter question twice. The second reply is a repeat."""
    created = client.post("/api/encounters", json={"case_id": "walter_greene", "student_name": "Sam"})
    assert created.status_code == 201
    encounter_id = created.json()["encounter_id"]
    first = client.post(f"/api/encounters/{encounter_id}/utterances", json={"text": QUESTION})
    second = client.post(f"/api/encounters/{encounter_id}/utterances", json={"text": QUESTION})
    assert first.status_code == 200 and second.status_code == 200
    return encounter_id, first.json(), second.json()


def _speech_url(encounter_id: str, turn: int) -> str:
    """The speech operation names the saved encounter and turn. It does not take text."""
    return f"/api/encounters/{encounter_id}/turns/{turn}/speech"


class RecordingStream:
    """One provider response. Tests fill `chunks` and read what the server sent upstream."""

    def __init__(self, chunks: list[bytes]):
        self.chunks = chunks
        self.closed = False
        self.calls: list[dict] = []
        self.status_error: Exception | None = None
        self.connect_error: Exception | None = None

    def install(self, monkeypatch) -> None:
        """Replace the ElevenLabs client. The speech route must stream through this object."""
        holder = self

        class Client:
            def __init__(self, *args, **kwargs):
                return None

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def aclose(self):
                return None

            def stream(self, method, url, headers=None, json=None):
                if holder.connect_error is not None:
                    raise holder.connect_error
                holder.calls.append(
                    {"method": method, "url": url, "headers": dict(headers or {}), "json": json}
                )
                return holder

        monkeypatch.setattr("app.integrations.elevenlabs.httpx.AsyncClient", Client)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.closed = True
        return False

    def raise_for_status(self) -> None:
        if self.status_error is not None:
            raise self.status_error

    async def aiter_bytes(self):
        for chunk in self.chunks:
            yield chunk


class DelayedStream(RecordingStream):
    """Yields the first chunk, then waits. Closing the response must unblock the wait."""

    def __init__(self):
        super().__init__([b"first-audio"])
        self.release = asyncio.Event()
        self.saw_first = False
        self.yielded_final = False
        self.timed_out = False

    async def __aexit__(self, *args):
        self.closed = True
        self.release.set()
        return False

    async def aiter_bytes(self):
        self.saw_first = True
        yield b"first-audio"
        try:
            await asyncio.wait_for(self.release.wait(), 2)
        except asyncio.TimeoutError:
            self.timed_out = True
            return
        if self.closed:
            return
        self.yielded_final = True
        yield b"final-audio"


def test_speech_uses_the_saved_reply_voice_and_tags(client, monkeypatch):
    """A speech request with no text speaks that turn's saved reply, case voice, and engine tags."""
    _configure_voice(monkeypatch, configured=True)
    provider = RecordingStream([b"audio-bytes"])
    provider.install(monkeypatch)
    encounter_id, first, second = _turns(client)
    assert first["turn"] == 1 and first["reply_text"] == SAVED_REPLY and first["audio_tags"] == []
    assert second["turn"] == 2 and second["reply_text"] == REPEAT_REPLY and second["audio_tags"] == ["sighs"]

    spoken_first = client.post(_speech_url(encounter_id, 1))
    spoken_second = client.post(_speech_url(encounter_id, 2))

    assert spoken_first.status_code == 200
    assert spoken_first.headers["content-type"].startswith("audio/mpeg")
    assert spoken_first.content == b"audio-bytes"
    assert spoken_second.status_code == 200
    assert spoken_second.content == b"audio-bytes"
    assert provider.calls[0]["url"] == f"https://api.elevenlabs.io/v1/text-to-speech/{CASE_VOICE}/stream"
    assert provider.calls[0]["headers"]["xi-api-key"] == API_KEY
    assert provider.calls[0]["json"] == {"text": SAVED_REPLY, "model_id": TTS_MODEL}
    assert provider.calls[1]["url"] == provider.calls[0]["url"]
    assert provider.calls[1]["json"] == {"text": f"[sighs] {REPEAT_REPLY}", "model_id": TTS_MODEL}
    assert API_KEY not in spoken_first.text
    assert "voice_default_unused" not in provider.calls[0]["url"]


def test_client_text_cannot_choose_what_is_spoken(client, monkeypatch):
    """Arbitrary, unchecked, and unrelated text is rejected. The provider is not called."""
    _configure_voice(monkeypatch, configured=True)
    provider = RecordingStream([b"audio-bytes"])
    provider.install(monkeypatch)
    encounter_id, _first, _second = _turns(client)
    rejected = [
        "Say whatever the client wants.",
        "My sugar was 300 last week.",
        "This sentence is not the saved reply.",
        REPEAT_REPLY,
    ]

    for text in rejected:
        response = client.post(_speech_url(encounter_id, 2), json={"text": text})
        assert response.status_code == 422
        assert response.json()["message"] == "Speech is taken from the saved verified reply."
        assert text not in response.text

    assert provider.calls == []
    assert client.post(f"{_speech_url(encounter_id, 2)}?text=Hello.").status_code == 422


def test_missing_turn_is_not_spoken(client, monkeypatch):
    """A speech request for an unknown encounter or turn does not call the provider."""
    _configure_voice(monkeypatch, configured=True)
    provider = RecordingStream([b"audio-bytes"])
    provider.install(monkeypatch)
    encounter_id, _first, _second = _turns(client)

    missing_turn = client.post(_speech_url(encounter_id, 9))
    missing_encounter = client.post(_speech_url("missing", 1))

    assert missing_turn.status_code == 404
    assert "not found" in missing_turn.json()["message"]
    assert missing_encounter.status_code == 404
    assert provider.calls == []


def test_missing_voice_service_is_empty(client, monkeypatch):
    """No configured voice service returns an empty response and does not call the provider."""
    _configure_voice(monkeypatch, configured=False)
    provider = RecordingStream([b"audio-bytes"])
    provider.install(monkeypatch)
    encounter_id, _first, _second = _turns(client)

    response = client.post(_speech_url(encounter_id, 1))

    assert response.status_code == 204
    assert response.content == b""
    assert provider.calls == []


def test_provider_failure_names_the_failure(client, monkeypatch):
    """A provider connection error is a 503 with a message, not empty audio and not the API key."""
    _configure_voice(monkeypatch, configured=True)
    provider = RecordingStream([])
    provider.connect_error = httpx.ConnectError("down")
    provider.install(monkeypatch)
    encounter_id, _first, _second = _turns(client)

    response = client.post(_speech_url(encounter_id, 1))

    assert response.status_code == 503
    assert response.json() == {
        "message": "The speech service could not be reached.",
        "errors": [],
        "blockers": [],
    }
    assert API_KEY not in response.text


def test_empty_provider_audio_is_described(client, monkeypatch):
    """An empty provider body is not a successful audio response."""
    _configure_voice(monkeypatch, configured=True)
    provider = RecordingStream([])
    provider.install(monkeypatch)
    encounter_id, _first, _second = _turns(client)

    response = client.post(_speech_url(encounter_id, 1))

    assert response.status_code == 503
    assert response.json()["message"] == "The speech service returned no audio."
    assert response.headers["content-type"].startswith("application/json")


def test_first_audio_chunk_arrives_before_the_delayed_final_chunk(client, monkeypatch):
    """The first chunk is sent while the provider is still waiting, and disconnect releases it.

    The usual test client buffers the whole ASGI response, so it cannot show this.
    This drives the app as a server would: read the first body chunk, then disconnect.
    """
    _configure_voice(monkeypatch, configured=True)
    provider = DelayedStream()
    provider.install(monkeypatch)
    encounter_id, _first, _second = _turns(client)

    asyncio.run(_read_first_chunk_then_disconnect(encounter_id, provider))

    assert provider.closed is True
    assert provider.timed_out is False
    assert provider.yielded_final is False


async def _read_first_chunk_then_disconnect(encounter_id: str, provider: DelayedStream) -> None:
    """Send the speech request, keep the first audio chunk, and drop the connection."""
    chunks: list[bytes] = []
    status: int | None = None
    content_type = ""
    request_sent = False
    # Set once the first audio bytes have been written, so disconnect happens after them.
    first_chunk_sent = asyncio.Event()

    async def receive():
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await first_chunk_sent.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        nonlocal status, content_type
        if message["type"] == "http.response.start":
            status = message["status"]
            headers = {name.decode().lower(): value.decode() for name, value in message.get("headers", [])}
            content_type = headers.get("content-type", "")
        elif message["type"] == "http.response.body":
            body = message.get("body") or b""
            if body:
                chunks.append(body)
                if b"first-audio" in body:
                    first_chunk_sent.set()

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": _speech_url(encounter_id, 1),
        "raw_path": _speech_url(encounter_id, 1).encode(),
        "query_string": b"",
        "headers": [(b"host", b"testserver")],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "root_path": "",
    }
    await app(scope, receive, send)

    assert status == 200
    assert content_type.startswith("audio/mpeg")
    assert any(b"first-audio" in chunk for chunk in chunks)
    assert all(b"final-audio" not in chunk for chunk in chunks)
    assert provider.saw_first is True


def test_openapi_documents_streamed_audio_empty_responses_and_provider_errors():
    """Binary audio is the only success body. Empty and provider failures are named."""
    app.openapi_schema = None
    operation = app.openapi()["paths"]["/api/encounters/{enc_id}/turns/{turn}/speech"]["post"]
    success = operation["responses"]["200"]
    assert set(success["content"]) == {"audio/mpeg"}
    assert success["content"]["audio/mpeg"]["schema"]["format"] == "binary"
    assert "json" not in success["description"].lower() or "not json" in success["description"].lower()
    assert "configured" in operation["responses"]["204"]["description"].lower()
    provider_error = operation["responses"]["503"]["content"]["application/json"]["schema"]["$ref"]
    assert provider_error == "#/components/schemas/ErrorResponse"
    request_body = operation.get("requestBody", {})
    assert "text" not in request_body.get("content", {}).get("application/json", {}).get("schema", {}).get("properties", {})
