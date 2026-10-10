"""HTTP contracts for health, public configuration, and Studio case summaries.

These tests talk to the API through FastAPI's TestClient and the OpenAPI document.
They do not call private helpers.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db as dbmod
from app import services
from app.db import Base
from app.main import app


@pytest.fixture
def client(tmp_path, load_golden):
    """SQLite API client with the three golden cases already saved."""
    dbmod.init_engine(f"sqlite:///{tmp_path / 'contracts.db'}")
    Base.metadata.create_all(dbmod.get_engine())
    with next(dbmod.get_session()) as session:
        for case_id in ("walter_greene", "alina_reyes", "eli_brooks"):
            services.upsert_golden(session, load_golden(case_id))
    return TestClient(app)


def test_health_response_is_a_concrete_contract():
    """A liveness check returns ok, and the schema names that object."""
    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}

    health = app.openapi()["components"]["schemas"]["HealthResponse"]
    assert health["type"] == "object"
    assert health["properties"]["ok"]["type"] == "boolean"
    assert health.get("additionalProperties") is not True
    body = app.openapi()["paths"]["/api/health"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert body["$ref"] == "#/components/schemas/HealthResponse"


def test_public_config_names_voice_settings_and_hides_secrets():
    """The browser can see which voice path is on, and nothing that should stay on the server."""
    response = TestClient(app).get("/api/config")

    assert response.status_code == 200
    assert response.json() == {
        "llm": False,
        "tts": False,
        "stt_provider": "elevenlabs",
        "stt_model_id": "scribe_v2_realtime",
        "voice_id": None,
        "tts_model_id": "eleven_turbo_v2_5",
        "vad_silence_secs": 1.2,
        "vad_threshold": 0.4,
        "commit_strategy": "vad",
        "include_timestamps": True,
    }

    config = app.openapi()["components"]["schemas"]["PublicConfig"]
    assert set(config["properties"]) == {
        "llm",
        "tts",
        "stt_provider",
        "stt_model_id",
        "voice_id",
        "tts_model_id",
        "vad_silence_secs",
        "vad_threshold",
        "commit_strategy",
        "include_timestamps",
    }
    assert config.get("additionalProperties") is not True
    body = app.openapi()["paths"]["/api/config"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert body["$ref"] == "#/components/schemas/PublicConfig"


def test_studio_lists_saved_case_summaries(client):
    """Faculty see saved cases, including a real version, status, and the summary fields."""
    listed = client.get("/api/studio/cases")
    assert listed.status_code == 200
    rows = listed.json()
    walter = next(row for row in rows if row["case_id"] == "walter_greene")
    assert walter["version"] == 1
    assert walter["status"] == "published"
    assert walter["title"] == "Walter Greene: diabetes, heart failure and a dinner club"
    assert walter["patient"] == "Walter Greene"
    assert walter["golden"] is True
    assert walter["blockers"] == []
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?", walter["updated_at"])

    created = client.post(
        "/api/studio/drafts",
        json={"description": "A 58-year-old man with type 2 diabetes and high blood pressure."},
    )
    assert created.status_code == 201
    draft_id = created.json()["case"]["case_id"]
    again = client.get("/api/studio/cases").json()
    draft = next(row for row in again if row["case_id"] == draft_id)
    assert draft["status"] == "draft"
    assert draft["version"] == 1
    assert draft["title"] == "New case (draft)"
    assert draft["patient"] == "New patient"
    assert draft["golden"] is False
    assert "Missing: What is the patient's name?" in draft["blockers"]

    summary = app.openapi()["components"]["schemas"]["StudioCaseSummary"]
    assert set(summary["properties"]) == {
        "case_id",
        "version",
        "status",
        "title",
        "golden",
        "patient",
        "updated_at",
        "blockers",
    }
    assert summary.get("additionalProperties") is not True
    items = app.openapi()["paths"]["/api/studio/cases"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["items"]
    assert items["$ref"] == "#/components/schemas/StudioCaseSummary"


def test_validation_error_keeps_message_and_location(client):
    """A too-short draft description is still 422, and the field location stays visible."""
    response = client.post("/api/studio/drafts", json={"description": "short"})

    assert response.status_code == 422
    assert response.json() == {
        "message": "String should have at least 10 characters",
        "errors": [
            {
                "loc": ["body", "description"],
                "msg": "String should have at least 10 characters",
                "type": "string_too_short",
            }
        ],
        "blockers": [],
    }


def test_publish_blockers_stay_structured(client):
    """A case that is not ready still returns 409, with the blocker sentences kept as a list."""
    created = client.post(
        "/api/studio/drafts",
        json={"description": "A 58-year-old man with type 2 diabetes and high blood pressure."},
    )
    case_id = created.json()["case"]["case_id"]
    response = client.post(f"/api/studio/cases/{case_id}/publish")

    assert response.status_code == 409
    body = response.json()
    assert body["message"] == "This case is not ready to publish."
    assert body["errors"] == []
    assert "Missing: What is the patient's name?" in body["blockers"]
    assert all(isinstance(item, str) for item in body["blockers"])


def test_missing_case_uses_the_same_error_shape(client):
    """An unknown case stays 404, and the old message is the error message."""
    response = client.get("/api/studio/cases/nobody")

    assert response.status_code == 404
    assert response.json() == {
        "message": "case nobody not found",
        "errors": [],
        "blockers": [],
    }


def test_openapi_describes_the_shared_error_body():
    """Clients read one error schema for validation, a missing case, and publish blockers."""
    schema = app.openapi()
    assert set(schema["components"]["schemas"]["ErrorResponse"]["properties"]) == {"message", "errors", "blockers"}

    def error_ref(path: str, method: str, status: str) -> str:
        return schema["paths"][path][method]["responses"][status]["content"]["application/json"]["schema"]["$ref"]

    assert error_ref("/api/studio/drafts", "post", "422") == "#/components/schemas/ErrorResponse"
    assert error_ref("/api/studio/cases/{case_id}", "get", "404") == "#/components/schemas/ErrorResponse"
    assert error_ref("/api/studio/cases/{case_id}/publish", "post", "409") == "#/components/schemas/ErrorResponse"
    assert "HTTPValidationError" not in schema["components"]["schemas"]


def test_openapi_export_is_deterministic_and_omits_local_config(tmp_path):
    """Export writes the schema twice, identically, without a server, database, or secret."""
    backend = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.update(
        {
            "LLM_ENABLED": "false",
            "NLM_LOOKUP_ENABLED": "false",
            "ELEVENLABS_API_KEY": "sentinel-eleven-key",
            "AWS_SECRET_ACCESS_KEY": "sentinel-aws-secret",
            "AWS_ACCESS_KEY_ID": "sentinel-aws-id",
            "DATABASE_URL": "postgresql+psycopg://rounds:sentinel-db-password@127.0.0.1:1/rounds",
            "CORS_ORIGINS": "http://sentinel-cors.invalid",
            "BEDROCK_MODEL_FAST": "sentinel-model-fast",
            "BEDROCK_MODEL_STRONG": "sentinel-model-strong",
            "ELEVENLABS_STT_MODEL": "sentinel-stt-model",
            "ELEVENLABS_DEFAULT_VOICE_ID": "sentinel-voice-id",
            "ELEVENLABS_TTS_MODEL_LIVE": "sentinel-tts-model",
            "STT_VAD_SILENCE_SECS": "9.5",
            "STT_VAD_THRESHOLD": "0.25",
        }
    )
    first = tmp_path / "one.json"
    second = tmp_path / "two.json"
    for destination in (first, second):
        result = subprocess.run(
            [sys.executable, "-m", "scripts.export_openapi", str(destination)],
            cwd=backend,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    assert first.read_bytes() == second.read_bytes()
    text = first.read_text(encoding="utf-8")
    for secret in (
        "sentinel-eleven-key",
        "sentinel-aws-secret",
        "sentinel-aws-id",
        "sentinel-db-password",
        "sentinel-cors.invalid",
        "sentinel-model-fast",
        "sentinel-model-strong",
        "sentinel-stt-model",
        "sentinel-voice-id",
        "sentinel-tts-model",
    ):
        assert secret not in text
    schema = json.loads(text)
    names = schema["components"]["schemas"]
    assert "HealthResponse" in names
    assert "PublicConfig" in names
    assert "StudioCaseSummary" in names
    assert "ErrorResponse" in names


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a contract command and keep its output for the assertion message."""
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=120, check=False)


@pytest.mark.skipif(shutil.which("bun") is None, reason="needs bun")
def test_api_check_rejects_drift_without_rewriting_artifacts():
    """bun run api:check fails on a missing or stale artifact and leaves the tree alone."""
    repo = Path(__file__).resolve().parents[2]
    openapi = repo / "frontend" / "src" / "api" / "openapi.json"
    schema = repo / "frontend" / "src" / "api" / "schema.ts"
    openapi.parent.mkdir(parents=True, exist_ok=True)
    openapi.unlink(missing_ok=True)
    schema.unlink(missing_ok=True)
    good_openapi: bytes | None = None
    good_schema: bytes | None = None

    try:
        missing = _run(["bun", "run", "api:check"], repo)
        assert missing.returncode != 0, missing.stdout + missing.stderr
        assert not openapi.exists()
        assert not schema.exists()

        generated = _run(["bun", "run", "api:generate"], repo)
        assert generated.returncode == 0, generated.stdout + generated.stderr
        good_openapi = openapi.read_bytes()
        good_schema = schema.read_bytes()

        again = _run(["bun", "run", "api:generate"], repo)
        assert again.returncode == 0, again.stdout + again.stderr
        assert openapi.read_bytes() == good_openapi
        assert schema.read_bytes() == good_schema

        fresh = _run(["bun", "run", "api:check"], repo)
        assert fresh.returncode == 0, fresh.stdout + fresh.stderr
        assert openapi.read_bytes() == good_openapi
        assert schema.read_bytes() == good_schema

        openapi.write_bytes(good_openapi + b"\n ")
        stale_schema = _run(["bun", "run", "api:check"], repo)
        assert stale_schema.returncode != 0, stale_schema.stdout + stale_schema.stderr
        assert openapi.read_bytes() == good_openapi + b"\n "
        openapi.write_bytes(good_openapi)

        schema.write_bytes(good_schema + b"\nexport type ContractDrift = true;\n")
        drifted = schema.read_bytes()
        stale_types = _run(["bun", "run", "api:check"], repo)
        assert stale_types.returncode != 0, stale_types.stdout + stale_types.stderr
        assert schema.read_bytes() == drifted
        schema.write_bytes(good_schema)

        openapi.unlink()
        removed = _run(["bun", "run", "api:check"], repo)
        assert removed.returncode != 0, removed.stdout + removed.stderr
        assert not openapi.exists()
        assert schema.read_bytes() == good_schema
        openapi.write_bytes(good_openapi)
    finally:
        # A failed check must not be the thing that puts the good artifacts back.
        if good_openapi is not None:
            openapi.write_bytes(good_openapi)
        if good_schema is not None:
            schema.write_bytes(good_schema)
