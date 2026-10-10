"""Notebook 07 negative controls use toy metadata, never study labels."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

import pytest

from backend_kelsch.app.integration import quality
from backend_kelsch.app.study.protocol import lock_manifest, make_packets
from backend_kelsch.app.study.review import load_reviews


def test_no_approval_means_no_performance_or_learner_import():
    report, packets = quality.preflight()
    assert len(packets) == 287
    assert report["approval"]["status"] == "NOT VERIFIED"
    assert report["review_denominators"]["missing_by_kind"] == {"release":189,"semantic":15,"claim":41,"domain":42}
    assert report["audit"]["events"] == 0
    assert report["prospective_learners"] == 0
    assert report["reviewed_class_balance"] is None and report["confidence_intervals"] is None
    assert report["gates"]["source_locked_import_quality"] == "PASS"
    assert all(v == "NOT EVALUABLE" for k,v in report["gates"].items() if k != "source_locked_import_quality")
    with pytest.raises(PermissionError, match="independently verified"):
        quality.preflight(corpus_path=__import__("pathlib").Path("/tmp/not_read.json"))


def test_source_lock_rejects_stale_report(tmp_path, monkeypatch):
    report = json.loads(quality.PRIOR.read_text())
    report["protocol"]["lock_id"] = "stale"
    file = tmp_path / "old_report.json"
    file.write_text(json.dumps(report))
    monkeypatch.setattr(quality, "PRIOR", file)
    with pytest.raises(ValueError, match="source lock differ"):
        quality.preflight()


def test_blindness_probe_rejects_leaked_release(monkeypatch):
    packets,mapping = make_packets(lock_manifest())
    broken = deepcopy(packets)
    release = next(p for p in broken if p["kind"] == "release")
    release["context"]["allowed_fact_ids"] = ["f_hidden"]
    monkeypatch.setattr(quality, "make_packets", lambda lock: (broken,mapping))
    with pytest.raises(ValueError, match="leaks engine output"):
        quality.preflight()


def test_approval_document_digests_are_checked_but_not_called_verified(tmp_path):
    lock=lock_manifest()
    docs=[]
    for scope in quality.SCOPES:
        p=tmp_path/f"{scope}.txt"
        p.write_text("toy metadata document; not institutional approval")
        docs.append({"scope":scope,"decision":"approved","approval_ref":"toy-ref",
                     "approved_at":"2026-10-10T10:00:00Z","approver_role":"institutional_ethics_office" if scope=="institutional_determination" else "faculty",
                     "approver_id":"toy-pseudonym", "sha256":sha256(p.read_bytes()).hexdigest(),"path":str(p)})
    bundle=tmp_path/"bundle.json"
    bundle.write_text(json.dumps({"protocol_lock":lock["lock_id"],"documents":docs}))
    status=quality.verify_approval_metadata(bundle,lock)
    assert status["metadata_complete"] and status["status"] == "NOT VERIFIED"
    p=tmp_path/"protocol.txt";p.write_text("changed")
    with pytest.raises(ValueError,match="digest mismatch"):
        quality.verify_approval_metadata(bundle,lock)


def _toy_review(packet):
    return {"packet_id":packet["packet_id"],"protocol_lock":packet["protocol_lock"],
        "case_sha256":packet["case_sha256"],"case_version":packet["case_version"],
        "reviewer_id":"toy-faculty-a","reviewer_role":"faculty","review_status":"approved",
        "reviewed_at":"2026-10-10T10:00:00Z","phase":"independent",
        "answer":{"expected_supported":False}}


def test_partial_private_review_audit_round_trip_and_tamper(tmp_path):
    packet=next(p for p in make_packets(lock_manifest())[0] if p["kind"]=="semantic")
    review_path=tmp_path/"private.jsonl"
    review_path.write_text(json.dumps(_toy_review(packet))+"\n")
    loaded=load_reviews(review_path,make_packets(lock_manifest())[0])
    audit_path=tmp_path/"audit.jsonl"
    audit_path.write_text("".join(json.dumps(e)+"\n" for e in loaded["audit_log"]))
    report,_=quality.preflight(reviews_path=review_path,audit_path=audit_path)
    assert report["audit"]["events"] == 1
    assert report["review_denominators"]["resolved_by_kind"] == {}
    assert report["gates"]["semantic_grounding"] == "NOT EVALUABLE"
    tampered=deepcopy(loaded["audit_log"])
    tampered[0]["answer_sha256"]="0"*64
    with pytest.raises(ValueError,match="broken audit chain"):
        quality.verify_audit_log(tampered,expected_head=loaded["audit_head"],packet_ids={packet["packet_id"]})
    audit_path.write_text(json.dumps(tampered[0])+"\n")
    with pytest.raises(ValueError,match="differs from validated review source"):
        quality.preflight(reviews_path=review_path,audit_path=audit_path)


def test_imported_audit_requires_source_and_exact_head(tmp_path):
    file=tmp_path/"audit.jsonl";file.write_text("")
    with pytest.raises(ValueError,match="review source required"):
        quality.preflight(audit_path=file)
    with pytest.raises(ValueError,match="audit head mismatch"):
        quality.verify_audit_log([],expected_head="wrong",packet_ids=set())


def test_approval_scope_and_role_cannot_be_inferred(tmp_path):
    lock=lock_manifest()
    file=tmp_path/"bundle.json"
    file.write_text(json.dumps({"protocol_lock":lock["lock_id"],"documents":[]}))
    with pytest.raises(ValueError,match="every approval scope"):
        quality.verify_approval_metadata(file,lock)
    file.write_text(json.dumps({"protocol_lock":"stale","documents":[]}))
    with pytest.raises(ValueError,match="protocol lock mismatch"):
        quality.verify_approval_metadata(file,lock)
