"""Single-use Scribe token and the public voice settings the browser is allowed to see.

These tests use the HTTP API. The ElevenLabs call is stubbed. Schema export must
not request a token or copy the long-lived key into the document.
"""

import json

import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.settings import get_settings


def test_voice_config_names_scribe_settings_and_hides_the_key(monkeypatch):
    """The browser learns the Scribe model, voice, and silence from config. The API key stays off the body."""
    monkeypatch.setenv("ELEVENLABS_API_KEY", "long-lived-eleven-key")
    monkeypatch.setenv("ELEVENLABS_STT_MODEL", "scribe_v2_realtime")
    monkeypatch.setenv("ELEVENLABS_DEFAULT_VOICE_ID", "voice_public_demo")
    monkeypatch.setenv("ELEVENLABS_TTS_MODEL_LIVE", "eleven_turbo_v2_5")
    monkeypatch.setenv("STT_VAD_SILENCE_SECS", "1.5")
    monkeypatch.setenv("STT_VAD_THRESHOLD", "0.4")
    get_settings.cache_clear()

    response = TestClient(app).get("/api/config")

    assert response.status_code == 200
    assert response.json() == {
        "llm": False,
        "tts": True,
        "stt_provider": "elevenlabs",
        "stt_model_id": "scribe_v2_realtime",
        "voice_id": "voice_public_demo",
        "tts_model_id": "eleven_turbo_v2_5",
        "vad_silence_secs": 1.5,
        "vad_threshold": 0.4,
        "commit_strategy": "vad",
        "include_timestamps": True,
    }
    assert "long-lived-eleven-key" not in response.text
    config = app.openapi()["components"]["schemas"]["PublicConfig"]
    assert "elevenlabs_api_key" not in config["properties"]
    assert config.get("additionalProperties") is not True


def test_scribe_token_is_single_use_and_hides_the_key(monkeypatch):
    """One token request reaches ElevenLabs with the server key and returns only the single-use token."""
    monkeypatch.setenv("ELEVENLABS_API_KEY", "long-lived-eleven-key")
    get_settings.cache_clear()
    calls: list[dict] = []

    def fake_post(url, headers=None, timeout=None, **kwargs):
        # The stub stands in for ElevenLabs. The assertion below checks the URL and the key header.
        calls.append({"url": url, "headers": headers or {}})

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {"token": "sutkn_one_use"}

        return Response()

    monkeypatch.setattr("app.integrations.elevenlabs.httpx.post", fake_post)
    response = TestClient(app).post("/api/stt/token")

    assert response.status_code == 200
    assert response.json() == {"token": "sutkn_one_use"}
    assert "long-lived-eleven-key" not in response.text
    assert calls == [
        {
            "url": "https://api.elevenlabs.io/v1/single-use-token/realtime_scribe",
            "headers": {"xi-api-key": "long-lived-eleven-key"},
        }
    ]
    token = app.openapi()["components"]["schemas"]["ScribeToken"]
    assert set(token["properties"]) == {"token"}
    assert token.get("additionalProperties") is not True


def test_missing_scribe_key_is_a_configuration_error(monkeypatch):
    """No long-lived key means no token, and the message says the service is not configured."""
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    get_settings.cache_clear()

    response = TestClient(app).post("/api/stt/token")

    assert response.status_code == 409
    assert response.json() == {
        "message": "Speech transcription is not configured.",
        "errors": [],
        "blockers": [],
    }


def test_scribe_provider_failure_uses_the_shared_error(monkeypatch):
    """A failed token request is a provider error, not an empty success and not the API key."""
    monkeypatch.setenv("ELEVENLABS_API_KEY", "long-lived-eleven-key")
    get_settings.cache_clear()

    def fake_post(url, headers=None, timeout=None, **kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setattr("app.integrations.elevenlabs.httpx.post", fake_post)
    response = TestClient(app).post("/api/stt/token")

    assert response.status_code == 503
    assert response.json()["message"] == "The transcription service did not provide a token."
    assert "long-lived-eleven-key" not in response.text


def test_openapi_does_not_request_a_scribe_token(monkeypatch):
    """Building the schema describes the token route and does not call ElevenLabs."""
    called = False

    def fail(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("schema export requested a token")

    monkeypatch.setattr("app.integrations.elevenlabs.create_scribe_token", fail)
    app.openapi_schema = None
    schema = app.openapi()

    assert called is False
    body = schema["paths"]["/api/stt/token"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert body["$ref"] == "#/components/schemas/ScribeToken"
    dumped = json.dumps(schema)
    assert "long-lived-eleven-key" not in dumped
    assert "xi-api-key" not in dumped
