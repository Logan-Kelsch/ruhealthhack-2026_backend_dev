"""HTTP contracts for creating a draft and answering guided intake.

These tests use FastAPI's TestClient. They check the saved case through the
API, not through the database.
"""

import pytest
from fastapi.testclient import TestClient

from app import db as dbmod
from app import services
from app.db import Base
from app.main import app

DESCRIPTION = "A 58-year-old man with type 2 diabetes and high blood pressure."

# Questions the faculty member should see for this description. Age is already
# in the sentence, so the age question is not one of them.
EXPECTED_GAPS = [
    {"id": "name", "question": "What is the patient's name?", "kind": "field", "blocking": True},
    {
        "id": "reason_for_visit",
        "question": "What is the reason for the visit, as it would appear on the schedule?",
        "kind": "field",
        "blocking": True,
    },
    {
        "id": "student_role",
        "question": "Who is the student in this encounter (profession and training level)?",
        "kind": "field",
        "blocking": True,
    },
    {
        "id": "goal",
        "question": "What should the student accomplish in this visit?",
        "kind": "field",
        "blocking": True,
    },
    {
        "id": "chief_complaint",
        "question": "In the patient's own words, why are they here today?",
        "kind": "facts",
        "blocking": True,
    },
    {
        "id": "medications",
        "question": "What medicines does the patient take, and do they take them as prescribed?",
        "kind": "facts",
        "blocking": False,
    },
    {
        "id": "allergies",
        "question": 'Any allergies? If none, say "no known allergies".',
        "kind": "facts",
        "blocking": False,
    },
    {
        "id": "social",
        "question": "Who do they live with, and what is daily life like (work, money, support)?",
        "kind": "facts",
        "blocking": False,
    },
    {
        "id": "personal_cue",
        "question": "What is one personal detail the patient might mention in passing (a pet, a hobby, a person)?",
        "kind": "facts",
        "blocking": False,
    },
    {
        "id": "hidden",
        "question": "What does the patient only share once they trust the student?",
        "kind": "facts",
        "blocking": False,
    },
    {
        "id": "goals_fears",
        "question": "What does the patient want from this visit, and what worries them?",
        "kind": "facts",
        "blocking": False,
    },
    {
        "id": "objectives",
        "question": "What are one to three things the student should learn from this case?",
        "kind": "objectives",
        "blocking": True,
    },
    {
        "id": "vitals",
        "question": "No vital signs yet. Use auto-fill, or type them in.",
        "kind": "autofill",
        "blocking": False,
    },
]


@pytest.fixture
def client(tmp_path, load_golden):
    """SQLite API client with the three golden cases already saved."""
    dbmod.init_engine(f"sqlite:///{tmp_path / 'draft-intake.db'}")
    Base.metadata.create_all(dbmod.get_engine())
    with next(dbmod.get_session()) as session:
        for case_id in ("walter_greene", "alina_reyes", "eli_brooks"):
            services.upsert_golden(session, load_golden(case_id))
    return TestClient(app)


def test_description_creates_one_saved_draft(client):
    """A plain-language description is stored as one draft the faculty member can open again."""
    before = client.get("/api/studio/cases")
    assert before.status_code == 200
    before_ids = {row["case_id"] for row in before.json()}

    created = client.post("/api/studio/drafts", json={"description": DESCRIPTION})
    assert created.status_code == 201
    body = created.json()
    case_id = body["case"]["case_id"]

    assert case_id not in before_ids
    assert body["status"] == "draft"
    assert body["llm_calls"] == []
    assert body["gaps"] == EXPECTED_GAPS
    assert body["blockers"] == [
        "Missing: What is the patient's name?",
        "Missing: What is the reason for the visit, as it would appear on the schedule?",
        "Missing: Who is the student in this encounter (profession and training level)?",
        "Missing: What should the student accomplish in this visit?",
        "Missing: In the patient's own words, why are they here today?",
        "Missing: What are one to three things the student should learn from this case?",
    ]
    case = body["case"]
    assert case["case_id"] == case_id
    assert case["version"] == 1
    assert case["status"] == "draft"
    assert case["title"] == "New case (draft)"
    assert case["description"] == DESCRIPTION
    assert case["profile"]["name"] == "New patient"
    assert case["profile"]["age"] == 58
    assert case["profile"]["sex"] == "male"
    assert case["facts"] == []
    assert case["vitals"] == []
    assert case["labs"] == []
    assert case["medications"] == []
    assert case["allergies"] == []
    assert case["objectives"] == []
    assert case["golden"] is False

    listed = client.get("/api/studio/cases")
    assert listed.status_code == 200
    matches = [row for row in listed.json() if row["case_id"] == case_id]
    assert len(matches) == 1
    assert matches[0]["version"] == 1
    assert matches[0]["status"] == "draft"
    assert matches[0]["patient"] == "New patient"
    assert matches[0]["title"] == "New case (draft)"

    opened = client.get(f"/api/studio/cases/{case_id}", params={"version": 1})
    assert opened.status_code == 200
    opened_body = opened.json()
    assert opened_body["case"]["case_id"] == case_id
    assert opened_body["case"]["version"] == 1
    assert opened_body["case"]["description"] == DESCRIPTION
    assert opened_body["status"] == "draft"
    assert opened_body["gaps"] == EXPECTED_GAPS
    assert "llm_calls" not in opened_body

    schema = app.openapi()
    draft_created = schema["paths"]["/api/studio/drafts"]["post"]["responses"]["201"]
    draft_schema = draft_created["content"]["application/json"]["schema"]
    assert draft_schema["$ref"] == "#/components/schemas/StudioDraftResult"
    detail_schema = schema["paths"]["/api/studio/cases/{case_id}"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert detail_schema["$ref"] == "#/components/schemas/StudioCaseDetail"
    named = schema["components"]["schemas"]
    assert set(named["StudioDraftResult"]["properties"]) == {"case", "status", "gaps", "blockers", "llm_calls"}
    assert named["StudioDraftResult"].get("additionalProperties") is not True
    assert set(named["StudioCaseDetail"]["properties"]) == {"case", "status", "gaps", "blockers"}
    assert named["StudioCaseDetail"].get("additionalProperties") is not True
    assert named["IntakeGap"]["properties"]["kind"]["enum"] == ["field", "facts", "objectives", "autofill"]
    assert set(named["NewDraft"]["required"]) == {"description"}
    assert set(named["NewDraft"]["properties"]) == {"description", "faculty"}


def test_answering_a_gap_persists_on_the_same_draft(client):
    """An allergy answer is stored on that draft, still unapproved, and the question closes."""
    created = client.post("/api/studio/drafts", json={"description": DESCRIPTION})
    assert created.status_code == 201
    case_id = created.json()["case"]["case_id"]

    answered = client.post(
        f"/api/studio/cases/{case_id}/intake",
        json={"gap_id": "allergies", "text": "No known allergies"},
    )
    assert answered.status_code == 200
    body = answered.json()
    assert body["case"]["case_id"] == case_id
    assert body["case"]["version"] == 1
    assert body["status"] == "draft"
    assert body["llm_calls"] == []
    assert body["case"]["medications"] == []
    assert body["case"]["vitals"] == []
    assert body["case"]["labs"] == []
    assert [gap["id"] for gap in body["gaps"]] == [gap["id"] for gap in EXPECTED_GAPS if gap["id"] != "allergies"]
    assert len(body["case"]["facts"]) == 1
    fact = body["case"]["facts"][0]
    assert fact["id"] == "f_allergies_1"
    assert fact["text"] == "No known allergies"
    assert fact["category"] == "allergy"
    assert fact["tier"] == "discoverable"
    assert fact["status"] == "draft"
    assert fact["source"]["kind"] == "faculty"
    assert fact["source"]["ref"] == "intake:allergies"

    opened = client.get(f"/api/studio/cases/{case_id}", params={"version": 1})
    assert opened.status_code == 200
    saved = opened.json()["case"]["facts"]
    assert len(saved) == 1
    assert saved[0]["text"] == "No known allergies"
    assert saved[0]["status"] == "draft"
    assert saved[0]["source"]["kind"] == "faculty"

    intake_schema = app.openapi()["paths"]["/api/studio/cases/{case_id}/intake"]["post"]
    success = intake_schema["responses"]["200"]["content"]["application/json"]["schema"]
    assert success["$ref"] == "#/components/schemas/StudioDraftResult"
    request_body = intake_schema["requestBody"]["content"]["application/json"]["schema"]
    assert request_body["$ref"] == "#/components/schemas/IntakeAnswer"
    answer = app.openapi()["components"]["schemas"]["IntakeAnswer"]
    assert set(answer["required"]) == {"gap_id", "text"}
    assert set(answer["properties"]) == {"gap_id", "text", "faculty"}


def test_a_name_answer_updates_the_saved_profile(client):
    """The name question writes the profile name and leaves every fact still unapproved."""
    created = client.post("/api/studio/drafts", json={"description": DESCRIPTION})
    case_id = created.json()["case"]["case_id"]

    answered = client.post(
        f"/api/studio/cases/{case_id}/intake",
        json={"gap_id": "name", "text": "Jordan Hale"},
    )
    assert answered.status_code == 200
    body = answered.json()
    assert body["case"]["profile"]["name"] == "Jordan Hale"
    assert body["case"]["facts"] == []
    assert body["case"]["version"] == 1
    assert all(gap["id"] != "name" for gap in body["gaps"])

    opened = client.get(f"/api/studio/cases/{case_id}", params={"version": 1})
    assert opened.json()["case"]["profile"]["name"] == "Jordan Hale"
    assert opened.json()["case"]["facts"] == []


def test_failed_create_does_not_save_or_echo_the_description(client):
    """A description that fails validation is not saved, and the error does not repeat it."""
    secret = "secret-x"
    before = [row["case_id"] for row in client.get("/api/studio/cases").json()]

    response = client.post(
        "/api/studio/drafts",
        json={"description": secret, "faculty": "do-not-echo-faculty"},
    )

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
    assert secret not in response.text
    assert "do-not-echo-faculty" not in response.text
    assert [row["case_id"] for row in client.get("/api/studio/cases").json()] == before


def test_failed_intake_does_not_change_the_saved_draft(client):
    """A rejected answer leaves the draft as it was and does not repeat the answer text."""
    created = client.post("/api/studio/drafts", json={"description": DESCRIPTION})
    case_id = created.json()["case"]["case_id"]
    before = client.get(f"/api/studio/cases/{case_id}", params={"version": 1}).json()
    ids_before = [row["case_id"] for row in client.get("/api/studio/cases").json()]

    missing_gap = client.post(
        f"/api/studio/cases/{case_id}/intake",
        json={"text": "do-not-echo-this-answer"},
    )
    assert missing_gap.status_code == 422
    assert "do-not-echo-this-answer" not in missing_gap.text
    error = missing_gap.json()
    assert error["blockers"] == []
    assert error["errors"] == [
        {
            "loc": ["body", "gap_id"],
            "msg": "Field required",
            "type": "missing",
        }
    ]
    assert "input" not in error

    unknown = client.post(
        "/api/studio/cases/nobody/intake",
        json={"gap_id": "name", "text": "Ada Lovelace"},
    )
    assert unknown.status_code == 404
    assert unknown.json() == {
        "message": "case nobody not found",
        "errors": [],
        "blockers": [],
    }
    assert "Ada Lovelace" not in unknown.text

    after = client.get(f"/api/studio/cases/{case_id}", params={"version": 1}).json()
    assert after == before
    ids_after = [row["case_id"] for row in client.get("/api/studio/cases").json()]
    assert ids_after == ids_before
    assert "nobody" not in ids_after

    documented = app.openapi()["paths"]["/api/studio/cases/{case_id}/intake"]["post"]["responses"]["404"]
    assert documented["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/ErrorResponse"


def test_refreshing_the_same_version_does_not_create_a_second_case(client):
    """Opening the same case id and version twice returns that draft and adds no row."""
    created = client.post("/api/studio/drafts", json={"description": DESCRIPTION})
    case_id = created.json()["case"]["case_id"]
    version = created.json()["case"]["version"]
    listed = client.get("/api/studio/cases").json()

    first = client.get(f"/api/studio/cases/{case_id}", params={"version": version})
    second = client.get(f"/api/studio/cases/{case_id}", params={"version": version})
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    assert second.json()["case"]["case_id"] == case_id
    assert second.json()["case"]["version"] == version

    again = client.get("/api/studio/cases").json()
    assert again == listed
    assert [row["case_id"] for row in again].count(case_id) == 1
