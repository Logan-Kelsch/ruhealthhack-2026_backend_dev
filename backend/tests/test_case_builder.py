"""HTTP contracts for the guided case builder (S-01 to S-04).

Run offline (LLM_ENABLED=false), so suggestions fall back to what code can read.
"""

import pytest
from fastapi.testclient import TestClient

from app import db as dbmod
from app.db import Base
from app.main import app
from app.studio import builder

DESCRIPTION = "A 58-year-old man with type 2 diabetes and high blood pressure who keeps missing doses."

FORM = {
    "description": DESCRIPTION,
    "notes": "Learners should notice the missed doses.",
    "name": "Ray Ortiz",
    "age": 58,
    "sex": "male",
    "setting": "Primary care clinic",
    "reason_for_visit": "Diabetes follow-up",
    "student_role": "Third-year medical student",
    "goal": "Find out why doses are missed and agree on one change.",
    "chief_complaint": "My sugar has been high and the doctor wanted me to come in.",
    "social": "Lives alone, drives a delivery truck on night shifts.",
    "hidden": "He skips metformin on work nights because it upsets his stomach.",
    "objectives": "Ask about adherence without judgment\nAgree on one realistic change",
    "conditions": [{"name": "Type 2 diabetes mellitus", "code": "E11.9"}, {"name": "Hypertension"}],
    "medications": [{"name": "Metformin", "dose": "1000 mg", "frequency": "twice daily", "purpose": "diabetes"}],
    "no_known_allergies": True,
    "vitals": [{"key": "temp_c", "label": "Temperature", "value": "36.9", "unit": "°C"}],
}


@pytest.fixture
def client(tmp_path):
    dbmod.init_engine(f"sqlite:///{tmp_path / 'builder.db'}")
    Base.metadata.create_all(dbmod.get_engine())
    return TestClient(app)


def test_suggest_offline_reads_only_age_and_sex(client):
    """Without the model nothing is guessed. Age and sex come from the sentence."""
    got = client.post("/api/studio/builder/suggest", json={"description": DESCRIPTION})
    assert got.status_code == 200
    body = got.json()
    assert body["used_model"] is False
    assert body["form"]["age"] == 58
    assert body["form"]["sex"] == "male"
    assert body["form"]["name"] == ""
    assert body["form"]["conditions"] == []
    assert body["llm_calls"] == []


def test_suggest_never_takes_measurements_from_the_model(monkeypatch):
    """A model reply with vitals in it does not put them on the form."""

    class Call:
        def to_dicts(self):
            return []

    reply = {"name": "Ray", "age": 58, "sex": "male", "vitals": [{"key": "bp", "value": "190/120"}], "conditions": ["Hypertension"]}
    monkeypatch.setattr(builder, "complete_json", lambda **_: (reply, Call()))
    suggestion, _ = builder.suggest(DESCRIPTION, "", use_llm=True)
    assert suggestion.used_model is True
    assert suggestion.form.name == "Ray"
    assert suggestion.form.vitals == []
    assert [c.name for c in suggestion.form.conditions] == ["Hypertension"]


def test_typical_vitals_name_their_source_and_follow_condition_rules(client):
    body = {"description": DESCRIPTION, "age": 58, "sex": "male", "conditions": [{"name": "Hypertension"}]}
    first = client.post("/api/studio/builder/vitals", json=body).json()
    again = client.post("/api/studio/builder/vitals", json=body).json()
    assert first == again
    by_key = {v["key"]: v for v in first["vitals"]}
    assert set(by_key) == {"bp", "hr", "rr", "temp_c", "spo2"}
    systolic = int(by_key["bp"]["value"].split("/")[0])
    assert systolic >= 140
    assert by_key["bp"]["source"]["kind"] == "rule"
    assert by_key["hr"]["source"]["kind"] == "reference"


def test_typical_vitals_say_when_there_is_no_band(client):
    got = client.post("/api/studio/builder/vitals", json={"age": 3, "sex": "female"}).json()
    assert got["vitals"] == []
    assert got["notes"]


def test_builder_saves_one_draft_with_the_form_content(client):
    created = client.post("/api/studio/builder", json=FORM)
    assert created.status_code == 201
    body = created.json()
    case = body["case"]
    assert body["status"] == "draft"
    assert case["profile"]["name"] == "Ray Ortiz"
    assert case["title"] == "Ray Ortiz: Diabetes follow-up"
    assert "Faculty notes: Learners should notice the missed doses." in case["profile"]["summary"]
    assert case["diagnoses"][0]["codes"] == [{"system": "ICD-10-CM", "code": "E11.9", "display": "Type 2 diabetes mellitus"}]
    assert case["medications"][0]["name"] == "Metformin"
    assert [v["key"] for v in case["vitals"]] == ["temp_c"]
    tiers = {f["category"]: f["tier"] for f in case["facts"]}
    assert tiers["presenting"] == "initial"
    assert tiers["social"] == "discoverable"
    assert any(f["tier"] == "reluctant" for f in case["facts"])
    assert all(f["source"]["kind"] == "faculty" and f["status"] == "draft" for f in case["facts"])
    assert [o["text"] for o in case["objectives"]] == ["Ask about adherence without judgment", "Agree on one realistic change"]
    gap_ids = {gap["id"] for gap in body["gaps"]}
    # Answered in the form, so the guided questions do not ask again.
    assert not gap_ids & {"name", "age", "reason_for_visit", "student_role", "goal", "chief_complaint", "allergies", "medications", "objectives"}

    opened = client.get(f"/api/studio/cases/{case['case_id']}")
    assert opened.status_code == 200
    assert opened.json()["case"]["profile"]["name"] == "Ray Ortiz"


def test_builder_rejects_a_short_description(client):
    got = client.post("/api/studio/builder", json={**FORM, "description": "short"})
    assert got.status_code == 422
