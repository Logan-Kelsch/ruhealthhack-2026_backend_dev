"""Saved encounter timings and the latency report.

The clock in these tests is a fixture. They do not call a voice vendor or use a microphone.
"""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from scripts.report_latency import main as report_latency

from app import db as dbmod
from app import services
from app.db import Base
from app.main import app

QUESTION = "Do you take anything over the counter for pain?"


def _client(tmp_path, load_golden) -> TestClient:
    """SQLite API with Walter published. The pipeline stays on the offline template path."""
    dbmod.init_engine(f"sqlite:///{tmp_path / 'latency.db'}")
    Base.metadata.create_all(dbmod.get_engine())
    with next(dbmod.get_session()) as session:
        services.upsert_golden(session, load_golden("walter_greene"))
    return TestClient(app)


def test_saved_turn_keeps_reply_playback_and_audio_marks_apart(tmp_path, load_golden):
    """Commit-to-reply and commit-to-playback stay distinct from the speech request and the first audio bytes."""
    client = _client(tmp_path, load_golden)
    created = client.post("/api/encounters", json={"case_id": "walter_greene", "student_name": "Sam"})
    assert created.status_code == 201
    encounter_id = created.json()["encounter_id"]
    turn = client.post(f"/api/encounters/{encounter_id}/utterances", json={"text": QUESTION})
    assert turn.status_code == 200
    body = turn.json()
    # The reply still carries the existing per-step durations. This capture must not replace them.
    assert set(body["latency_ms"]) >= {"classify", "disclosure", "total"}
    assert "phrase_1" not in body["latency_ms"]

    saved = client.post(
        f"/api/encounters/{encounter_id}/turns/{body['turn']}/timings",
        json={
            "verified_reply_arrival_ms": 400,
            "speech_request_ms": 450,
            "first_audio_bytes_ms": 620,
            "first_playback_ms": 700,
            "origin": "fixture",
            "speech_path": "vendor",
        },
    )
    assert saved.status_code == 200
    sample = saved.json()
    assert sample["encounter_id"] == encounter_id
    assert sample["turn_id"] == body["turn"]
    # These four numbers are the fixture clock, not one duration copied into every field.
    assert sample["verified_reply_arrival_ms"] == 400
    assert sample["speech_request_ms"] == 450
    assert sample["first_audio_bytes_ms"] == 620
    assert sample["first_playback_ms"] == 700
    assert sample["pipeline_ms"] == body["latency_ms"]
    assert sample["origin"] == "fixture"

    again = client.get(f"/api/encounters/{encounter_id}/turns/{body['turn']}/timings")
    assert again.status_code == 200
    assert again.json()["encounter_id"] == encounter_id
    assert again.json()["turn_id"] == body["turn"]
    assert again.json()["first_playback_ms"] == 700
    assert again.json()["first_audio_bytes_ms"] == 620


def test_first_audio_bytes_are_not_stored_as_first_playback(tmp_path, load_golden):
    """A turn that received audio but never started playback keeps playback missing."""
    client = _client(tmp_path, load_golden)
    created = client.post("/api/encounters", json={"case_id": "walter_greene", "student_name": "Sam"})
    encounter_id = created.json()["encounter_id"]
    turn = client.post(f"/api/encounters/{encounter_id}/utterances", json={"text": QUESTION}).json()

    missing = client.get(f"/api/encounters/{encounter_id}/turns/{turn['turn']}/timings")
    assert missing.status_code == 404

    saved = client.post(
        f"/api/encounters/{encounter_id}/turns/{turn['turn']}/timings",
        json={
            "verified_reply_arrival_ms": 400,
            "speech_request_ms": 450,
            "first_audio_bytes_ms": 620,
            "origin": "fixture",
            "speech_path": "vendor",
            "error": "The reply could not be played.",
        },
    )
    assert saved.status_code == 200
    sample = saved.json()
    assert sample["first_audio_bytes_ms"] == 620
    assert sample["first_playback_ms"] is None
    assert sample["error"] == "The reply could not be played."
    assert sample["unavailable"] == ["first_playback_ms"]
    # Offline replies use the template. That is a fallback, and there was no blocked retry.
    assert sample["fallback"] is True
    assert sample["fallback_kinds"] == ["template"]
    assert sample["retries"] == 0
    assert sample["pipeline_ms"] == turn["latency_ms"]


def test_incomparable_marks_stay_missing(tmp_path, load_golden):
    """An impossible order is not repaired, and a negative offset is not stored."""
    client = _client(tmp_path, load_golden)
    created = client.post("/api/encounters", json={"case_id": "walter_greene", "student_name": "Sam"})
    encounter_id = created.json()["encounter_id"]
    turn = client.post(f"/api/encounters/{encounter_id}/utterances", json={"text": QUESTION}).json()
    saved = client.post(
        f"/api/encounters/{encounter_id}/turns/{turn['turn']}/timings",
        json={
            # Bytes before the request, and playback before the reply, cannot be one clock.
            "verified_reply_arrival_ms": 400,
            "speech_request_ms": 500,
            "first_audio_bytes_ms": 100,
            "first_playback_ms": -5,
            "origin": "fixture",
            "speech_path": "browser",
        },
    )
    sample = saved.json()
    assert sample["verified_reply_arrival_ms"] == 400
    assert sample["speech_request_ms"] is None
    assert sample["first_audio_bytes_ms"] is None
    assert sample["first_playback_ms"] is None
    assert sample["unavailable"] == ["speech_request_ms", "first_audio_bytes_ms", "first_playback_ms"]
    assert sample["fallback"] is True
    assert sample["fallback_kinds"] == ["template", "browser_voice"]


def test_latency_report_names_gaps_and_does_not_claim_the_target(tmp_path):
    """The summary keeps missing clocks missing and does not treat a fixture as live performance."""
    source = Path(__file__).resolve().parents[1] / "scripts" / "fixtures" / "latency_samples.json"
    output = tmp_path / "latency.json"
    report_latency(["--samples", str(source), "--output", str(output)])
    report = json.loads(output.read_text(encoding="utf-8"))

    assert [(row["encounter_id"], row["turn_id"]) for row in report["samples"]] == [
        ("enc-ok", 1),
        ("enc-partial", 2),
        ("enc-fallback", 1),
        ("enc-skew", 4),
        ("enc-live", 1),
    ]
    # The partial turn kept the byte time and did not invent a playback time from it.
    partial = report["samples"][1]
    assert partial["first_audio_bytes_ms"] == 800
    assert partial["first_playback_ms"] is None
    # Bytes before the request, and playback before the reply, stay missing.
    skew = report["samples"][3]
    assert skew["verified_reply_arrival_ms"] is None
    assert skew["speech_request_ms"] is None
    assert skew["first_audio_bytes_ms"] is None
    assert skew["first_playback_ms"] is None

    assert report["counts"] == {"samples": 5, "live": 1, "fixture": 4}
    assert report["retries"] == [{"encounter_id": "enc-partial", "turn_id": 2, "retries": 1}]
    assert report["fallbacks"] == [
        {"encounter_id": "enc-fallback", "turn_id": 1, "fallback_kinds": ["template", "browser_voice"]}
    ]
    assert report["errors"] == [
        {"encounter_id": "enc-partial", "turn_id": 2, "error": "The reply could not be played."}
    ]

    fixture = report["by_origin"]["fixture"]
    live = report["by_origin"]["live"]
    # 700 and 900 only. The missing playback and the skewed 80 are not in this median.
    assert fixture["first_playback_ms"] == {"count": 2, "median": 800, "p90": 900}
    assert fixture["first_audio_bytes_ms"] == {"count": 2, "median": 710, "p90": 800}
    assert fixture["speech_request_ms"] == {"count": 2, "median": 505, "p90": 560}
    assert fixture["verified_reply_arrival_ms"] == {"count": 3, "median": 400, "p90": 500}
    assert fixture["unavailable"] == {
        "verified_reply_arrival_ms": 1,
        "speech_request_ms": 2,
        "first_audio_bytes_ms": 2,
        "first_playback_ms": 2,
    }
    assert fixture["pipeline_ms"]["classify"] == {"count": 4, "median": 25, "p90": 40}
    assert fixture["pipeline_ms"]["phrase_1"] is None
    assert fixture["pipeline_ms"]["verify_1"] is None
    # The live clock is not folded into the fixture median, and its missing playback stays missing.
    assert live["samples"] == 1
    assert live["first_playback_ms"] is None
    assert live["pipeline_ms"]["classify"] == {"count": 1, "median": 100, "p90": 100}
    assert live["unavailable"]["first_playback_ms"] == 1

    # 800 ms is under the 2 second goal. The report still must not say the goal was met.
    assert fixture["first_playback_ms"]["median"] == 800
    assert report["commit_to_first_audio_goal_ms"] == 2000
    assert report["target_claimed_met"] is False
    assert report["http_versus_websocket_ms"] is None
    assert report["limitations"] == [
        "Samples marked fixture use a controlled clock. They are not live vendor performance.",
        "The median commit-to-first-audio target is a measured goal. This report does not claim it is met.",
        "No HTTP-versus-WebSocket delay was measured.",
        "The live sample has no commit-to-first-playback measurement, so live vendor performance is not shown.",
    ]
    websocket_keys = [key for key in _keys(report) if "websocket" in key]
    assert websocket_keys == ["http_versus_websocket_ms"]


def _keys(value: object) -> list[str]:
    """Every object key in the report, so an invented delay cannot hide under another name."""
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            found.append(str(key))
            found.extend(_keys(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_keys(item))
    return found
