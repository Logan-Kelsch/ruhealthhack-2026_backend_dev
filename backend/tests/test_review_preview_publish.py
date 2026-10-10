"""HTTP contracts for consistency review, test-student preview, and publish.

These tests use FastAPI's TestClient on SQLite. A later read is how a refresh
would see the save. They do not query the database.
"""

from fastapi.testclient import TestClient

from app import db as dbmod
from app import services
from app.db import Base
from app.main import app

DESCRIPTION = "A 58-year-old man with type 2 diabetes and high blood pressure."
AGE_MESSAGE = "Text says 58-year-old but the profile age is 40."


def _client(tmp_path, load_golden) -> TestClient:
    """SQLite API client with the three golden cases already saved."""
    dbmod.init_engine(f"sqlite:///{tmp_path / 'review.db'}")
    Base.metadata.create_all(dbmod.get_engine())
    with next(dbmod.get_session()) as session:
        for case_id in ("walter_greene", "alina_reyes", "eli_brooks"):
            services.upsert_golden(session, load_golden(case_id))
    return TestClient(app)


def test_consistency_findings_persist_when_dismissed(tmp_path, load_golden):
    """A real finding can be dismissed, and a refresh still shows that dismissal."""
    client = _client(tmp_path, load_golden)
    created = client.post("/api/studio/drafts", json={"description": DESCRIPTION})
    assert created.status_code == 201
    case_id = created.json()["case"]["case_id"]
    case = created.json()["case"]
    # The profile age disagrees with the description, which is a review finding.
    case["profile"]["age"] = 40
    case["consistency_findings"] = [
        {
            "id": "age_mismatch_1",
            "rule": "age_mismatch",
            "severity": "review",
            "message": AGE_MESSAGE,
            "refs": ["description"],
            "dismissed": False,
        }
    ]
    saved = client.put(f"/api/studio/cases/{case_id}", json=case)
    assert saved.status_code == 200

    checked = client.get(f"/api/studio/cases/{case_id}/consistency")
    assert checked.status_code == 200
    finding = next(item for item in checked.json() if item["message"] == AGE_MESSAGE)
    assert finding["dismissed"] is False
    assert finding["severity"] == "review"
    assert finding["rule"] == "age_mismatch"
    assert "description" in finding["refs"]
    assert finding["id"]

    dismissed = client.post(f"/api/studio/cases/{case_id}/consistency/{finding['id']}/dismiss")
    assert dismissed.status_code == 200
    assert dismissed.json()["status"] == "draft"
    stored = next(item for item in dismissed.json()["case"]["consistency_findings"] if item["message"] == AGE_MESSAGE)
    assert stored["dismissed"] is True

    # A refresh reads the check again. The dismissal has to still be there.
    refreshed = client.get(f"/api/studio/cases/{case_id}/consistency")
    assert refreshed.status_code == 200
    again = [item for item in refreshed.json() if item["message"] == AGE_MESSAGE]
    assert again
    assert all(item["dismissed"] is True for item in again)

    reopened = client.get(f"/api/studio/cases/{case_id}")
    kept = next(item for item in reopened.json()["case"]["consistency_findings"] if item["message"] == AGE_MESSAGE)
    assert kept["dismissed"] is True

    missing = client.post(f"/api/studio/cases/{case_id}/consistency/not_a_finding/dismiss")
    assert missing.status_code == 404
    assert missing.json()["message"] == "finding not found; run the check again"
    assert missing.json()["blockers"] == []

    unknown = client.get("/api/studio/cases/nobody/consistency")
    assert unknown.status_code == 404
    assert unknown.json()["message"] == "case nobody not found"

    schema = app.openapi()
    findings = schema["paths"]["/api/studio/cases/{case_id}/consistency"]["get"]["responses"]["200"]
    assert findings["content"]["application/json"]["schema"]["items"]["$ref"] == "#/components/schemas/ConsistencyFinding"
    finding_model = schema["components"]["schemas"]["ConsistencyFinding"]
    assert finding_model.get("additionalProperties") is not True
    dismiss_ok = schema["paths"]["/api/studio/cases/{case_id}/consistency/{finding_id}/dismiss"]["post"]["responses"]["200"]
    assert dismiss_ok["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/StudioCaseDetail"
    dismiss_missing = schema["paths"]["/api/studio/cases/{case_id}/consistency/{finding_id}/dismiss"]["post"]["responses"]["404"]
    assert dismiss_missing["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/ErrorResponse"
    check_missing = schema["paths"]["/api/studio/cases/{case_id}/consistency"]["get"]["responses"]["404"]
    assert check_missing["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/ErrorResponse"


# The scripted novice says these lines. They are the driver's script, not a recomputation of the run.
NOVICE_LINES = [
    "What brings you in?",
    "Do you take your medicines?",
    "Any allergies?",
    "Do you drink alcohol?",
    "You need to eat better and take your pills.",
    "Okay, that's all for today.",
]

# Patient lines the Walter case actually says for this novice visit. Taken from the authored facts.
NOVICE_PATIENT = {
    3: "Penicillin gives me hives. Shellfish closes up my throat. And sulfa.",
    4: "A small beer or two in front of the TV.",
    6: "Okay. Thanks.",
}

# Facts this novice run elicits against Walter's medication objective.
NOVICE_DISCOVERIES = [
    {
        "fact_id": "f_metformin_nausea",
        "text": "Skips metformin some days because it makes him nauseous and sometimes vomit.",
        "turn": 2,
        "objective_id": "obj_meds",
    },
    {
        "fact_id": "f_eplerenone_forgets",
        "text": "Sometimes forgets eplerenone; worries it will drop his blood pressure and make him faint.",
        "turn": 2,
        "objective_id": "obj_meds",
    },
    {
        "fact_id": "f_lisinopril_belief",
        "text": "Takes lisinopril every morning; believes it is only for blood pressure.",
        "turn": 2,
        "objective_id": "obj_meds",
    },
]

DISCUSSION_AID = (
    "Use the total as a discussion aid, not a pass/fail grade. "
    "A score of 1 in professionalism, safety, or clinical reasoning should trigger review even when the total is high."
)


def test_preview_returns_the_selected_run_and_reports_driver_fallback(tmp_path, load_golden):
    """Preview runs the chosen level, driver, and visit, and says when the model driver could not."""
    client = _client(tmp_path, load_golden)
    run = client.post(
        "/api/studio/cases/walter_greene/preview",
        json={"level": "novice", "driver": "scripted", "visit_id": "v2"},
    )
    assert run.status_code == 200
    body = run.json()
    assert body["level"] == "novice"
    assert body["driver"] == "scripted"
    assert body["visit_id"] == "v2"
    assert body["fallback"] is None
    assert [turn["student"] for turn in body["transcript"]] == NOVICE_LINES
    assert {turn["turn"]: turn["patient"] for turn in body["transcript"] if turn["turn"] in NOVICE_PATIENT} == NOVICE_PATIENT
    assert body["discoveries"] == NOVICE_DISCOVERIES
    assert body["blocked_replies"] == []
    assert body["replies_failing_audit"] == 0
    assert body["feedback"]["total"] == 12
    assert body["feedback"]["max_total"] == 28
    assert body["feedback"]["interpretation"] == DISCUSSION_AID
    assert [(domain["key"], domain["score"]) for domain in body["feedback"]["domains"]] == [
        ("opening_and_purpose", 2),
        ("rapport_respect_empathy", 2),
        ("information_gathering", 1),
        ("listening_and_response_to_cues", 3),
        ("explanation_and_shared_decisions", 1),
        ("clinical_reasoning_and_synthesis", 1),
        ("professionalism_safety_closure", 2),
    ]

    # The model driver is off in this test, so the scripted student runs and the response says so.
    fallback = client.post(
        "/api/studio/cases/walter_greene/preview",
        json={"level": "novice", "driver": "llm", "visit_id": "v1"},
    )
    assert fallback.status_code == 200
    fell_back = fallback.json()
    assert fell_back["driver"] == "scripted"
    assert fell_back["visit_id"] == "v1"
    assert fell_back["fallback"] == {
        "requested": "llm",
        "used": "scripted",
        "reason": "The language model is not available, so the scripted test student ran instead.",
    }
    assert [turn["student"] for turn in fell_back["transcript"]] == NOVICE_LINES

    missing = client.post("/api/studio/cases/walter_greene/preview", json={"level": "novice", "visit_id": "v9"})
    assert missing.status_code == 404
    assert missing.json()["message"] == "visit v9 not found"
    assert missing.json()["blockers"] == []

    schema = app.openapi()
    preview_ok = schema["paths"]["/api/studio/cases/{case_id}/preview"]["post"]["responses"]["200"]
    assert preview_ok["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/PreviewRun"
    preview_model = schema["components"]["schemas"]["PreviewRun"]
    assert set(preview_model["properties"]) == {
        "level",
        "driver",
        "visit_id",
        "fallback",
        "transcript",
        "discoveries",
        "blocked_replies",
        "feedback",
        "replies_failing_audit",
    }
    assert preview_model.get("additionalProperties") is not True
    preview_missing = schema["paths"]["/api/studio/cases/{case_id}/preview"]["post"]["responses"]["404"]
    assert preview_missing["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/ErrorResponse"


def test_publish_blockers_leave_the_case_a_draft(tmp_path, load_golden):
    """A rejected publish stays a draft, and the blocker sentences stay on the error."""
    client = _client(tmp_path, load_golden)
    created = client.post("/api/studio/drafts", json={"description": DESCRIPTION})
    case_id = created.json()["case"]["case_id"]
    rejected = client.post(f"/api/studio/cases/{case_id}/publish")
    assert rejected.status_code == 409
    body = rejected.json()
    assert body["message"] == "This case is not ready to publish."
    assert body["errors"] == []
    assert "Missing: What is the patient's name?" in body["blockers"]
    assert body["blockers"]
    assert all(isinstance(item, str) and " " in item for item in body["blockers"])

    opened = client.get(f"/api/studio/cases/{case_id}")
    assert opened.json()["status"] == "draft"
    assert opened.json()["case"]["status"] == "draft"
    assert opened.json()["case"]["version"] == 1


def test_publish_returns_the_saved_published_version(tmp_path, load_golden):
    """Publishing a ready draft returns that version, and the library lists it as published."""
    client = _client(tmp_path, load_golden)
    full = client.get("/api/studio/cases/eli_brooks").json()
    case = full["case"]
    case["title"] = case["title"] + " (ready)"
    saved = client.put("/api/studio/cases/eli_brooks", json=case)
    assert saved.status_code == 200
    assert saved.json()["status"] == "draft"
    assert saved.json()["case"]["version"] == 2
    assert saved.json()["blockers"] == []

    published = client.post("/api/studio/cases/eli_brooks/publish")
    assert published.status_code == 200
    body = published.json()
    assert body["status"] == "published"
    assert body["case"]["status"] == "published"
    assert body["case"]["version"] == 2
    assert body["case"]["title"].endswith("(ready)")
    assert body["blockers"] == []

    listed = client.get("/api/studio/cases").json()
    eli = next(row for row in listed if row["case_id"] == "eli_brooks")
    assert eli["status"] == "published"
    assert eli["version"] == 2
    assert eli["blockers"] == []

    missing = client.post("/api/studio/cases/nobody/publish")
    assert missing.status_code == 404
    assert missing.json()["message"] == "case nobody not found"

    schema = app.openapi()
    publish_ok = schema["paths"]["/api/studio/cases/{case_id}/publish"]["post"]["responses"]["200"]
    assert publish_ok["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/StudioCaseDetail"
    publish_blocked = schema["paths"]["/api/studio/cases/{case_id}/publish"]["post"]["responses"]["409"]
    assert publish_blocked["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/ErrorResponse"
    publish_missing = schema["paths"]["/api/studio/cases/{case_id}/publish"]["post"]["responses"]["404"]
    assert publish_missing["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/ErrorResponse"


def test_later_edit_keeps_the_encounter_on_its_original_case_version(tmp_path, load_golden):
    """An encounter keeps the published version it started with after a new draft is saved."""
    client = _client(tmp_path, load_golden)
    started = client.post(
        "/api/encounters",
        json={"case_id": "walter_greene", "version": 1, "visit_id": "v1", "student_name": "Sam"},
    )
    assert started.status_code == 201
    encounter_id = started.json()["encounter_id"]
    assert started.json()["case_version"] == 1
    blood_pressure = next(item for item in started.json()["chart"] if item["ref"] == "bp")
    assert blood_pressure["value"].startswith("158/92")

    studio = client.get("/api/studio/cases/walter_greene").json()
    case = studio["case"]
    vital = next(item for item in case["vitals"] if item["key"] == "bp")
    vital["value"] = "99/50"
    saved = client.put("/api/studio/cases/walter_greene", json=case)
    assert saved.status_code == 200
    assert saved.json()["status"] == "draft"
    assert saved.json()["case"]["version"] == 2
    edited = next(item for item in saved.json()["case"]["vitals"] if item["key"] == "bp")
    assert edited["value"] == "99/50"

    recovered = client.get(f"/api/encounters/{encounter_id}")
    assert recovered.status_code == 200
    assert recovered.json()["case_version"] == 1
    still = next(item for item in recovered.json()["chart"] if item["ref"] == "bp")
    assert still["value"].startswith("158/92")
    assert "99/50" not in still["value"]

    # Students still open the published version. The new draft is not that version.
    public = client.get("/api/cases/walter_greene")
    assert public.status_code == 200
    assert public.json()["version"] == 1
    doorway = next(item for item in public.json()["doorway_vitals"] if item["key"] == "bp")
    assert doorway["value"] == "158/92"
