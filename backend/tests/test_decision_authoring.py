"""HTTP contracts for authored visits, decision points, and outcomes.

A later read is what a refresh would show. These tests do not query the database.
"""

from fastapi.testclient import TestClient

from app import db as dbmod
from app import services
from app.db import Base
from app.main import app

DESCRIPTION = "A 58-year-old man with type 2 diabetes and high blood pressure."


def _client(tmp_path, load_golden) -> TestClient:
    """SQLite API client with the golden cases already saved."""
    dbmod.init_engine(f"sqlite:///{tmp_path / 'decision-authoring.db'}")
    Base.metadata.create_all(dbmod.get_engine())
    with next(dbmod.get_session()) as session:
        for case_id in ("walter_greene", "alina_reyes", "eli_brooks"):
            services.upsert_golden(session, load_golden(case_id))
    return TestClient(app)


def _draft(client: TestClient) -> tuple[str, dict]:
    """A synthetic draft whose one fact can be named by a predicate."""
    created = client.post("/api/studio/drafts", json={"description": DESCRIPTION})
    assert created.status_code == 201
    case = created.json()["case"]
    case["facts"] = [
        {
            "id": "f_headache",
            "text": "He has had a headache for three days.",
            "tier": "discoverable",
            "unlock": {"topics": ["chief_complaint"], "requires_facts": []},
            "source": {"kind": "faculty", "ref": "faculty interview", "by": "Dr Lee"},
            "status": "draft",
        }
    ]
    case["actions"] = [
        {
            "id": "counsel_headache",
            "description": "Explains the headache plan in plain words",
            "keywords": [],
        }
    ]
    return case["case_id"], case


def _covered_visits() -> list[dict]:
    """Two visits whose yes/no results each have a faculty-written outcome."""
    return [
        {
            "id": "v1",
            "label": "First visit",
            "day": 0,
            "changes": {
                "mood": "worried",
                "briefing": {
                    "setting": "Primary care clinic",
                    "reason_for_visit": "Headache follow-up",
                    "goal": "Check the new symptom",
                    "student_role": "Medical student",
                    "show_doorway_vitals": True,
                },
                "vitals": [
                    {
                        "key": "bp",
                        "label": "Blood pressure",
                        "value": "128/82",
                        "unit": "mmHg",
                        "status": "draft",
                        "source": {"kind": "faculty", "ref": None, "by": "Dr Lee"},
                    }
                ],
            },
            "decision_points": [
                {
                    "id": "dp_story",
                    "label": "Asked why he came in and examined him",
                    "affects": "patient",
                    "predicate": {
                        "all": [
                            {"topic": "chief_complaint"},
                            {"maneuver": "cardiac_auscultation"},
                            {"order": "bmp"},
                            {"fact_disclosed": "f_headache"},
                            {"not": {"action": "prescribe_antibiotic"}},
                            {
                                "before": [
                                    {"open_question": True},
                                    {"action": "counsel_headache"},
                                ]
                            },
                        ]
                    },
                },
                {
                    "id": "dp_summary",
                    "label": "Summarized the story",
                    "affects": "patient",
                    "predicate": {"any": [{"action": "summarize"}, {"topic": "chief_complaint"}]},
                },
            ],
            "branches": [
                {
                    "id": "b_yes",
                    "label": "Headache improving",
                    "when": {"dp_story": True},
                    "summary": "The headache is better at the next visit.",
                    "tag": "common",
                    "status": "draft",
                    "changes": {
                        "add_facts": [
                            {
                                "id": "f_better",
                                "text": "The headache is better.",
                                "say": "My head is better.",
                                "status": "draft",
                                "source": {"kind": "faculty", "by": "Dr Lee"},
                            }
                        ],
                        "update_facts": {
                            "f_headache": {
                                "text": "The headache has lasted two weeks.",
                                "tier": "discoverable",
                            }
                        },
                    },
                },
                {
                    "id": "b_no",
                    "label": "Reason still unclear",
                    "when": {"dp_story": False},
                    "summary": "The reason for the visit is still unclear.",
                    "tag": "rare",
                    "status": "draft",
                },
            ],
        },
        {
            "id": "v2",
            "label": "Follow-up",
            "day": 14,
            "changes": {"mood": "calmer"},
            "decision_points": [],
            "branches": [],
        },
    ]


def test_predicate_contract_names_supported_operators():
    """The case contract lists the operators. A free-form object is not the predicate."""
    schema = app.openapi()["components"]["schemas"]
    predicate = schema["Predicate"]
    assert predicate.get("additionalProperties") is False
    assert set(predicate["properties"]) == {
        "topic",
        "action",
        "maneuver",
        "order",
        "fact_disclosed",
        "open_question",
        "any",
        "all",
        "not",
        "before",
    }
    point = schema["DecisionPoint"]["properties"]["predicate"]
    assert point["$ref"] == "#/components/schemas/Predicate"
    patch = schema["FactPatch"]
    assert patch.get("additionalProperties") is False
    assert "text" in patch["properties"]
    update = schema["VisitChanges"]["properties"]["update_facts"]
    assert update["additionalProperties"]["$ref"] == "#/components/schemas/FactPatch"


def test_authored_visits_round_trip(tmp_path, load_golden):
    """Save and read back visit ids, labels, time gaps, changes, decision points, and outcomes."""
    client = _client(tmp_path, load_golden)
    case_id, case = _draft(client)
    case["visits"] = _covered_visits()

    saved = client.put(f"/api/studio/cases/{case_id}", json=case)
    assert saved.status_code == 200
    assert saved.json()["status"] == "draft"

    opened = client.get(f"/api/studio/cases/{case_id}", params={"version": 1})
    assert opened.status_code == 200
    visits = opened.json()["case"]["visits"]
    assert [visit["id"] for visit in visits] == ["v1", "v2"]
    assert visits[0]["label"] == "First visit"
    assert visits[0]["day"] == 0
    assert visits[1]["label"] == "Follow-up"
    assert visits[1]["day"] == 14
    assert visits[0]["changes"]["mood"] == "worried"
    assert visits[0]["changes"]["briefing"]["reason_for_visit"] == "Headache follow-up"
    assert visits[0]["changes"]["vitals"][0]["value"] == "128/82"
    assert visits[0]["changes"]["vitals"][0]["status"] == "draft"
    assert visits[1]["changes"]["mood"] == "calmer"
    story = visits[0]["decision_points"][0]
    assert story["id"] == "dp_story"
    assert story["predicate"] == {
        "all": [
            {"topic": "chief_complaint"},
            {"maneuver": "cardiac_auscultation"},
            {"order": "bmp"},
            {"fact_disclosed": "f_headache"},
            {"not": {"action": "prescribe_antibiotic"}},
            {"before": [{"open_question": True}, {"action": "counsel_headache"}]},
        ]
    }
    assert visits[0]["decision_points"][1]["predicate"] == {
        "any": [{"action": "summarize"}, {"topic": "chief_complaint"}]
    }
    outcome = visits[0]["branches"][0]
    assert outcome["id"] == "b_yes"
    assert outcome["label"] == "Headache improving"
    assert outcome["when"] == {"dp_story": True}
    assert outcome["summary"] == "The headache is better at the next visit."
    assert outcome["tag"] == "common"
    assert outcome["status"] == "draft"
    assert outcome["changes"]["add_facts"][0]["id"] == "f_better"
    assert outcome["changes"]["add_facts"][0]["status"] == "draft"
    assert outcome["changes"]["update_facts"] == {
        "f_headache": {"text": "The headache has lasted two weeks.", "tier": "discoverable"}
    }
    assert visits[0]["branches"][1]["status"] == "draft"


def test_free_text_does_not_become_a_predicate(tmp_path, load_golden):
    """A sentence in place of an operator is rejected and is not stored."""
    client = _client(tmp_path, load_golden)
    case_id, case = _draft(client)
    case["visits"] = _covered_visits()
    assert client.put(f"/api/studio/cases/{case_id}", json=case).status_code == 200

    case["visits"][0]["decision_points"][0]["predicate"] = {
        "note": "asked about mania in their own words"
    }
    rejected = client.put(f"/api/studio/cases/{case_id}", json=case)
    assert rejected.status_code == 422
    assert rejected.json()["errors"]
    assert "asked about mania in their own words" not in rejected.text

    opened = client.get(f"/api/studio/cases/{case_id}")
    assert opened.status_code == 200
    stored = opened.json()["case"]["visits"][0]["decision_points"][0]["predicate"]
    assert stored["all"][0] == {"topic": "chief_complaint"}
    assert "asked about mania in their own words" not in opened.text


def test_unknown_vocabulary_and_dangling_references_are_rejected(tmp_path, load_golden):
    """Topic, fact, outcome, and fact-change ids must already exist. A bad save is not stored."""
    client = _client(tmp_path, load_golden)
    case_id, case = _draft(client)
    case["visits"] = _covered_visits()
    assert client.put(f"/api/studio/cases/{case_id}", json=case).status_code == 200

    unknown_topic = _covered_visits()
    unknown_topic[0]["decision_points"][1]["predicate"] = {"topic": "not_a_topic"}
    case["visits"] = unknown_topic
    rejected = client.put(f"/api/studio/cases/{case_id}", json=case)
    assert rejected.status_code == 422
    assert "not_a_topic" in rejected.json()["message"]

    dangling_fact = _covered_visits()
    dangling_fact[0]["decision_points"][1]["predicate"] = {"fact_disclosed": "f_missing"}
    case["visits"] = dangling_fact
    rejected = client.put(f"/api/studio/cases/{case_id}", json=case)
    assert rejected.status_code == 422
    assert "f_missing" in rejected.json()["message"]

    dangling_when = _covered_visits()
    dangling_when[0]["branches"][0]["when"] = {"missing_dp": True}
    case["visits"] = dangling_when
    rejected = client.put(f"/api/studio/cases/{case_id}", json=case)
    assert rejected.status_code == 422
    assert "missing_dp" in rejected.json()["message"]

    dangling_prior = _covered_visits()
    dangling_prior[0]["branches"][0]["after_branches"] = ["missing_branch"]
    case["visits"] = dangling_prior
    rejected = client.put(f"/api/studio/cases/{case_id}", json=case)
    assert rejected.status_code == 422
    assert "missing_branch" in rejected.json()["message"]

    invented_patch = _covered_visits()
    invented_patch[0]["branches"][0]["changes"]["update_facts"] = {"f_headache": {"guess": "worse"}}
    case["visits"] = invented_patch
    rejected = client.put(f"/api/studio/cases/{case_id}", json=case)
    assert rejected.status_code == 422

    opened = client.get(f"/api/studio/cases/{case_id}")
    assert opened.json()["case"]["visits"][0]["decision_points"][1]["predicate"] == {
        "any": [{"action": "summarize"}, {"topic": "chief_complaint"}]
    }


def test_decision_point_count_and_missing_outcomes_are_rejected(tmp_path, load_golden):
    """A visit has 2 to 4 decision points, and a later visit needs an outcome for every result."""
    client = _client(tmp_path, load_golden)
    case_id, case = _draft(client)
    case["visits"] = _covered_visits()
    assert client.put(f"/api/studio/cases/{case_id}", json=case).status_code == 200

    one_point = _covered_visits()
    one_point[0]["decision_points"] = one_point[0]["decision_points"][:1]
    case["visits"] = one_point
    rejected = client.put(f"/api/studio/cases/{case_id}", json=case)
    assert rejected.status_code == 422
    assert "2 to 4" in rejected.json()["message"]

    too_many = _covered_visits()
    extra = []
    for index in range(5):
        extra.append(
            {
                "id": f"dp_{index}",
                "label": f"Point {index}",
                "affects": "score",
                "predicate": {"action": "summarize"},
            }
        )
    too_many[0]["decision_points"] = extra
    case["visits"] = too_many
    rejected = client.put(f"/api/studio/cases/{case_id}", json=case)
    assert rejected.status_code == 422
    assert "2 to 4" in rejected.json()["message"]

    # The follow-up exists, so the first visit cannot leave a yes or no without an outcome.
    uncovered = _covered_visits()
    uncovered[0]["branches"] = [uncovered[0]["branches"][0]]
    case["visits"] = uncovered
    rejected = client.put(f"/api/studio/cases/{case_id}", json=case)
    assert rejected.status_code == 422
    assert "does not cover" in rejected.json()["message"]

    opened = client.get(f"/api/studio/cases/{case_id}")
    assert len(opened.json()["case"]["visits"][0]["branches"]) == 2


def test_last_visit_can_score_without_an_invented_outcome(tmp_path, load_golden):
    """The last visit may record decision points without a generated next state."""
    client = _client(tmp_path, load_golden)
    case_id, case = _draft(client)
    case["visits"] = [
        {
            "id": "v1",
            "label": "Only visit",
            "day": 0,
            "decision_points": [
                {
                    "id": "dp_one",
                    "label": "Asked why he came in",
                    "affects": "patient",
                    "predicate": {"topic": "chief_complaint"},
                },
                {
                    "id": "dp_two",
                    "label": "Summarized the story",
                    "affects": "score",
                    "predicate": {"action": "summarize"},
                },
            ],
            "branches": [],
        }
    ]
    saved = client.put(f"/api/studio/cases/{case_id}", json=case)
    assert saved.status_code == 200
    opened = client.get(f"/api/studio/cases/{case_id}")
    assert opened.json()["case"]["visits"][0]["branches"] == []
    assert len(opened.json()["case"]["visits"][0]["decision_points"]) == 2


def test_outcome_and_clinical_changes_stay_draft_until_approved(tmp_path, load_golden):
    """Saving an outcome does not approve it. Approval is a separate faculty action."""
    client = _client(tmp_path, load_golden)
    case_id, case = _draft(client)
    case["visits"] = _covered_visits()
    saved = client.put(f"/api/studio/cases/{case_id}", json=case)
    assert saved.status_code == 200
    stored = saved.json()["case"]["visits"][0]
    assert stored["branches"][0]["status"] == "draft"
    assert stored["branches"][0]["changes"]["add_facts"][0]["status"] == "draft"
    assert stored["changes"]["vitals"][0]["status"] == "draft"

    approved = client.post(
        f"/api/studio/cases/{case_id}/approve",
        json={"group": "branches", "keys": ["b_yes"], "status": "approved"},
    )
    assert approved.status_code == 200
    outcome = approved.json()["case"]["visits"][0]["branches"][0]
    assert outcome["status"] == "approved"
    assert outcome["changes"]["add_facts"][0]["status"] == "approved"
    # The other outcome was not in the request.
    assert approved.json()["case"]["visits"][0]["branches"][1]["status"] == "draft"
    # A visit change is not approved by approving an outcome.
    assert approved.json()["case"]["visits"][0]["changes"]["vitals"][0]["status"] == "draft"

    visit_approved = client.post(
        f"/api/studio/cases/{case_id}/approve",
        json={"group": "visit_changes", "keys": ["v1"], "status": "approved"},
    )
    assert visit_approved.status_code == 200
    body = visit_approved.json()["case"]["visits"][0]
    assert body["changes"]["vitals"][0]["status"] == "approved"
    assert body["branches"][1]["status"] == "draft"

    opened = client.get(f"/api/studio/cases/{case_id}")
    refreshed = opened.json()["case"]["visits"][0]
    assert refreshed["branches"][0]["status"] == "approved"
    assert refreshed["branches"][0]["changes"]["add_facts"][0]["text"] == "The headache is better."
    assert refreshed["changes"]["vitals"][0]["status"] == "approved"


def test_a_fact_named_by_a_decision_point_cannot_be_deleted(tmp_path, load_golden):
    """Removing a fact that a predicate still checks fails, and the fact remains."""
    client = _client(tmp_path, load_golden)
    case_id, case = _draft(client)
    case["visits"] = _covered_visits()
    assert client.put(f"/api/studio/cases/{case_id}", json=case).status_code == 200

    case["facts"] = []
    rejected = client.put(f"/api/studio/cases/{case_id}", json=case)
    assert rejected.status_code == 409
    assert any("dp_story" in item["msg"] for item in rejected.json()["errors"])

    opened = client.get(f"/api/studio/cases/{case_id}")
    assert opened.json()["case"]["facts"][0]["id"] == "f_headache"


def test_golden_cases_still_save(tmp_path, load_golden):
    """The reviewed cases already follow the visit rules, so saving them again keeps the tree."""
    client = _client(tmp_path, load_golden)
    for case_id in ("walter_greene", "alina_reyes", "eli_brooks"):
        opened = client.get(f"/api/studio/cases/{case_id}")
        assert opened.status_code == 200
        case = opened.json()["case"]
        saved = client.put(f"/api/studio/cases/{case_id}", json=case)
        assert saved.status_code == 200, saved.text
        again = client.get(f"/api/studio/cases/{case_id}")
        assert [visit["id"] for visit in again.json()["case"]["visits"]] == [visit["id"] for visit in case["visits"]]
        assert again.json()["case"]["visits"][0]["decision_points"][0]["id"] == case["visits"][0]["decision_points"][0]["id"]
