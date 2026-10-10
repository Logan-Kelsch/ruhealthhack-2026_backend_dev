"""Faculty review and score overrides through the HTTP API.

These tests use saved encounters. Expected scores and names come from the
golden case and the official rubric, not from recomputing the scorer.
"""

from fastapi.testclient import TestClient

from app import db as dbmod
from app import services
from app.db import Base
from app.main import app

# The sentence in the official rubric file. A shorter discussion-aid clause sits inside it.
DISCUSSION_AID = (
    "Use the total as a discussion aid, not a pass/fail grade. "
    "A score of 1 in professionalism, safety, or clinical reasoning should trigger review even when the total is high."
)


def _client(tmp_path, load_golden) -> TestClient:
    """SQLite API with the published golden cases and no live model calls."""
    dbmod.init_engine(f"sqlite:///{tmp_path / 'review.db'}")
    Base.metadata.create_all(dbmod.get_engine())
    with next(dbmod.get_session()) as session:
        for case_id in ("walter_greene", "alina_reyes", "eli_brooks"):
            services.upsert_golden(session, load_golden(case_id))
    return TestClient(app)


def _domain(body: dict, key: str) -> dict:
    """The generated domain row. Overrides are a sibling, not a replacement of this row."""
    return next(domain for domain in body["rubric"]["domains"] if domain["key"] == key)


def _complete(client: TestClient, case_id: str, student_name: str) -> str:
    """Speak one line, end, and submit a note so the encounter has saved feedback."""
    started = client.post("/api/encounters", json={"case_id": case_id, "student_name": student_name})
    assert started.status_code == 201
    encounter_id = started.json()["encounter_id"]
    spoken = client.post(
        f"/api/encounters/{encounter_id}/utterances",
        json={"text": "Do you take anything over the counter for pain?"},
    )
    assert spoken.status_code == 200
    assert client.post(f"/api/encounters/{encounter_id}/end").status_code == 200
    documented = client.post(
        f"/api/encounters/{encounter_id}/documentation",
        json={"fields": {"problem": "Asked about pain medicine.", "etiology": "", "signs": ""}},
    )
    assert documented.status_code == 200
    return encounter_id


def test_a_faculty_score_stays_beside_the_generated_score(tmp_path, load_golden):
    """N/A is a supported score, and refresh still shows the generated 1 next to it."""
    client = _client(tmp_path, load_golden)
    encounter_id = _complete(client, "walter_greene", "Sam")
    before = client.get(f"/api/encounters/{encounter_id}/feedback")
    assert before.status_code == 200
    generated = _domain(before.json(), "professionalism_safety_closure")
    assert generated["score"] == 1
    assert generated["evidence"]
    assert before.json()["rubric"]["max_total"] == 28
    assert before.json()["rubric"]["interpretation"] == DISCUSSION_AID
    assert before.json()["overrides"] is None

    saved = client.patch(
        f"/api/encounters/{encounter_id}/feedback",
        json={"scores": [{"domain": "professionalism_safety_closure", "score": "N/A"}]},
    )
    assert saved.status_code == 200
    body = saved.json()
    assert _domain(body, "professionalism_safety_closure")["score"] == 1
    assert _domain(body, "professionalism_safety_closure")["evidence"] == generated["evidence"]
    assert body["overrides"]["scores"] == [{"domain": "professionalism_safety_closure", "score": "N/A"}]
    assert body["rubric"]["review_flag"] is True

    refreshed = client.get(f"/api/encounters/{encounter_id}/feedback")
    assert refreshed.status_code == 200
    again = refreshed.json()
    assert _domain(again, "professionalism_safety_closure")["score"] == 1
    assert again["overrides"]["scores"] == [{"domain": "professionalism_safety_closure", "score": "N/A"}]
    assert again["rubric"]["total"] == before.json()["rubric"]["total"]
    assert again["rubric"]["interpretation"] == DISCUSSION_AID


def _patch(client: TestClient, encounter_id: str, body: dict):
    """Send one override. Callers assert the status themselves."""
    return client.patch(f"/api/encounters/{encounter_id}/feedback", json=body)


def test_invalid_override_fields_are_rejected_and_the_saved_change_stays(tmp_path, load_golden):
    """A bad domain, score, or field is a 422, and the earlier faculty score is still there."""
    client = _client(tmp_path, load_golden)
    encounter_id = _complete(client, "walter_greene", "Sam")
    kept = {"scores": [{"domain": "professionalism_safety_closure", "score": 3}]}
    assert _patch(client, encounter_id, kept).status_code == 200

    rejected = [
        {"scores": [{"domain": "bedside_manner", "score": 4}]},
        {"scores": [{"domain": "professionalism_safety_closure", "score": 5}]},
        {"scores": [{"domain": "professionalism_safety_closure", "score": "na"}]},
        {"scores": [{"domain": "opening_and_purpose", "score": 4, "note": "raised"}], "comments": []},
        {"comments": [{"domain": "opening_and_purpose", "field": "grade", "text": "Better"}]},
        {"cohort_average": 1.8},
        {},
    ]
    for body in rejected:
        failed = _patch(client, encounter_id, body)
        assert failed.status_code == 422, body
        assert failed.json()["errors"]

    refreshed = client.get(f"/api/encounters/{encounter_id}/feedback").json()
    assert _domain(refreshed, "professionalism_safety_closure")["score"] == 1
    assert refreshed["overrides"]["scores"] == [{"domain": "professionalism_safety_closure", "score": 3}]
    assert refreshed["overrides"]["comments"] == []


def test_a_faculty_comment_stays_beside_the_generated_comment(tmp_path, load_golden):
    """The generated safety comment remains, and a later score change does not drop the faculty comment."""
    client = _client(tmp_path, load_golden)
    encounter_id = _complete(client, "walter_greene", "Sam")
    before = client.get(f"/api/encounters/{encounter_id}/feedback").json()
    generated = _domain(before, "professionalism_safety_closure")["safety_or_accuracy_concern"]
    faculty_note = "Faculty note: ask about the unsafe pain medicine before the visit ends."

    commented = _patch(
        client,
        encounter_id,
        {
            "comments": [
                {
                    "domain": "professionalism_safety_closure",
                    "field": "safety_or_accuracy_concern",
                    "text": faculty_note,
                }
            ]
        },
    )
    assert commented.status_code == 200
    assert _domain(commented.json(), "professionalism_safety_closure")["safety_or_accuracy_concern"] == generated
    assert commented.json()["overrides"]["comments"] == [
        {
            "domain": "professionalism_safety_closure",
            "field": "safety_or_accuracy_concern",
            "text": faculty_note,
        }
    ]

    rescored = _patch(
        client,
        encounter_id,
        {"scores": [{"domain": "opening_and_purpose", "score": 4}]},
    )
    assert rescored.status_code == 200
    refreshed = client.get(f"/api/encounters/{encounter_id}/feedback").json()
    assert _domain(refreshed, "professionalism_safety_closure")["safety_or_accuracy_concern"] == generated
    assert refreshed["overrides"]["comments"][0]["text"] == faculty_note
    assert {"domain": "opening_and_purpose", "score": 4} in refreshed["overrides"]["scores"]


def test_review_entries_come_from_saved_encounters_and_the_limit_is_visible(tmp_path, load_golden):
    """Completion, review flags, and a student's history come from saved rows. A short limit does not hide the total."""
    client = _client(tmp_path, load_golden)
    complete_id = _complete(client, "walter_greene", "Sam")
    started = client.post("/api/encounters", json={"case_id": "alina_reyes", "student_name": "Riley"})
    assert started.status_code == 201
    active_id = started.json()["encounter_id"]
    feedback = client.get(f"/api/encounters/{complete_id}/feedback").json()

    listed = client.get("/api/encounters")
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 2
    assert body["limit"] == 200
    by_id = {row["encounter_id"]: row for row in body["encounters"]}
    sam = by_id[complete_id]
    assert sam["status"] == "complete"
    assert sam["student_name"] == "Sam"
    assert sam["case_id"] == "walter_greene"
    assert sam["review_flag"] is feedback["rubric"]["review_flag"]
    assert sam["review_flag"] is True
    assert sam["rubric_total"] == feedback["rubric"]["total"]
    assert sam["patient_name"] == "Walter Greene"
    assert sam["case_title"] == "Walter Greene: diabetes, heart failure and a dinner club"
    assert sam["visit_label"] == "First visit"
    riley = by_id[active_id]
    assert riley["status"] == "active"
    assert riley["student_name"] == "Riley"
    assert riley["review_flag"] is False
    assert riley["rubric_total"] is None
    assert riley["patient_name"] == "Alina Reyes"

    history = client.get("/api/encounters", params={"student_name": "Riley"})
    assert history.status_code == 200
    assert history.json()["total"] == 1
    assert [row["encounter_id"] for row in history.json()["encounters"]] == [active_id]
    assert history.json()["encounters"][0]["status"] == "active"

    capped = client.get("/api/encounters", params={"limit": 1})
    assert capped.status_code == 200
    assert capped.json()["limit"] == 1
    assert capped.json()["total"] == 2
    assert len(capped.json()["encounters"]) == 1

    paths = app.openapi()["paths"]
    listed_schema = paths["/api/encounters"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert listed_schema["$ref"] == "#/components/schemas/EncounterList"
    patch = paths["/api/encounters/{enc_id}/feedback"]["patch"]
    assert patch["requestBody"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/FeedbackOverrideRequest"
    assert patch["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/FeedbackResponse"
    assert patch["responses"]["404"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/ErrorResponse"
    assert patch["responses"]["422"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/ErrorResponse"


def test_a_missing_or_active_encounter_does_not_save_an_override(tmp_path, load_golden):
    """Changing feedback before the visit ends, or for an unknown id, leaves no faculty change."""
    client = _client(tmp_path, load_golden)
    missing = _patch(
        client,
        "missing-encounter",
        {"scores": [{"domain": "opening_and_purpose", "score": 4}]},
    )
    assert missing.status_code == 404
    assert missing.json()["message"] == "encounter missing-encounter not found"

    started = client.post("/api/encounters", json={"case_id": "walter_greene", "student_name": "Sam"})
    encounter_id = started.json()["encounter_id"]
    active = _patch(
        client,
        encounter_id,
        {"scores": [{"domain": "opening_and_purpose", "score": 4}]},
    )
    assert active.status_code == 409
    assert active.json()["message"] == "end the encounter first"

    ended = client.post(f"/api/encounters/{encounter_id}/end")
    assert ended.status_code == 200
    # Ending does not invent feedback. The first successful override can score the visit, and the generated score stays.
    saved = _patch(client, encounter_id, {"comments": [{"domain": "opening_and_purpose", "field": "strength_demonstrated", "text": "Opened clearly."}]})
    assert saved.status_code == 200
    assert _domain(saved.json(), "opening_and_purpose")["strength_demonstrated"] != "Opened clearly."
    assert saved.json()["overrides"]["comments"][0]["text"] == "Opened clearly."
