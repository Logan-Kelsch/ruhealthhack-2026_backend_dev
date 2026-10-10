"""Student case, briefing, encounter, turn, and recovery contracts.

These tests use the HTTP API and the published golden cases. They check what a
student is allowed to see. They do not read engine state from the database.
"""

import re

import pytest
from fastapi.testclient import TestClient

from app import db as dbmod
from app import services
from app.db import Base
from app.main import app

# Keys that belong to faculty authoring or the disclosure engine. A student response
# must not use them, including inside nested objects.
HIDDEN_KEYS = {
    "trust",
    "trust_after",
    "trust_at",
    "trust_log",
    "trust_events",
    "withheld",
    "facts",
    "predicate",
    "decision_points",
    "branches",
    "unlock",
    "disclosed",
    "intent",
    "engine",
    "allowed_fact_ids",
    "min_trust",
    "thresholds",
    "changes",
}

# Spoken lines and chart values that exist only on hidden facts or unreleased branches.
HIDDEN_TEXT = (
    "Truth is, I'm scared. What happens to me when I can't do for myself?",
    "I switched to Tylenol like you said",
    "142/86",
    "Hospital discharge summary",
    "3+ pitting edema up to both knees",
)


@pytest.fixture
def client(tmp_path, load_golden):
    """SQLite API with the three published golden cases and no live model calls."""
    dbmod.init_engine(f"sqlite:///{tmp_path / 'student.db'}")
    Base.metadata.create_all(dbmod.get_engine())
    with next(dbmod.get_session()) as session:
        for case_id in ("walter_greene", "alina_reyes", "eli_brooks"):
            services.upsert_golden(session, load_golden(case_id))
    return TestClient(app)


def _hidden_keys(value: object) -> set[str]:
    """Collect forbidden key names anywhere in a JSON-like value."""
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in HIDDEN_KEYS:
                found.add(key)
            found.update(_hidden_keys(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_hidden_keys(item))
    return found


def _assert_student_safe(body: object) -> None:
    """A public response keeps withheld facts, trust, and unreleased branches private."""
    assert _hidden_keys(body) == set()
    text = str(body)
    for secret in HIDDEN_TEXT:
        assert secret not in text


def test_published_cases_are_public_briefings(client):
    """A student sees published cases and doorway facts, not the Studio case."""
    listed = client.get("/api/cases")
    assert listed.status_code == 200
    rows = listed.json()
    assert {row["case_id"] for row in rows} == {"walter_greene", "alina_reyes", "eli_brooks"}
    walter = next(row for row in rows if row["case_id"] == "walter_greene")
    assert walter["version"] == 1
    assert walter["title"] == "Walter Greene: diabetes, heart failure and a dinner club"
    assert walter["patient"]["name"] == "Walter Greene"
    assert walter["patient"]["age"] == 72
    assert walter["briefing"]["student_role"] == "Dietetics student (supervised practice)"
    assert walter["briefing"]["goal"].startswith("Take a nutrition-focused history")
    assert walter["visits"] == [
        {"id": "v1", "label": "First visit", "day": 0},
        {"id": "v2", "label": "Follow-up, 3 months later", "day": 90},
    ]
    blood_pressure = next(item for item in walter["doorway_vitals"] if item["key"] == "bp")
    assert blood_pressure["value"] == "158/92"
    assert blood_pressure["source"]["kind"] == "faculty"
    _assert_student_safe(rows)

    detail = client.get("/api/cases/walter_greene", params={"version": 1, "visit_id": "v1"})
    assert detail.status_code == 200
    assert detail.json()["briefing"]["setting"] == "Outpatient nutrition clinic"
    assert detail.json()["briefing"]["reason_for_visit"].startswith("Referral for medical nutrition therapy")
    _assert_student_safe(detail.json())

    follow_up = client.get("/api/cases/walter_greene", params={"visit_id": "v2"})
    assert follow_up.status_code == 200
    assert follow_up.json()["briefing"]["goal"] == "Review what changed since the first visit and adjust the plan."
    # Visit 2's own briefing is public. Branch vitals from visit 1 are not.
    assert follow_up.json()["doorway_vitals"]
    assert all(item["value"] != "142/86" for item in follow_up.json()["doorway_vitals"])
    _assert_student_safe(follow_up.json())

    missing = client.get("/api/cases/nobody")
    assert missing.status_code == 404
    assert missing.json()["message"] == "case nobody not found"
    assert missing.json()["blockers"] == []

    schema = app.openapi()["components"]["schemas"]["PublicCase"]
    assert schema.get("additionalProperties") is not True
    assert "facts" not in schema["properties"]
    body = app.openapi()["paths"]["/api/cases"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert body["items"]["$ref"] == "#/components/schemas/PublicCase"


def test_recovery_returns_the_same_encounter(client):
    """Refresh reads the saved encounter. It does not mint a new id or drop turns."""
    started = client.post(
        "/api/encounters",
        json={"case_id": "walter_greene", "version": 1, "visit_id": "v1", "student_name": "Sam"},
    )
    assert started.status_code == 201
    view = started.json()
    encounter_id = view["encounter_id"]
    assert view["status"] == "active"
    assert view["case_version"] == 1
    assert view["visit_id"] == "v1"
    assert view["visit_label"] == "First visit"
    assert view["previous_encounter_id"] is None
    assert view["transcript"] == []
    assert view["last_turn"] is None
    assert view["ended_at"] is None
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?", view["started_at"])
    referral = next(item for item in view["chart"] if item["ref"] == "referral")
    assert referral["body"].startswith("Medical nutrition therapy referral.")
    assert referral["source"]["kind"] == "faculty"
    blood_pressure = next(item for item in view["chart"] if item["ref"] == "bp")
    assert blood_pressure["value"].startswith("158/92")
    assert blood_pressure["source"]["kind"] == "faculty"
    _assert_student_safe(view)

    first = client.post(
        f"/api/encounters/{encounter_id}/utterances",
        json={"text": "Do you take anything over the counter for pain?", "start_ms": 1200, "end_ms": 4600},
    )
    assert first.status_code == 200
    assert first.json()["turn"] == 1
    assert first.json()["mode"] == "template"
    assert first.json()["speaker"] == "Walter Greene"
    released = next(item for item in first.json()["chart_releases"] if item["source_fact"] == "f_ibuprofen")
    assert "ibuprofen" in released["label"].lower()
    _assert_student_safe(first.json())

    second = client.post(
        f"/api/encounters/{encounter_id}/utterances",
        json={"text": "I'm going to listen to your lungs.", "start_ms": 5000, "end_ms": 7000},
    )
    assert second.status_code == 200
    assert second.json()["turn"] == 2
    finding = second.json()["exam_results"][0]
    assert finding["ref"] == "lung_auscultation"
    assert finding["value"] == "Fine crackles at both lung bases."
    assert finding["source"]["kind"] == "faculty"
    _assert_student_safe(second.json())

    active = client.get(f"/api/encounters/{encounter_id}")
    assert active.status_code == 200
    recovered = active.json()
    assert recovered["encounter_id"] == encounter_id
    assert recovered["status"] == "active"
    assert [line["turn"] for line in recovered["transcript"]] == [1, 2]
    assert recovered["transcript"][0]["student_start_ms"] == 1200
    assert recovered["transcript"][0]["student_end_ms"] == 4600
    assert recovered["transcript"][0]["is_last"] is False
    assert recovered["transcript"][1]["student_text"] == "I'm going to listen to your lungs."
    assert recovered["transcript"][1]["student_start_ms"] == 5000
    assert recovered["transcript"][1]["is_last"] is True
    assert recovered["last_turn"] == 2
    ibuprofen = next(item for item in recovered["chart"] if item["source_fact"] == "f_ibuprofen")
    assert "ibuprofen" in ibuprofen["label"].lower()
    lungs = next(item for item in recovered["chart"] if item["ref"] == "lung_auscultation")
    assert lungs["kind"] == "exam"
    assert lungs["value"] == "Fine crackles at both lung bases."
    assert lungs["source"]["kind"] == "faculty"
    _assert_student_safe(recovered)

    listed = client.get("/api/encounters", params={"case_id": "walter_greene"}).json()
    row = next(item for item in listed if item["encounter_id"] == encounter_id)
    assert row["status"] == "active"
    assert row["visit_id"] == "v1"
    assert row["student_name"] == "Sam"
    assert row["previous_encounter_id"] is None
    _assert_student_safe(listed)

    ended = client.post(f"/api/encounters/{encounter_id}/end")
    assert ended.status_code == 200
    assert ended.json()["encounter_id"] == encounter_id
    assert ended.json()["status"] == "ended"
    assert ended.json()["last_turn"] == 2
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?", ended.json()["ended_at"])
    ended_again = client.get(f"/api/encounters/{encounter_id}").json()
    assert ended_again["status"] == "ended"
    assert [line["turn"] for line in ended_again["transcript"]] == [1, 2]
    _assert_student_safe(ended_again)

    # Documentation is how an encounter becomes complete. The public view still hides the debrief.
    documented = client.post(
        f"/api/encounters/{encounter_id}/documentation",
        json={"fields": {"subjective": "Takes ibuprofen for back pain."}},
    )
    assert documented.status_code == 200
    complete = client.get(f"/api/encounters/{encounter_id}")
    assert complete.status_code == 200
    assert complete.json()["status"] == "complete"
    assert complete.json()["encounter_id"] == encounter_id
    assert [line["turn"] for line in complete.json()["transcript"]] == [1, 2]
    _assert_student_safe(complete.json())

    missing = client.get("/api/encounters/missing-encounter")
    assert missing.status_code == 404
    assert missing.json() == {
        "message": "encounter missing-encounter not found",
        "errors": [],
        "blockers": [],
    }

    follow_up = client.post("/api/encounters", json={"case_id": "walter_greene", "previous_encounter_id": encounter_id})
    assert follow_up.status_code == 201
    assert follow_up.json()["encounter_id"] != encounter_id
    assert follow_up.json()["previous_encounter_id"] == encounter_id
    assert follow_up.json()["visit_id"] == "v2"

    paths = app.openapi()["paths"]
    assert paths["/api/encounters"]["post"]["responses"]["201"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/PublicEncounter"
    assert paths["/api/encounters/{enc_id}"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/PublicEncounter"
    assert paths["/api/encounters"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["items"]["$ref"] == "#/components/schemas/EncounterSummary"
    assert paths["/api/encounters/{enc_id}/utterances"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/TurnResult"
    encounter_schema = app.openapi()["components"]["schemas"]["PublicEncounter"]
    assert {"transcript", "last_turn", "started_at", "ended_at", "previous_encounter_id"} <= set(encounter_schema["properties"])
    assert encounter_schema.get("additionalProperties") is not True


def test_committed_words_and_turn_times_are_saved(client):
    """A committed utterance keeps its word times and turn times, and the released fact stays cited."""
    started = client.post(
        "/api/encounters",
        json={"case_id": "walter_greene", "version": 1, "visit_id": "v1", "student_name": "Sam"},
    )
    encounter_id = started.json()["encounter_id"]
    words = [
        {"text": "Do", "start_ms": 1200, "end_ms": 1400},
        {"text": "you", "start_ms": 1500, "end_ms": 1700},
    ]
    sent = client.post(
        f"/api/encounters/{encounter_id}/utterances",
        json={
            "text": "Do you take anything over the counter for pain?",
            "start_ms": 1200,
            "end_ms": 4600,
            "words": words,
        },
    )
    assert sent.status_code == 200
    released = next(item for item in sent.json()["chart_releases"] if item["source_fact"] == "f_ibuprofen")
    assert "ibuprofen" in released["label"].lower()
    assert released["source"]["kind"] == "faculty"
    _assert_student_safe(sent.json())

    recovered = client.get(f"/api/encounters/{encounter_id}").json()
    line = recovered["transcript"][0]
    assert line["student_text"] == "Do you take anything over the counter for pain?"
    assert line["student_start_ms"] == 1200
    assert line["student_end_ms"] == 4600
    assert line["words"] == words
    _assert_student_safe(recovered)

    utterance = app.openapi()["components"]["schemas"]["Utterance"]
    assert "words" in utterance["properties"]
    transcript = app.openapi()["components"]["schemas"]["TranscriptEntry"]
    assert "words" in transcript["properties"]


def test_unavailable_order_does_not_invent_a_finding(client):
    """An order this case cannot release stays unavailable, and the offline reply is the template."""
    started = client.post(
        "/api/encounters",
        json={"case_id": "walter_greene", "version": 1, "visit_id": "v1", "student_name": "Sam"},
    )
    encounter_id = started.json()["encounter_id"]
    sent = client.post(
        f"/api/encounters/{encounter_id}/utterances",
        json={"text": "Can we order a troponin?"},
    )
    assert sent.status_code == 200
    body = sent.json()
    assert body["mode"] == "template"
    assert body["exam_results"] == []
    assert any(notice["kind"] == "order_unavailable" and "Troponin" in notice["text"] for notice in body["notices"])
    assert any(notice["kind"] == "fallback" and notice["text"] == "Simplified responses" for notice in body["notices"])
    assert not any(item.get("ref") == "troponin" or "troponin" in (item.get("label") or "").lower() for item in body["chart_releases"])
    _assert_student_safe(body)
