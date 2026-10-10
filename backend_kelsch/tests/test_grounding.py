"""Notebook 04 tests distinguish authored mechanics from reviewed evaluation."""
import json

import pytest

from backend_kelsch.app.grounding.evaluation import (
    _case, challenges, check_challenges, encounter_runs, export_review_queue,
    load_reviews, release_metrics, scripts, semantic_metrics,
)
from backend_kelsch.scripts.eval_grounding import evaluate


def test_all_case_level_preset_runs_replay_and_guarded_safety():
    runs, evidence = encounter_runs()
    assert len(runs) == 27
    assert evidence["counts"]["replay_matches"] == 27
    assert evidence["counts"]["invariant_violations"] == 0, evidence["violations"]
    assert {r["case_id"] for r in runs} == {"walter_greene", "alina_reyes", "eli_brooks"}
    assert {r["level"] for r in runs} == {"novice", "competent", "expert"}
    assert all(r["case_source"]["sha256"] and r["case_version"] for r in runs)
    assert all(t["expected_disclosures"] is None and t["verifier"]["fallback_used"]
               for r in runs for t in r["turns"])


def test_adversarial_requests_do_not_introduce_fact_or_student_label():
    runs, _ = encounter_runs()
    for r in runs:
        assert any("98765" in t["utterance"] for t in r["turns"] if r["level"] != "expert") or r["level"] == "expert"
        assert all("98765" not in t["reply"] for t in r["turns"])
        assert all(t["intent_origin"] == "authored_fixture" for t in r["turns"])
    novice = next(r for r in runs if r["script_id"] == "walter_greene:novice:typical")
    assert novice["turns"][2]["is_repeat"]
    assert "f_scared_future" not in novice["turns"][1]["allowed_fact_ids"]


def test_verifier_challenges_and_unchecked_prose():
    rows = challenges()
    result = check_challenges(rows)
    assert result["counts"]["mechanical_blocks"] == result["counts"]["mechanical_block_attempts"] == 9
    assert result["counts"]["mechanical_supported_passed"] == 3
    prose = [r for r in rows if r["kind"] == "unsupported_prose"]
    assert len(prose) == 3 and all(not r["deterministic_blocked"] for r in prose)
    assert all(r["review_status"] == "pending" and r["faculty_expected_supported"] is None for r in rows)
    assert all(r["llm_judge"]["status"] == "NOT RUN" for r in rows)


def test_review_queue_and_provenance_enforced(tmp_path):
    runs, _ = encounter_runs()
    rows = challenges()
    queue = tmp_path / "queue.jsonl"
    export_review_queue(queue, runs, rows)
    data = [json.loads(x) for x in queue.read_text().splitlines()]
    assert len(data) == sum(len(r["turns"]) for r in runs) + len(rows)
    assert all(x["review_status"] == "pending" for x in data)
    with pytest.raises(ValueError, match="independent"):
        load_reviews(queue, runs, rows)
    first = data[0]
    first.update(review_status="approved", reviewer_role="faculty", reviewer_id="reviewer-a",
                 reviewed_at="2026-10-10", expected_fact_ids=[])
    queue.write_text(json.dumps(first) + "\n")
    partial = load_reviews(queue, runs, rows)
    assert partial["reviewed_release_turns"] == 1 and not partial["release_complete"]
    assert release_metrics(runs, partial) is None
    first["case_sha256"] = "tampered"
    queue.write_text(json.dumps(first) + "\n")
    with pytest.raises(ValueError, match="hash/version"):
        load_reviews(queue, runs, rows)
    first["case_sha256"] = runs[0]["case_source"]["sha256"]
    first["reviewer_id"] = "notebook04_script"
    queue.write_text(json.dumps(first) + "\n")
    with pytest.raises(ValueError, match="independent"):
        load_reviews(queue, runs, rows)


def test_metrics_denominators_and_unreviewed_gate():
    report, trace = evaluate()
    assert report["gates"]["offline_mechanics"] == "PASS"
    assert report["gates"]["reviewed_disclosure_accuracy"] == "NOT EVALUABLE"
    assert report["disclosure_metrics"] is None
    assert report["mechanics"]["offline_template_rate"]["denominator"] == 189
    assert len(trace["runs"]) == 27
    assert semantic_metrics(trace["challenges"], {"semantic_complete": False}) is None
    synthetic = [{"script_id": "unit", "turns": [{"turn": 1, "allowed_fact_ids": ["a", "b"]}]}]
    reviews = {"release_complete": True, "releases": {("unit", 1): ["a", "c"]}}
    score = release_metrics(synthetic, reviews)
    assert (score["tp"], score["fp"], score["fn"]) == (1, 1, 1)
    assert score["precision"] == score["recall"] == 0.5
