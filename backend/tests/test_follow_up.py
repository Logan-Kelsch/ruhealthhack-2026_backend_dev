"""Follow-up visits selected from a completed encounter.

These tests speak two different visit-1 paths on the published Walter Greene
case, then continue. Expected vitals, notes, and summaries are the faculty
text in that case, not values recomputed by the test.
"""

from fastapi.testclient import TestClient

from app import db as dbmod
from app import services
from app.db import Base
from app.main import app

# Faculty-authored outcome text from cases/walter_greene.json.
IMPROVED_SUMMARY = (
    "He switched to Tylenol for his back and orders the plain version at the dinner club. "
    "Blood pressure and swelling are better."
)
PARTIAL_SUMMARY = "He stopped the ibuprofen, but dinner-club meals are the same. Swelling is about the same."
MISSED_SUMMARY = (
    "Nobody caught the ibuprofen. Two weeks later he was hospitalized with fluid in his lungs "
    "and worse kidney function."
)
DISCHARGE_NOTE = (
    "Admitted 4 days for acute on chronic heart failure with fluid overload and acute kidney injury. "
    "Home medicines reviewed. Ibuprofen use noted."
)
# The patient says this only after the improved branch is disclosed. It is not a chart value.
WITHHELD_SAY = "I switched to Tylenol like you said"
V2_GOAL = "Review what changed since the first visit and adjust the plan."


def _client(tmp_path, load_golden) -> TestClient:
    """SQLite API with the published golden cases and no live model calls."""
    dbmod.init_engine(f"sqlite:///{tmp_path / 'follow-up.db'}")
    Base.metadata.create_all(dbmod.get_engine())
    with next(dbmod.get_session()) as session:
        for case_id in ("walter_greene", "alina_reyes", "eli_brooks"):
            services.upsert_golden(session, load_golden(case_id))
    return TestClient(app)


def _finish(client: TestClient, utterances: list[str]) -> str:
    """Run one visit 1 and store a note so the debrief, and a follow-up, can be requested."""
    started = client.post("/api/encounters", json={"case_id": "walter_greene", "version": 1, "student_name": "Sam"})
    assert started.status_code == 201
    encounter_id = started.json()["encounter_id"]
    assert started.json()["case_version"] == 1
    for text in utterances:
        sent = client.post(f"/api/encounters/{encounter_id}/utterances", json={"text": text})
        assert sent.status_code == 200
    documented = client.post(
        f"/api/encounters/{encounter_id}/documentation",
        json={"fields": {"problem": "Nutrition follow-up."}},
    )
    assert documented.status_code == 200
    return encounter_id


def _continue(client: TestClient, encounter_id: str) -> dict:
    """Start the next visit from the finished encounter, ignoring any other visit id."""
    started = client.post(
        "/api/encounters",
        json={
            "case_id": "walter_greene",
            "version": 99,
            "visit_id": "v9",
            "previous_encounter_id": encounter_id,
        },
    )
    assert started.status_code == 201
    return started.json()


def test_two_prior_paths_apply_the_authored_follow_up(tmp_path, load_golden):
    """Finding the ibuprofen path and missing it release different faculty-written visit-2 state."""
    client = _client(tmp_path, load_golden)
    improved_id = _finish(
        client,
        [
            "Do you take anything over the counter for pain?",
            "Ibuprofen is hard on your kidneys and your heart. Ask about Tylenol instead.",
            "How often do you eat out with your dinner club?",
            "Let's cut back on the salt at those meals.",
        ],
    )
    missed_id = _finish(client, ["How have you been sleeping?"])

    improved = _continue(client, improved_id)
    missed = _continue(client, missed_id)

    assert improved["visit_id"] == "v2"
    assert improved["case_version"] == 1
    assert improved["previous_encounter_id"] == improved_id
    assert improved["briefing"]["goal"] == V2_GOAL
    improved_bp = next(item for item in improved["chart"] if item["ref"] == "bp")
    assert improved_bp["value"].startswith("142/86")
    assert improved_bp["source"]["kind"] == "faculty"
    assert all(item["label"] != "Hospital discharge summary" for item in improved["chart"])
    assert WITHHELD_SAY not in str(improved)

    assert missed["visit_id"] == "v2"
    assert missed["case_version"] == 1
    assert missed["previous_encounter_id"] == missed_id
    assert missed["briefing"]["goal"] == V2_GOAL
    missed_bp = next(item for item in missed["chart"] if item["ref"] == "bp")
    assert missed_bp["value"].startswith("162/94")
    discharge = next(item for item in missed["chart"] if item["ref"] == "discharge")
    assert discharge["label"] == "Hospital discharge summary"
    assert discharge["body"] == DISCHARGE_NOTE
    assert "142/86" not in str(missed)
    assert WITHHELD_SAY not in str(missed)

    # A refresh reads the same follow-up. It does not start another visit.
    before = {row["encounter_id"] for row in client.get("/api/encounters").json()["encounters"]}
    again = client.get(f"/api/encounters/{improved['encounter_id']}")
    assert again.status_code == 200
    assert again.json()["encounter_id"] == improved["encounter_id"]
    assert again.json()["previous_encounter_id"] == improved_id
    assert again.json()["case_version"] == 1
    assert next(item for item in again.json()["chart"] if item["ref"] == "bp")["value"].startswith("142/86")
    assert {row["encounter_id"] for row in client.get("/api/encounters").json()["encounters"]} == before


def _ids(client: TestClient) -> set[str]:
    """Encounter ids that exist. A rejected continuation must not add one."""
    listed = client.get("/api/encounters")
    assert listed.status_code == 200
    return {row["encounter_id"] for row in listed.json()["encounters"]}


def test_debrief_paths_are_public_and_a_bad_continuation_is_rejected(tmp_path, load_golden):
    """The debrief names the taken and unselected outcomes. A bad continuation does not open a visit."""
    client = _client(tmp_path, load_golden)
    improved_id = _finish(
        client,
        [
            "Do you take anything over the counter for pain?",
            "Ibuprofen is hard on your kidneys and your heart. Ask about Tylenol instead.",
            "How often do you eat out with your dinner club?",
            "Let's cut back on the salt at those meals.",
        ],
    )
    feedback = client.get(f"/api/encounters/{improved_id}/feedback")
    assert feedback.status_code == 200
    path = feedback.json()["decision_path"]
    assert path["visit_id"] == "v1"
    assert path["taken"]["id"] == "b_improved"
    assert path["taken"]["label"] == "Stopped ibuprofen and changed dinner-club orders"
    assert path["taken"]["summary"] == IMPROVED_SUMMARY
    assert set(path["taken"]) == {"id", "label", "summary", "evidence"}
    pain_quote = "Do you take anything over the counter for pain?"
    assert any(item["quote"] == pain_quote for item in path["taken"]["evidence"])
    ghosts = {item["id"]: item for item in path["ghosts"]}
    assert ghosts["b_partial"]["summary"] == PARTIAL_SUMMARY
    assert ghosts["b_nsaid_missed"]["summary"] == MISSED_SUMMARY
    for ghost in ghosts.values():
        assert set(ghost) == {"id", "label", "summary", "evidence"}
    nsaid = next(item for item in path["decisions"] if item["id"] == "dp_nsaid")
    # Offline keyword tags are low confidence, so the result is unclear, but the path still counts it as yes.
    assert nsaid["result"] == "unclear"
    assert "Found the ibuprofen use and explained the risk" in path["needs_faculty_review"]
    assert nsaid["label"] == "Found the ibuprofen use and explained the risk"
    assert any(item["quote"] == pain_quote for item in nsaid["evidence"])
    assert "predicate" not in nsaid
    rendered = str(feedback.json())
    assert "probability" not in rendered
    assert WITHHELD_SAY not in rendered
    assert "162/94" not in rendered
    assert "Hospital discharge summary" not in rendered
    assert "3+ pitting edema up to both knees" not in rendered
    assert '"changes"' not in rendered
    assert '"when"' not in rendered
    branch_schema = app.openapi()["components"]["schemas"]["BranchSummary"]["properties"]
    assert set(branch_schema) == {"id", "label", "summary", "evidence"}
    assert "decisions" in app.openapi()["components"]["schemas"]["DecisionPathView"]["properties"]

    # The case card for visit 2 does not preview a branch that this student has not taken.
    preview = client.get("/api/cases/walter_greene", params={"visit_id": "v2"})
    assert preview.status_code == 200
    assert preview.json()["briefing"]["goal"] == V2_GOAL
    assert all(item["value"] != "142/86" for item in preview.json()["doorway_vitals"])
    assert "Hospital discharge summary" not in str(preview.json())

    before = _ids(client)
    missing = client.post("/api/encounters", json={"case_id": "walter_greene", "previous_encounter_id": "missing"})
    assert missing.status_code == 404
    assert _ids(client) == before

    active = client.post("/api/encounters", json={"case_id": "walter_greene", "student_name": "Sam"})
    assert active.status_code == 201
    active_id = active.json()["encounter_id"]
    before = _ids(client)
    early = client.post("/api/encounters", json={"case_id": "walter_greene", "previous_encounter_id": active_id})
    assert early.status_code == 409
    assert early.json()["message"]
    assert _ids(client) == before

    invented = client.post("/api/encounters", json={"case_id": "walter_greene", "visit_id": "v2"})
    assert invented.status_code == 409
    assert _ids(client) == before

    other_case = client.post("/api/encounters", json={"case_id": "alina_reyes", "previous_encounter_id": improved_id})
    assert other_case.status_code == 409
    assert _ids(client) == before

    follow_up = _continue(client, improved_id)
    before = _ids(client)
    no_third = client.post(
        "/api/encounters",
        json={"case_id": "walter_greene", "previous_encounter_id": follow_up["encounter_id"]},
    )
    assert no_third.status_code == 409
    assert _ids(client) == before
