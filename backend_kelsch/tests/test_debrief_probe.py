"""Source integrity, uncertainty and branch behavior in authored probes."""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from backend_kelsch.app.debrief_probe.evaluation import (
    ROOT, audit_claims, evaluate_scenario, import_reviews, na_probe, review_queue,
    run_all, span_ref,
)
from app.schemas.case import Case


def test_all_case_claims_have_exact_sources_and_replay():
    report, records = run_all()
    assert {r["case_id"] for r in records} == {"walter_greene", "alina_reyes", "eli_brooks"}
    assert report["counts"]["authored_scenarios"] == len(records) == 6
    assert report["counts"]["branches_replayed"] == report["counts"]["branch_replay_denominator"] == 4
    assert report["counts"]["evidence_audit_denominator"] >= report["counts"]["claims"] > 0
    assert all(r["faculty_approved_scores"] is None for r in records)
    assert all(c.get("faculty_score") is None for r in records for c in r["claims"])
    assert report["gates"]["trained_action_extraction"] == "NOT EVALUABLE"


def test_tampered_transcript_offset_and_fact_source_rejected():
    r = evaluate_scenario("walter_greene", "authored")
    case = Case.model_validate_json((ROOT / "cases/walter_greene.json").read_text())
    claim = next(c for c in r["claims"] if c["kind"] == "explicit_fixture_action")
    broken = deepcopy(claim)
    broken["evidence"][0]["start"] += 1
    with pytest.raises(ValueError, match="span does not match"):
        audit_claims([broken], r["transcript"], r["note"], case, r["case_source"])
    fact_claim = next(c for c in r["claims"] if c["kind"] == "disclosed_source_fact")
    broken = deepcopy(fact_claim)
    broken["evidence"][0]["case_sha256"] = "wrong"
    with pytest.raises(ValueError, match="source changed"):
        audit_claims([broken], r["transcript"], r["note"], case, r["case_source"])


def test_absent_evidence_is_not_an_action_and_safety_flags_are_review_only():
    r = evaluate_scenario("walter_greene", "absent")
    assert not [c for c in r["claims"] if c["kind"] == "explicit_fixture_action"]
    assert r["branch"]["taken_id"] == "b_nsaid_missed"
    assert 6 in r["safety_review_domain_ids"] and 7 in r["safety_review_domain_ids"]
    assert all(c["evidence"] for c in r["claims"] if c["kind"] == "faculty_safety_review_flag")


def test_low_confidence_and_conflicting_actions_do_not_become_suggestions():
    low = evaluate_scenario("walter_greene", "low_confidence")
    assert "dp_nsaid" in low["branch"]["uncertain_predicates"]
    assert any(c.get("review_status") == "low_confidence_review" for c in low["claims"])
    assert not any(c["kind"] == "rubric_suggestion" and c["domain_key"] == "explanation_and_shared_decisions" for c in low["claims"])
    clash = evaluate_scenario("eli_brooks", "conflicting")
    assert clash["branch"]["taken_id"] == "b_abx"
    assert "conflicting_antibiotic_actions" in clash["branch"]["uncertain_predicates"]
    assert not any(c["kind"] == "rubric_suggestion" and c["domain_key"] == "explanation_and_shared_decisions" for c in clash["claims"])


def test_documentation_numeric_discrepancy_is_exact_note_span():
    r = evaluate_scenario("eli_brooks", "authored", note={"assessment": "Temperature 98765."})
    discrepancies = [c for c in r["claims"] if c["kind"] == "documentation_unbacked_number"]
    assert discrepancies and discrepancies[0]["evidence"][0]["quote"] == "Temperature 98765."
    assert r["documentation_method"] == "rule-based"
    assert na_probe()["observed"] == "N/A"


def test_review_import_requires_independent_complete_source_locked_reviews(tmp_path):
    _, records = run_all()
    queue = review_queue(records)
    file = tmp_path / "reviews.jsonl"
    file.write_text(json.dumps({**queue[0], "review_status": "approved", "reviewer_role": "faculty",
                               "reviewer_id": "faculty-pseudonym", "reviewed_at": "2026-10-10T00:00:00Z",
                               "expected_supported": True}) + "\n")
    assert import_reviews(file, records)["feedback_accuracy"] is None
    row = json.loads(file.read_text())
    row["case_sha256"] = "tampered"
    file.write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="source mismatch"):
        import_reviews(file, records)
    row["case_sha256"] = queue[0]["case_sha256"]
    row["reviewer_role"] = "script"
    file.write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="independent faculty"):
        import_reviews(file, records)


def test_absent_quote_cannot_be_linked():
    with pytest.raises(ValueError, match="unanchored"):
        span_ref(1, "student", "A real turn", "invented words")
