"""HTTP contract for importing the sponsor sample set as reviewable drafts.

These tests talk to the API through FastAPI's TestClient. They do not call
the importer's private helpers, and they do not publish the imported cases.
"""

import pytest
from fastapi.testclient import TestClient

from app import db as dbmod
from app.db import Base
from app.main import app

# The eight names in the bundled sample file, in file order. The count is this
# set, not whatever the handler happens to return.
SAMPLE_PATIENTS = [
    "Dominic Rivera",
    "Yvette Armstrong",
    "Nisha Patel",
    "Omar Sinclair",
    "Marcus Ramirez",
    "Walter Greene",
    "Wyatt Nelson",
    "Vladko Bareche",
]


@pytest.fixture
def client(tmp_path):
    """Empty SQLite API. Golden cases are not seeded, so import ids stay the profile slugs."""
    dbmod.init_engine(f"sqlite:///{tmp_path / 'sponsor-import.db'}")
    Base.metadata.create_all(dbmod.get_engine())
    return TestClient(app)


def test_sponsor_sample_import_saves_reviewable_drafts(client):
    """Importing the sample set returns the real count and drafts, and keeps the sponsor fields."""
    response = client.post("/api/studio/import/vhs")

    assert response.status_code == 201
    body = response.json()
    assert body["count"] == 8
    assert [row["patient"] for row in body["cases"]] == SAMPLE_PATIENTS
    assert {row["status"] for row in body["cases"]} == {"draft"}
    assert {row["version"] for row in body["cases"]} == {1}
    assert {row["golden"] for row in body["cases"]} == {False}
    assert all(row["blockers"] for row in body["cases"])

    # Students only see published cases, so these drafts stay out of that list.
    assert client.get("/api/cases").json() == []

    listed = client.get("/api/studio/cases").json()
    assert [row["patient"] for row in listed] == sorted(SAMPLE_PATIENTS)
    assert {row["status"] for row in listed} == {"draft"}

    walter_id = next(row["case_id"] for row in body["cases"] if row["patient"] == "Walter Greene")
    detail = client.get(f"/api/studio/cases/{walter_id}").json()
    assert detail["status"] == "draft"
    case = detail["case"]
    assert case["status"] == "draft"
    assert case["golden"] is False

    initial = next(fact for fact in case["facts"] if fact["text"] == "He introduces himself as Walter Greene.")
    assert initial["tier"] == "initial"
    assert initial["status"] == "draft"
    assert initial["source"]["kind"] == "vhs_import"
    assert initial["source"]["ref"] == (
        "data/vhs/virtual-patient-profiles-sample.json :: information_disclosure.initial_information[0]"
    )
    assert any(
        fact["tier"] == "discoverable" and "dinner club" in fact["text"]
        for fact in case["facts"]
    )
    assert any(fact["tier"] == "reluctant" and "failed his kids" in fact["text"] for fact in case["facts"])
    assert any(fact["tier"] == "hidden" and "scared about his future" in fact["text"] for fact in case["facts"])
    assert all(fact["source"]["kind"] == "vhs_import" for fact in case["facts"])

    assert any(item["text"].startswith("Apply the Nutrition Care Process.") for item in case["objectives"])
    assert case["objectives"]
    assert all(item["status"] == "draft" for item in case["objectives"])

    assert "Patient will say 'I don't need a care plan, I just need to eat less.'" in case["profile"]["personality"]["example_lines"]

    rules = {finding["rule"] for finding in case["consistency_findings"]}
    assert {"lab_text_mismatch", "unknown_drug_name", "weight_contradiction", "age_mismatch", "nsaid_with_hf_or_ckd"} <= rules
    assert any("Epirocil" in finding["message"] for finding in case["consistency_findings"])
    assert all(finding["dismissed"] is False for finding in case["consistency_findings"])

    assert {
        "what": "Patient profile",
        "source": "Rutgers Virtual Health Simulation sample profiles (event-provided)",
    } in case["credits"]

    operation = app.openapi()["paths"]["/api/studio/import/vhs"]["post"]
    assert "requestBody" not in operation
    assert "sample set" in operation["description"].lower()
    created = operation["responses"]["201"]["content"]["application/json"]["schema"]
    assert created["$ref"] == "#/components/schemas/VhsImportResponse"
    model = app.openapi()["components"]["schemas"]["VhsImportResponse"]
    assert set(model["properties"]) == {"count", "cases"}
    assert model["properties"]["cases"]["items"]["$ref"] == "#/components/schemas/StudioCaseSummary"
    assert model.get("additionalProperties") is not True


def test_failed_sponsor_import_is_visible_and_saves_nothing(client, monkeypatch, tmp_path):
    """A sample set that cannot be read is an error, and no draft is stored for it."""
    monkeypatch.setattr("app.studio.vhs_import.VHS_PATH", tmp_path / "missing-sample.json")
    before = client.get("/api/studio/cases").json()

    response = client.post("/api/studio/import/vhs")

    assert response.status_code == 500
    assert response.json() == {
        "message": "The sponsor sample set could not be imported.",
        "errors": [],
        "blockers": [],
    }
    assert client.get("/api/studio/cases").json() == before

    error_ref = app.openapi()["paths"]["/api/studio/import/vhs"]["post"]["responses"]["500"]["content"]["application/json"]["schema"]["$ref"]
    assert error_ref == "#/components/schemas/ErrorResponse"
