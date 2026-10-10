"""HTTP contracts for saving, approving, and auto-filling a case.

These tests use FastAPI's TestClient. A later read of the case is how a refresh
would see the save. They do not query the database.
"""

from fastapi.testclient import TestClient

from app import db as dbmod
from app import services
from app.db import Base
from app.main import app

DESCRIPTION = "A 58-year-old man with type 2 diabetes and high blood pressure."


def _client(tmp_path, load_golden) -> TestClient:
    """SQLite API client with the three golden cases already saved."""
    dbmod.init_engine(f"sqlite:///{tmp_path / 'case-edits.db'}")
    Base.metadata.create_all(dbmod.get_engine())
    with next(dbmod.get_session()) as session:
        for case_id in ("walter_greene", "alina_reyes", "eli_brooks"):
            services.upsert_golden(session, load_golden(case_id))
    return TestClient(app)


def test_edit_save_refresh_keeps_fact_identity_and_sources(tmp_path, load_golden):
    """A saved edit keeps the fact id, its source, its disclosure rule, and the objective that names it."""
    client = _client(tmp_path, load_golden)
    created = client.post("/api/studio/drafts", json={"description": DESCRIPTION})
    assert created.status_code == 201
    case = created.json()["case"]
    case_id = case["case_id"]

    case["title"] = "Jordan Hale: high sugars"
    case["profile"]["name"] = "Jordan Hale"
    case["profile"]["age"] = 72
    case["profile"]["occupation"] = "Bus driver"
    case["profile"]["personality"] = {
        "summary": "Speaks in short sentences.",
        "communication_style": "Direct",
        "traits": {"openness": 0.4, "irritability": 0.2, "verbosity": 0.3, "humor": 0.1},
        "health_literacy": "low",
        "mood": "worried",
        "example_lines": ["I just want the sugar to stop jumping around."],
    }
    case["briefing"] = {
        "setting": "Primary care clinic",
        "reason_for_visit": "High sugars",
        "goal": "Agree on one food change",
        "student_role": "Dietetics student",
        "show_doorway_vitals": True,
    }
    case["facts"] = [
        {
            "id": "f_headache",
            "category": "presenting",
            "text": "He has had a headache for three days.",
            "say": "My head has hurt for three days.",
            "tier": "reluctant",
            "unlock": {"topics": ["chief_complaint"], "min_trust": 2, "requires_facts": []},
            "source": {"kind": "faculty", "ref": "faculty interview", "by": "Dr Lee"},
            "status": "draft",
        }
    ]
    case["vitals"] = [
        {
            "key": "bp",
            "label": "Blood pressure",
            "value": "120/80",
            "unit": "mmHg",
            "source": {"kind": "faculty", "ref": "typed by faculty", "by": "Dr Lee"},
            "status": "draft",
        }
    ]
    case["labs"] = [
        {
            "id": "lab_na",
            "key": "na",
            "name": "Sodium",
            "value": 140,
            "unit": "mmol/L",
            "source": {"kind": "faculty", "ref": "outside lab", "by": "Dr Lee"},
            "status": "draft",
        }
    ]
    case["exam"] = [
        {
            "maneuver": "cardiac_auscultation",
            "finding": "Regular rate and rhythm, no murmur.",
            "abnormal": False,
            "source": {"kind": "faculty", "ref": None, "by": "Dr Lee"},
            "status": "draft",
        }
    ]
    case["diagnoses"] = [
        {
            "name": "Type 2 diabetes mellitus with hyperglycemia",
            "codes": [{"system": "ICD-10-CM", "code": "E11.65", "display": "Type 2 diabetes mellitus with hyperglycemia"}],
            "source": {"kind": "faculty", "ref": "icd10 lookup", "by": "Dr Lee"},
            "status": "draft",
        }
    ]
    case["medications"] = [
        {
            "name": "Metformin",
            "dose": "500 mg",
            "frequency": "twice daily",
            "purpose": "Blood sugar",
            "source": {"kind": "faculty", "ref": None, "by": "Dr Lee"},
            "status": "draft",
        }
    ]
    case["allergies"] = [
        {
            "substance": "Penicillin",
            "reaction": "Rash",
            "source": {"kind": "faculty", "ref": None, "by": "Dr Lee"},
            "status": "draft",
        }
    ]
    case["objectives"] = [
        {
            "id": "obj_headache",
            "text": "Ask when the headache started.",
            "expected_discoveries": ["f_headache"],
            "expected_actions": ["summarize"],
            "status": "draft",
        }
    ]

    saved = client.put(f"/api/studio/cases/{case_id}", json=case)
    assert saved.status_code == 200
    saved_body = saved.json()
    assert saved_body["status"] == "draft"
    assert saved_body["case"]["version"] == 1

    # A second edit changes the wording only. The id and the links stay put.
    edited = saved_body["case"]
    edited["facts"][0]["text"] = "He has had a headache for four days."
    resaved = client.put(f"/api/studio/cases/{case_id}", json=edited)
    assert resaved.status_code == 200

    opened = client.get(f"/api/studio/cases/{case_id}", params={"version": 1})
    assert opened.status_code == 200
    body = opened.json()
    assert body["status"] == "draft"
    stored = body["case"]
    assert stored["title"] == "Jordan Hale: high sugars"
    assert stored["profile"]["name"] == "Jordan Hale"
    assert stored["profile"]["age"] == 72
    assert stored["profile"]["occupation"] == "Bus driver"
    assert stored["profile"]["personality"]["summary"] == "Speaks in short sentences."
    assert stored["profile"]["personality"]["health_literacy"] == "low"
    assert stored["profile"]["personality"]["mood"] == "worried"
    assert stored["profile"]["personality"]["traits"]["openness"] == 0.4
    assert stored["profile"]["personality"]["example_lines"] == ["I just want the sugar to stop jumping around."]
    assert stored["briefing"]["setting"] == "Primary care clinic"
    assert stored["briefing"]["goal"] == "Agree on one food change"
    assert stored["briefing"]["student_role"] == "Dietetics student"
    fact = stored["facts"][0]
    assert fact["id"] == "f_headache"
    assert fact["text"] == "He has had a headache for four days."
    assert fact["tier"] == "reluctant"
    assert fact["unlock"]["topics"] == ["chief_complaint"]
    assert fact["unlock"]["min_trust"] == 2
    assert fact["source"] == {"kind": "faculty", "ref": "faculty interview", "by": "Dr Lee"}
    assert fact["status"] == "draft"
    assert stored["vitals"][0]["value"] == "120/80"
    assert stored["vitals"][0]["source"]["kind"] == "faculty"
    assert stored["labs"][0]["id"] == "lab_na"
    assert stored["labs"][0]["value"] == 140
    assert stored["labs"][0]["source"]["ref"] == "outside lab"
    assert stored["exam"][0]["maneuver"] == "cardiac_auscultation"
    assert stored["exam"][0]["finding"] == "Regular rate and rhythm, no murmur."
    assert stored["diagnoses"][0]["codes"][0]["code"] == "E11.65"
    assert stored["medications"][0]["name"] == "Metformin"
    assert stored["medications"][0]["dose"] == "500 mg"
    assert stored["allergies"][0]["substance"] == "Penicillin"
    assert stored["objectives"][0]["expected_discoveries"] == ["f_headache"]
    assert stored["objectives"][0]["status"] == "draft"

    save_schema = app.openapi()["paths"]["/api/studio/cases/{case_id}"]["put"]["responses"]["200"]
    assert save_schema["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/StudioCaseDetail"


def _draft_with_fact(client: TestClient) -> tuple[str, dict]:
    """Create a draft that already has one fact and an objective pointing at it."""
    created = client.post("/api/studio/drafts", json={"description": DESCRIPTION})
    assert created.status_code == 201
    case = created.json()["case"]
    case["profile"]["age"] = 72
    case["facts"] = [
        {
            "id": "f_headache",
            "text": "He has had a headache for three days.",
            "tier": "reluctant",
            "unlock": {"topics": ["chief_complaint"], "min_trust": 2, "requires_facts": []},
            "source": {"kind": "faculty", "ref": "faculty interview", "by": "Dr Lee"},
            "status": "draft",
        }
    ]
    case["objectives"] = [
        {
            "id": "obj_headache",
            "text": "Ask when the headache started.",
            "expected_discoveries": ["f_headache"],
            "expected_actions": ["summarize"],
            "status": "draft",
        }
    ]
    case["labs"] = [
        {
            "id": "lab_na",
            "key": "na",
            "name": "Sodium",
            "value": 140,
            "unit": "mmol/L",
            "source": {"kind": "faculty", "ref": "outside lab", "by": "Dr Lee"},
            "status": "draft",
        },
        {
            "id": "lab_cl",
            "key": "cl",
            "name": "Chloride",
            "value": 104,
            "unit": "mmol/L",
            "source": {"kind": "faculty", "ref": "outside lab", "by": "Dr Lee"},
            "status": "draft",
        },
        {
            "id": "lab_hco3",
            "key": "hco3",
            "name": "Bicarbonate",
            "value": 24,
            "unit": "mmol/L",
            "source": {"kind": "faculty", "ref": "outside lab", "by": "Dr Lee"},
            "status": "draft",
        },
        {
            "id": "lab_cr",
            "key": "cr",
            "name": "Creatinine",
            "value": 1.6,
            "unit": "mg/dL",
            "source": {"kind": "faculty", "ref": "outside lab", "by": "Dr Lee"},
            "status": "draft",
        },
    ]
    case["vitals"] = [
        {
            "key": "bp",
            "label": "Blood pressure",
            "value": "120/80",
            "unit": "mmHg",
            "source": {"kind": "faculty", "ref": "typed by faculty", "by": "Dr Lee"},
            "status": "draft",
        }
    ]
    saved = client.put(f"/api/studio/cases/{case['case_id']}", json=case)
    assert saved.status_code == 200
    return case["case_id"], saved.json()["case"]


def test_approval_and_return_to_draft_persist(tmp_path, load_golden):
    """Approving a fact, then returning it to draft, is what a refresh shows."""
    client = _client(tmp_path, load_golden)
    case_id, _case = _draft_with_fact(client)

    approved = client.post(
        f"/api/studio/cases/{case_id}/approve",
        json={"group": "facts", "keys": ["f_headache"], "status": "approved"},
    )
    assert approved.status_code == 200
    approved_fact = approved.json()["case"]["facts"][0]
    assert approved_fact["id"] == "f_headache"
    assert approved_fact["status"] == "approved"
    assert approved_fact["source"] == {"kind": "faculty", "ref": "faculty interview", "by": "Dr Lee"}
    # The lab was not in the request, so it stays a draft.
    assert approved.json()["case"]["labs"][0]["status"] == "draft"

    opened = client.get(f"/api/studio/cases/{case_id}")
    assert opened.status_code == 200
    assert opened.json()["case"]["facts"][0]["status"] == "approved"

    returned = client.post(
        f"/api/studio/cases/{case_id}/approve",
        json={"group": "facts", "keys": ["f_headache"], "status": "draft"},
    )
    assert returned.status_code == 200
    assert returned.json()["case"]["facts"][0]["status"] == "draft"
    refreshed = client.get(f"/api/studio/cases/{case_id}")
    assert refreshed.json()["case"]["facts"][0]["status"] == "draft"
    assert refreshed.json()["case"]["facts"][0]["text"] == "He has had a headache for three days."

    approve_schema = app.openapi()["paths"]["/api/studio/cases/{case_id}/approve"]["post"]["responses"]["200"]
    assert approve_schema["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/StudioCaseDetail"
    group = app.openapi()["components"]["schemas"]["Approve"]["properties"]["group"]
    assert "facts" in group["enum"]
    assert "branches" in group["enum"]


def test_deleting_a_referenced_fact_reports_the_reference_and_keeps_it(tmp_path, load_golden):
    """A save that drops a fact an objective still names fails, and the fact is still there afterward."""
    client = _client(tmp_path, load_golden)
    case_id, case = _draft_with_fact(client)
    case["facts"] = []
    rejected = client.put(f"/api/studio/cases/{case_id}", json=case)
    assert rejected.status_code == 409
    body = rejected.json()
    assert body["message"]
    assert any(item["loc"] == ["facts", "f_headache"] for item in body["errors"])
    assert any("obj_headache" in item["msg"] for item in body["errors"])

    opened = client.get(f"/api/studio/cases/{case_id}")
    assert opened.status_code == 200
    assert opened.json()["case"]["facts"][0]["id"] == "f_headache"
    assert opened.json()["case"]["objectives"][0]["expected_discoveries"] == ["f_headache"]


def test_autofill_proposes_values_without_replacing_faculty_entries(tmp_path, load_golden):
    """Auto-fill adds sourced drafts and leaves faculty numbers and the known formulas alone."""
    client = _client(tmp_path, load_golden)
    case_id, _case = _draft_with_fact(client)

    filled = client.post(f"/api/studio/cases/{case_id}/autofill", json={"panels": ["bmp", "a1c"], "vitals": True})
    assert filled.status_code == 200
    body = filled.json()
    assert body["status"] == "draft"
    labs = {lab["key"]: lab for lab in body["case"]["labs"]}
    assert labs["na"]["value"] == 140
    assert labs["na"]["source"]["kind"] == "faculty"
    assert labs["cr"]["value"] == 1.6
    assert labs["cr"]["source"]["kind"] == "faculty"
    # CKD-EPI 2021 for creatinine 1.6, age 72, male is 45. The unit test locks that input.
    assert labs["egfr"]["value"] == 45
    assert labs["egfr"]["source"]["kind"] == "computed"
    assert "CKD-EPI 2021" in labs["egfr"]["source"]["ref"]
    assert labs["egfr"]["status"] == "draft"
    # Anion gap is sodium minus chloride and bicarbonate: 140 - (104 + 24) = 12.
    assert labs["anion_gap"]["value"] == 12
    assert labs["anion_gap"]["source"]["kind"] == "computed"
    assert labs["a1c"]["source"]["kind"] == "rule"
    assert 7.0 <= labs["a1c"]["value"] <= 9.5
    assert labs["a1c"]["status"] == "draft"
    vitals = {vital["key"]: vital for vital in body["case"]["vitals"]}
    assert vitals["bp"]["value"] == "120/80"
    assert vitals["bp"]["source"]["kind"] == "faculty"
    assert any(vital["status"] == "draft" and vital["key"] == "hr" for vital in body["case"]["vitals"])
    assert "lab_na" not in body["added"]["labs"]
    assert "lab_egfr" in body["added"]["labs"]
    assert "bp" not in body["added"]["vitals"]
    assert "hr" in body["added"]["vitals"]
    assert any("diabetes" in note for note in body["notes"])

    opened = client.get(f"/api/studio/cases/{case_id}")
    refreshed = {lab["key"]: lab for lab in opened.json()["case"]["labs"]}
    assert refreshed["na"]["value"] == 140
    assert refreshed["egfr"]["value"] == 45

    schema = app.openapi()["components"]["schemas"]
    autofill_body = app.openapi()["paths"]["/api/studio/cases/{case_id}/autofill"]["post"]["responses"]["200"]
    assert autofill_body["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/StudioAutofillResult"
    assert set(schema["StudioAutofillResult"]["properties"]) == {"case", "status", "gaps", "blockers", "added", "notes"}
    assert schema["StudioAutofillResult"].get("additionalProperties") is not True
    assert set(schema["AutofillAdded"]["properties"]) == {"labs", "vitals"}
    added_labs = schema["AutofillAdded"]["properties"]["labs"]
    assert added_labs["items"]["type"] == "string"


def test_diagnosis_lookup_returns_the_local_catalog_match(tmp_path, load_golden):
    """The diagnosis search returns the existing offline match, not a made-up code."""
    client = _client(tmp_path, load_golden)
    found = client.get("/api/studio/lookup/icd10", params={"q": "E11.65"})
    assert found.status_code == 200
    assert found.json() == [
        {"code": "E11.65", "display": "Type 2 diabetes mellitus with hyperglycemia"},
    ]
    assert client.get("/api/studio/lookup/icd10", params={"q": "a"}).json() == []

    lookup_schema = app.openapi()["paths"]["/api/studio/lookup/icd10"]["get"]["responses"]["200"]
    assert lookup_schema["content"]["application/json"]["schema"]["items"]["$ref"] == "#/components/schemas/Icd10Match"
    match = app.openapi()["components"]["schemas"]["Icd10Match"]
    assert set(match["properties"]) == {"code", "display"}
    assert match.get("additionalProperties") is not True


def test_vocab_names_topics_actions_maneuvers_and_panels(tmp_path, load_golden):
    """The editor's closed lists are the catalog entries, each with the fields the screen shows."""
    client = _client(tmp_path, load_golden)
    response = client.get("/api/studio/vocab")
    assert response.status_code == 200
    body = response.json()
    greeting = next(item for item in body["topics"] if item["id"] == "greeting_introduction")
    assert greeting == {
        "id": "greeting_introduction",
        "description": "Student greets the patient or introduces themself and their role",
    }
    summarize = next(item for item in body["actions"] if item["id"] == "summarize")
    assert summarize == {
        "id": "summarize",
        "description": "Student summarizes what the patient said back to them",
    }
    appearance = next(item for item in body["maneuvers"] if item["id"] == "general_appearance")
    assert appearance == {
        "id": "general_appearance",
        "label": "General appearance (inspection)",
        "normal": "Alert, in no acute distress.",
    }
    assert "bmp" in body["lab_panels"]
    assert body["lab_panels"] == sorted(body["lab_panels"])

    schema = app.openapi()["components"]["schemas"]["StudioVocab"]
    assert set(schema["properties"]) == {"topics", "actions", "maneuvers", "lab_panels"}
    assert schema.get("additionalProperties") is not True
    vocab_body = app.openapi()["paths"]["/api/studio/vocab"]["get"]["responses"]["200"]
    assert vocab_body["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/StudioVocab"
    maneuver = app.openapi()["components"]["schemas"]["StudioVocabManeuver"]
    assert set(maneuver["properties"]) == {"id", "label", "normal"}
    assert maneuver.get("additionalProperties") is not True


def test_save_validation_and_autofill_failures_are_errors(tmp_path, load_golden):
    """A bad save or auto-fill stays an error, and the stored case is unchanged."""
    client = _client(tmp_path, load_golden)
    case_id, case = _draft_with_fact(client)

    mismatch = dict(case)
    mismatch["case_id"] = "someone_else"
    rejected = client.put(f"/api/studio/cases/{case_id}", json=mismatch)
    assert rejected.status_code == 422
    assert rejected.json()["message"] == "case_id in the body does not match the URL"
    assert "case" not in rejected.json()

    invalid = client.put(f"/api/studio/cases/{case_id}", json={"case_id": case_id, "profile": {"name": "Jordan", "age": "seventy"}})
    assert invalid.status_code == 422
    assert invalid.json()["errors"]
    assert any("age" in [str(part) for part in item["loc"]] for item in invalid.json()["errors"])

    missing = client.post("/api/studio/cases/missing_case/autofill", json={"panels": ["bmp"], "vitals": True})
    assert missing.status_code == 404
    assert missing.json()["message"]
    assert "added" not in missing.json()

    bad_panels = client.post(f"/api/studio/cases/{case_id}/autofill", json={"panels": "bmp"})
    assert bad_panels.status_code == 422
    assert "added" not in bad_panels.json()

    opened = client.get(f"/api/studio/cases/{case_id}")
    assert opened.status_code == 200
    assert opened.json()["case"]["facts"][0]["text"] == "He has had a headache for three days."
    assert {lab["key"] for lab in opened.json()["case"]["labs"]} == {"na", "cl", "hco3", "cr"}
