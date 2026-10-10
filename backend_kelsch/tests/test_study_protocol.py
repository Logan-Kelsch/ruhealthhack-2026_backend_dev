"""Toy-only validation fixtures; they are never reported as learner observations."""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from backend_kelsch.app.study.analysis import planning_n_per_arm, quadratic_kappa, wilson
from backend_kelsch.app.study.protocol import digest, lock_manifest, make_packets, split_audit, validate_corpus
from backend_kelsch.app.study.review import _answer, action_annotations, load_reviews
from backend_kelsch.scripts.eval_study import evaluate


def _toy_corpus(lock):
    cases = ("walter_greene", "alina_reyes", "eli_brooks")
    conversations = []
    for i, case in enumerate(cases):
        turns = [{"turn_id": "t1", "speaker": "student", "text": f"Toy question for {case}?"},
                 {"turn_id": "t2", "speaker": "patient", "text": "Toy reply."}]
        conversations.append({"conversation_id": f"toy{i}", "patient_id": case,
            "family_id": f"family{i}", "learner_id": f"pseudonym{i}",
            "arm": "feedback" if i % 2 else "standard", "phase": "baseline",
            "assignment_ref": "toy assignment", "consent_ref": "toy consent",
            "case_id": case, "case_version": 1,
            "case_sha256": lock["source_sha256"][f"cases/{case}.json"],
            "source_sha256": digest(turns), "turns": turns})
    return {"protocol_lock": lock["lock_id"], "origin": "consented_synthetic_case_encounters",
        "contains_real_patient_data": False, "deidentified": True,
        "consent_and_ethics_verified": True, "consent_policy_ref": "toy-policy",
        "ethics_determination_ref": "toy-ethics", "conversations": conversations}


def _review(packet, reviewer, answer, *, phase="independent"):
    return {"packet_id": packet["packet_id"], "protocol_lock": packet["protocol_lock"],
        "case_sha256": packet["case_sha256"], "case_version": packet["case_version"],
        "reviewer_id": reviewer, "reviewer_role": "faculty", "review_status": "approved",
        "reviewed_at": "2026-10-10T10:00:00Z", "phase": phase, "answer": answer}


def _write(tmp_path, rows):
    path = tmp_path / "reviews.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path


def test_lock_and_blind_packets_from_all_previous_stages():
    lock = lock_manifest()
    packets, mapping = make_packets(lock)
    assert len(packets) == 287
    assert {k: sum(p["kind"] == k for p in packets) for k in ("release", "semantic", "claim", "domain")} == {
        "release": 189, "semantic": 15, "claim": 41, "domain": 42}
    assert len(mapping) == len(packets)
    assert all(p["expected"] is None and p["review_status"] == "pending" for p in packets)
    assert all("allowed_fact_ids" not in p["context"] and "actual_disclosures" not in p["context"]
               for p in packets if p["kind"] == "release")
    assert all("level" not in p["context"] and "score" not in p["context"] for p in packets if p["kind"] in {"release", "domain"})


def test_all_gates_remain_blocked_without_reviews():
    report, packets, log = evaluate()
    assert len(packets) == 287 and log == []
    assert report["reviews"]["submitted_rows"] == 0
    assert report["gates"]["protocol_and_import_workflow"] == "PASS"
    assert all(v == "NOT EVALUABLE" for k,v in report["gates"].items() if k != "protocol_and_import_workflow")
    assert all(x is None for x in report["results"].values())


def test_review_disagreement_needs_independent_adjudication_and_audit(tmp_path):
    packet = next(p for p in make_packets(lock_manifest())[0] if p["kind"] == "semantic")
    rows = [_review(packet,"rater-a",{"expected_supported":True}),
            _review(packet,"rater-b",{"expected_supported":False})]
    partial = load_reviews(_write(tmp_path, rows),[packet])
    assert partial["counts"]["awaiting_adjudication"] == 1
    assert not partial["complete_by_kind"]["semantic"]
    rows.append(_review(packet,"rater-c",{"expected_supported":False},phase="adjudication"))
    full = load_reviews(_write(tmp_path, rows),[packet])
    assert full["complete_by_kind"]["semantic"]
    assert full["resolved"][packet["packet_id"]]["expected_supported"] is False
    assert len(full["audit_log"]) == 3 and full["audit_head"] == full["audit_log"][-1]["chain_sha256"]
    assert full["audit_head"] == load_reviews(_write(tmp_path, rows[::-1]),[packet])["audit_head"]


def test_reject_tampering_duplicate_rater_and_wrong_answer(tmp_path):
    packet = next(p for p in make_packets(lock_manifest())[0] if p["kind"] == "release")
    row = _review(packet,"faculty-a",{"expected_fact_ids":[]})
    wrong = deepcopy(row); wrong["protocol_lock"] = "wrong"
    with pytest.raises(ValueError, match="lock mismatch"):
        load_reviews(_write(tmp_path,[wrong]),[packet])
    with pytest.raises(ValueError, match="distinct raters"):
        load_reviews(_write(tmp_path,[row,row]),[packet])
    wrong = deepcopy(row); wrong["answer"] = {"expected_fact_ids":["made_up"]}
    with pytest.raises(ValueError, match="approved case facts"):
        load_reviews(_write(tmp_path,[wrong]),[packet])
    wrong = deepcopy(row); wrong["reviewed_at"] = "2026-10-10"
    with pytest.raises(ValueError, match="timezone"):
        load_reviews(_write(tmp_path,[wrong]),[packet])


def test_domain_requires_exact_quote_and_na_reason():
    packet = next(p for p in make_packets(lock_manifest())[0] if p["kind"] == "domain")
    with pytest.raises(ValueError, match="transcript evidence"):
        _answer(packet,{"score":1,"evidence":[]})
    with pytest.raises(ValueError, match="N/A requires"):
        _answer(packet,{"score":"N/A"})
    turn = packet["context"]["transcript"][0]
    speaker = "student" if "student" in turn else "patient"
    text = turn[speaker]
    assert _answer(packet,{"score":1,"evidence":[{"kind":"transcript_span","turn":turn["turn"],
        "speaker":speaker,"start":0,"end":len(text),"quote":text}]})["score"] == 1


def test_private_corpus_source_consent_and_grouped_split():
    lock = lock_manifest(); corpus = _toy_corpus(lock)
    conv = validate_corpus(corpus,lock)
    packets, mapping = make_packets(lock,corpus)
    assert sum(p["kind"] == "action" for p in packets) == 3
    assert sum(p["kind"] == "domain" for p in packets) == 42+21
    assert split_audit(conv)["cross_split_links"] == 0
    bad = deepcopy(corpus); bad["consent_and_ethics_verified"] = False
    with pytest.raises(ValueError, match="consent/ethics"):
        validate_corpus(bad,lock)
    bad = deepcopy(corpus); bad["conversations"][0]["source_sha256"] = "wrong"
    with pytest.raises(ValueError, match="digest mismatch"):
        validate_corpus(bad,lock)
    bad = deepcopy(corpus); bad["conversations"][1]["patient_id"] = bad["conversations"][0]["patient_id"]
    # Shared patient families must stay in the same split, even across cases.
    assert split_audit(bad["conversations"])["cross_split_links"] == 0


def test_action_span_validation_and_reviewed_conversion(tmp_path):
    lock=lock_manifest(); corpus=_toy_corpus(lock)
    packets,mapping=make_packets(lock,corpus)
    p=next(p for p in packets if p["kind"]=="action")
    text=p["context"]["text"]
    answer={"annotations":[{"start":0,"end":len(text),"span":text,
                            "labels":["other"],"rubric_mapping":[]}]}
    with pytest.raises(ValueError,match="action span"):
        _answer(p,{"annotations":[{**answer["annotations"][0],"span":"wrong"}]})
    reviews=load_reviews(_write(tmp_path,[_review(p,"a",answer),_review(p,"b",answer)]),packets)
    rows=action_annotations(packets,mapping,reviews,corpus["conversations"])
    assert len(rows)==1 and rows[0]["review_status"]=="approved"
    assert rows[0]["namespace"]=="student_skill" and rows[0]["labels"]==["other"]


def test_ci_and_planning_are_descriptive_only():
    assert wilson(0,0) is None
    assert wilson(10,10)["lower"] < 1
    assert quadratic_kappa([(1,1),(2,2),(3,3),(4,4)]) == 1
    assert planning_n_per_arm()["with_loss_rounded_up"] >= 74
