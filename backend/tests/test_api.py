"""End-to-end through HTTP on SQLite, offline: seed, encounter, debrief, next visit, Studio."""
import pytest
from fastapi.testclient import TestClient

from app import db as dbmod
from app import services
from app.db import Base


@pytest.fixture
def client(tmp_path, load_golden):
    dbmod.init_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(dbmod.get_engine())
    with next(dbmod.get_session()) as s:
        for cid in ("walter_greene", "alina_reyes", "eli_brooks"):
            services.upsert_golden(s, load_golden(cid))
    from app.main import app

    return TestClient(app)


def test_student_case_list_hides_facts(client):
    cases = client.get("/api/cases").json()
    assert {c["case_id"] for c in cases} == {"walter_greene", "alina_reyes", "eli_brooks"}
    assert "facts" not in str(cases[0].keys())


def test_full_encounter_and_next_visit(client):
    enc = client.post("/api/encounters", json={"case_id": "walter_greene", "student_name": "Sam"}).json()
    eid = enc["encounter_id"]
    assert enc["visit_id"] == "v1" and enc["has_next_visit"]
    r = client.post(f"/api/encounters/{eid}/utterances", json={"text": "Do you take anything over the counter for pain?"}).json()
    assert r["reply_text"] and r["mode"] == "template"
    assert client.post(f"/api/encounters/{eid}/utterances", json={"text": ""}).status_code == 422

    assert client.post(f"/api/encounters/{eid}/end").json()["status"] == "ended"
    assert client.post(f"/api/encounters/{eid}/utterances", json={"text": "hello"}).status_code == 409
    fb = client.post(f"/api/encounters/{eid}/documentation", json={"fields": {"subjective": "Takes ibuprofen for knee pain."}}).json()
    assert fb["rubric"]["total"] is not None and fb["transcript"]
    assert fb["decision_path"]["taken"]

    nxt = client.post("/api/encounters", json={"case_id": "walter_greene", "previous_encounter_id": eid})
    assert nxt.status_code == 201 and nxt.json()["visit_id"] == "v2"


def test_unknown_ids(client):
    assert client.get("/api/encounters/nope").status_code == 404
    assert client.post("/api/encounters", json={"case_id": "walter_greene", "visit_id": "v9"}).status_code == 404
    assert client.post("/api/encounters", json={"case_id": "nobody"}).status_code == 404


def test_tts_without_key_falls_back(client):
    assert client.post("/api/tts", json={"text": "Hello."}).status_code == 204


def test_studio_draft_to_publish(client):
    d = client.post("/api/studio/drafts", json={"description": "A 58-year-old man with type 2 diabetes and high blood pressure."}).json()
    cid = d["case"]["case_id"]
    assert d["gaps"] and d["blockers"]
    assert client.post(f"/api/studio/cases/{cid}/publish").status_code == 409

    filled = client.post(f"/api/studio/cases/{cid}/autofill", json={"panels": ["bmp", "a1c"]}).json()
    assert filled["added"]["labs"] and all(lab["source"]["kind"] in ("rule", "reference", "computed") for lab in filled["case"]["labs"])
    before = len(filled["case"]["facts"])
    after = client.post(f"/api/studio/cases/{cid}/intake", json={"gap_id": "chief_complaint", "text": "My sugars have been running high."}).json()
    assert len(after["case"]["facts"]) == before + 1

    approved = client.post(f"/api/studio/cases/{cid}/approve", json={"group": "labs"}).json()
    assert all(lab["status"] == "approved" for lab in approved["case"]["labs"])

    run = client.post("/api/studio/cases/walter_greene/preview", json={"level": "expert"}).json()
    assert run["grounding"]["replies_failing_audit"] == 0


def test_editing_published_case_starts_new_version(client):
    full = client.get("/api/studio/cases/eli_brooks").json()
    case = full["case"]
    case["title"] = case["title"] + " (edited)"
    saved = client.put("/api/studio/cases/eli_brooks", json=case).json()
    assert saved["status"] == "draft" and saved["case"]["version"] == case["version"] + 1
    # Students still get the published version.
    assert client.get("/api/cases/eli_brooks").json()["version"] == case["version"]


def test_config_and_vocab(client):
    cfg = client.get("/api/config").json()
    assert cfg["llm"] is False and cfg["stt_provider"] == "browser"
    v = client.get("/api/studio/vocab").json()
    assert v["topics"] and v["maneuvers"]
