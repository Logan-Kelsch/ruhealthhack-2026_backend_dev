"""End, documentation, and debrief through the HTTP API.

These tests use the published golden cases offline. Expected scores, quotes, and
the discussion-aid sentence come from the encounter the test speaks and from the
official rubric file, not from the scorer's own arithmetic.
"""

import re

from fastapi.testclient import TestClient

from app import db as dbmod
from app import services
from app.db import Base
from app.main import app

# The sentence in the official rubric file. The shorter discussion-aid clause is inside it.
DISCUSSION_AID = (
    "Use the total as a discussion aid, not a pass/fail grade. "
    "A score of 1 in professionalism, safety, or clinical reasoning should trigger review even when the total is high."
)
REVIEW_DOMAIN_NAMES = {
    "Clinical reasoning and synthesis",
    "Professionalism, safety, and closure",
}


def _client(tmp_path, load_golden) -> TestClient:
    """SQLite API with the published golden cases and no live model calls."""
    dbmod.init_engine(f"sqlite:///{tmp_path / 'debrief.db'}")
    Base.metadata.create_all(dbmod.get_engine())
    with next(dbmod.get_session()) as session:
        for case_id in ("walter_greene", "alina_reyes", "eli_brooks"):
            services.upsert_golden(session, load_golden(case_id))
    return TestClient(app)


def _norm(text: str) -> str:
    """Compare a quote to the transcript without caring about case or extra space."""
    return re.sub(r"\s+", " ", text.lower()).strip(" .,!?;:\"'")


def _start(client: TestClient, case_id: str) -> str:
    """Open one encounter. Later reads must keep this id."""
    started = client.post("/api/encounters", json={"case_id": case_id, "student_name": "Sam"})
    assert started.status_code == 201
    return started.json()["encounter_id"]


def _ids(client: TestClient) -> list[str]:
    """Encounter ids that exist. Recovery must not add to this list."""
    listed = client.get("/api/encounters")
    assert listed.status_code == 200
    return [row["encounter_id"] for row in listed.json()]


def test_end_returns_the_case_template_and_does_not_start_another_encounter(tmp_path, load_golden):
    """Ending saves the visit and names the documentation template the case stored."""
    client = _client(tmp_path, load_golden)
    encounter_id = _start(client, "walter_greene")
    before = _ids(client)

    ended = client.post(f"/api/encounters/{encounter_id}/end")
    assert ended.status_code == 200
    body = ended.json()
    assert body["encounter_id"] == encounter_id
    assert body["status"] == "ended"
    assert body["documentation_template"] == {
        "id": "PES",
        "label": "PES statement (Problem, Etiology, Signs and symptoms)",
        "fields": [
            {"id": "problem", "label": "Problem", "hint": "The nutrition diagnosis"},
            {"id": "etiology", "label": "Etiology", "hint": "Related to: the cause"},
            {"id": "signs", "label": "Signs and symptoms", "hint": "As evidenced by: what you found"},
        ],
    }
    assert body["saved_documentation"] is None
    assert "trust" not in body
    assert "trust_timeline" not in body

    recovered = client.get(f"/api/encounters/{encounter_id}")
    assert recovered.status_code == 200
    assert recovered.json()["encounter_id"] == encounter_id
    assert recovered.json()["status"] == "ended"
    assert recovered.json()["documentation_template"]["id"] == "PES"
    assert _ids(client) == before

    missing = client.post("/api/encounters/missing-encounter/end")
    assert missing.status_code == 404
    assert missing.json()["message"] == "encounter missing-encounter not found"
    assert missing.json()["errors"] == []

    schema = app.openapi()["components"]["schemas"]
    assert "id" in schema["DocumentationTemplate"]["properties"]
    end_schema = app.openapi()["paths"]["/api/encounters/{enc_id}/end"]["post"]["responses"]
    assert end_schema["200"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/PublicEncounter"
    assert "404" in end_schema


def test_documentation_check_uses_the_disclosure_log_and_stays_saved(tmp_path, load_golden):
    """A number the visit never released is unsupported, and the missed fact keeps its id."""
    client = _client(tmp_path, load_golden)
    encounter_id = _start(client, "walter_greene")
    spoken = client.post(
        f"/api/encounters/{encounter_id}/utterances",
        json={"text": "Do you take anything over the counter for pain?"},
    )
    assert spoken.status_code == 200
    assert any(item["source_fact"] == "f_ibuprofen" for item in spoken.json()["chart_releases"])
    client.post(f"/api/encounters/{encounter_id}/end")

    submitted = client.post(
        f"/api/encounters/{encounter_id}/documentation",
        json={"fields": {"problem": "Blood pressure was 999 over 999.", "etiology": "", "signs": ""}},
    )
    assert submitted.status_code == 200
    check = submitted.json()["documentation"]
    assert check["method"] == "rule-based"
    assert any(
        "999" in claim["statement"] and claim["reason"] == "contains a number that did not come up in the encounter"
        for claim in check["unsupported"]
    )
    missed = next(item for item in check["missing"] if item["id"] == "f_ibuprofen")
    assert "ibuprofen" in missed["text"].lower()
    assert "999" not in missed["text"]

    feedback = client.get(f"/api/encounters/{encounter_id}/feedback")
    assert feedback.status_code == 200
    assert feedback.json()["documentation"]["unsupported"] == check["unsupported"]
    assert feedback.json()["documentation"]["missing"] == check["missing"]

    recovered = client.get(f"/api/encounters/{encounter_id}")
    assert recovered.status_code == 200
    assert recovered.json()["status"] == "complete"
    assert recovered.json()["encounter_id"] == encounter_id
    assert recovered.json()["saved_documentation"]["problem"] == "Blood pressure was 999 over 999."
    assert _ids(client) == [encounter_id]

    # A failed read of another encounter must not erase the note that was saved.
    missing = client.get("/api/encounters/missing-encounter/feedback")
    assert missing.status_code == 404
    assert missing.json()["message"] == "encounter missing-encounter not found"
    again = client.get(f"/api/encounters/{encounter_id}/feedback")
    assert again.json()["documentation"]["unsupported"] == check["unsupported"]
    assert client.get(f"/api/encounters/{encounter_id}").json()["saved_documentation"]["problem"].startswith("Blood pressure")

    paths = app.openapi()["paths"]
    documented = paths["/api/encounters/{enc_id}/documentation"]["post"]["responses"]
    assert documented["200"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/FeedbackResponse"
    assert documented["404"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/ErrorResponse"
    fetched = paths["/api/encounters/{enc_id}/feedback"]["get"]["responses"]
    assert fetched["200"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/FeedbackResponse"
    assert fetched["404"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/ErrorResponse"
    assert fetched["409"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/ErrorResponse"
    assert "unsupported" in app.openapi()["components"]["schemas"]["DocumentationCheck"]["properties"]


def test_rubric_cites_transcript_spans_and_flags_a_one_in_domain_six_or_seven(tmp_path, load_golden):
    """A scored domain quotes the student, and a 1 in domain 6 or 7 raises the review flag."""
    client = _client(tmp_path, load_golden)
    encounter_id = _start(client, "walter_greene")
    student = "Do you take anything over the counter for pain?"
    client.post(f"/api/encounters/{encounter_id}/utterances", json={"text": student})
    client.post(f"/api/encounters/{encounter_id}/end")
    feedback = client.post(
        f"/api/encounters/{encounter_id}/documentation",
        json={"fields": {"problem": "Asked about pain medicine.", "etiology": "", "signs": ""}},
    )
    assert feedback.status_code == 200
    rubric = feedback.json()["rubric"]
    assert len(rubric["domains"]) == 7
    assert rubric["max_total"] == 28
    assert rubric["interpretation"] == DISCUSSION_AID
    assert rubric["total"] <= 28
    transcript = {line["turn"]: f"{line['student']}\n{line['patient']}" for line in feedback.json()["transcript"]}
    numeric = []
    for domain in rubric["domains"]:
        assert domain["score"] in (1, 2, 3, 4, "N/A")
        if domain["score"] == "N/A":
            continue
        numeric.append(domain)
        assert domain["evidence"], domain["key"]
        for span in domain["evidence"]:
            spoken = transcript[span["turn"]]
            assert _norm(span["quote"]) in _norm(spoken)
            assert span["quote"]
    assert numeric
    assert rubric["review_flag"] is True
    assert REVIEW_DOMAIN_NAMES & set(rubric["review_reasons"])
    flagged = [domain for domain in rubric["domains"] if domain["id"] in (6, 7) and domain["score"] == 1]
    assert flagged
    assert flagged[0]["evidence"][0]["quote"]

    # Strengths, gaps, and safety text are the domain fields, and the lists below are present.
    assert "strength_demonstrated" in rubric["domains"][0]
    assert "important_gap_or_missed_opportunity" in rubric["domains"][0]
    assert "safety_or_accuracy_concern" in rubric["domains"][0]
    assert "elicited" in feedback.json()
    assert "metrics" in feedback.json()
    assert "open_questions" in feedback.json()["metrics"]
    found_ibuprofen = [
        item
        for objective in feedback.json()["elicited"]
        for item in objective["found"]
        if item["fact_id"] == "f_ibuprofen"
    ]
    assert found_ibuprofen and found_ibuprofen[0]["turn"] == 1


def test_a_score_without_a_transcript_is_not_a_number(tmp_path, load_golden):
    """Nothing was said, so a domain that cannot cite a span is N/A rather than 1 through 4."""
    client = _client(tmp_path, load_golden)
    encounter_id = _start(client, "walter_greene")
    active = client.get(f"/api/encounters/{encounter_id}/feedback")
    assert active.status_code == 409
    assert active.json()["message"] == "end the encounter first"
    assert active.json()["errors"] == []

    client.post(f"/api/encounters/{encounter_id}/end")
    feedback = client.post(
        f"/api/encounters/{encounter_id}/documentation",
        json={"fields": {"problem": "No findings.", "etiology": "", "signs": ""}},
    )
    assert feedback.status_code == 200
    domains = feedback.json()["rubric"]["domains"]
    assert any(domain["score"] == "N/A" for domain in domains)
    for domain in domains:
        if domain["score"] != "N/A":
            assert domain["evidence"]
    # The encounter is complete and still the only one.
    assert client.get(f"/api/encounters/{encounter_id}").json()["status"] == "complete"
    assert _ids(client) == [encounter_id]


def test_asking_about_suicidal_thoughts_is_a_communication_note(tmp_path, load_golden):
    """An abrupt suicide question is quoted in the debrief and does not lower trust."""
    client = _client(tmp_path, load_golden)
    encounter_id = _start(client, "alina_reyes")
    asked = "Are you having thoughts of suicide?"
    client.post(f"/api/encounters/{encounter_id}/utterances", json={"text": asked})
    ended = client.post(f"/api/encounters/{encounter_id}/end")
    assert "trust" not in ended.json()

    feedback = client.post(
        f"/api/encounters/{encounter_id}/documentation",
        json={"fields": {"subjective": "Asked about suicidal thoughts.", "objective": "", "assessment": "", "plan": ""}},
    )
    assert feedback.status_code == 200
    body = feedback.json()
    assert any("always the right thing to do" in note for note in body["communication_notes"])
    assert any("open question" in note for note in body["communication_notes"])
    for point in body["trust_timeline"]:
        for event in point["events"]:
            assert event["delta"] >= 0
            assert event["event"] != "blunt_sensitive_question"
            spoken = next(line for line in body["transcript"] if line["turn"] == event["turn"])
            combined = f"{spoken['student']}\n{spoken['patient']}"
            assert _norm(event["span"]) in _norm(combined)
    # The encounter view still hides the timeline. The debrief is where it appears.
    recovered = client.get(f"/api/encounters/{encounter_id}").json()
    assert "trust_timeline" not in recovered
    assert recovered["status"] == "complete"
