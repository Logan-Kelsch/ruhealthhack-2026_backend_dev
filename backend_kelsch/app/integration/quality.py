"""Preflight for a proposed study: audit imports, do not infer authorization.

The repository contains no approval receipt or learner outcomes. A complete
metadata bundle alone cannot establish that an institution approved a study.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from backend_kelsch.app.debrief_probe.evaluation import ROOT
from backend_kelsch.app.study.protocol import digest, lock_manifest, make_packets
from backend_kelsch.app.study.review import load_reviews

SCOPES = ("protocol", "synthetic_cases", "consent_process", "review_roster",
          "outcome_definitions", "institutional_determination")
PRIOR = ROOT / "backend_kelsch/docs/validation/study_protocol.json"
TEST_EXECUTION = ROOT / "backend_kelsch/docs/validation/integration_test_execution.json"


def verify_approval_metadata(path: Path | None, lock: dict) -> dict:
    """Check source references, never call self-attested approval verified."""
    if path is None:
        return {"status": "NOT VERIFIED", "metadata_complete": False,
                "scopes_checked": 0, "required_scopes": len(SCOPES),
                "reason": "No faculty or institutional approval bundle supplied"}
    bundle = json.loads(path.read_text())
    if bundle.get("protocol_lock") != lock["lock_id"]:
        raise ValueError("approval bundle protocol lock mismatch")
    rows = bundle.get("documents")
    if not isinstance(rows, list) or len(rows) != len(SCOPES) or {r.get("scope") for r in rows} != set(SCOPES):
        raise ValueError("one document for every approval scope required")
    for r in rows:
        if (r.get("decision") != "approved" or not r.get("approval_ref") or
            not r.get("approved_at") or not r.get("approver_role") or
            not r.get("approver_id") or not r.get("sha256") or not r.get("path")):
            raise ValueError("approval document metadata incomplete")
        file = Path(r["path"])
        if not file.is_file() or sha256(file.read_bytes()).hexdigest() != r["sha256"]:
            raise ValueError("approval document digest mismatch")
        if r["scope"] == "institutional_determination" and r["approver_role"] != "institutional_ethics_office":
            raise ValueError("institutional scope requires ethics-office role")
        if r["scope"] != "institutional_determination" and r["approver_role"] != "faculty":
            raise ValueError("faculty approval role required")
    return {"status": "NOT VERIFIED", "metadata_complete": True,
            "scopes_checked": len(SCOPES), "required_scopes": len(SCOPES),
            "reason": "Document hashes and declared roles checked; institutional authenticity and authority need an independent trusted verification step"}


def verify_audit_log(events: list[dict], *, expected_head: str, packet_ids: set[str]) -> dict:
    """Check ordering, references and full predecessor chain, not just the head."""
    previous = "0" * 64
    seen = set()
    for number, event in enumerate(events, 1):
        if event.get("sequence") != number or event.get("packet_id") not in packet_ids:
            raise ValueError("audit event sequence or packet ID mismatch")
        unit = (event["packet_id"], event.get("phase"), event.get("reviewer_sha256"))
        if unit in seen:
            raise ValueError("duplicate audit review event")
        seen.add(unit)
        data = {k: event[k] for k in ("packet_id", "phase", "reviewer_sha256", "reviewed_at", "answer_sha256")}
        current = digest({"previous": previous, "event": data})
        if event.get("chain_sha256") != current:
            raise ValueError("broken audit chain")
        previous = current
    if previous != expected_head:
        raise ValueError("audit head mismatch")
    return {"status": "PASS", "events": len(events), "head": previous}


def preflight(*, approval_path: Path | None = None, reviews_path: Path | None = None,
              audit_path: Path | None = None, corpus_path: Path | None = None) -> tuple[dict, list[dict]]:
    """Allow review quality checks; block prospective analysis until authorization."""
    lock = lock_manifest()
    prior = json.loads(PRIOR.read_text())
    if prior["protocol"]["lock_id"] != lock["lock_id"]:
        raise ValueError("Notebook 06 report and current protocol source lock differ")
    packets, _ = make_packets(lock)
    counts = dict(Counter(p["kind"] for p in packets))
    if counts != prior["packet_counts"]:
        raise ValueError("packet denominator differs from locked Notebook 06 report")
    for p in packets:
        if p["expected"] is not None or p["review_status"] != "pending":
            raise ValueError("reviewer packet contains a system answer")
        context = p["context"]
        if p["kind"] == "release" and any(k in context for k in ("allowed_fact_ids", "explicit_intent", "level", "actual_disclosures")):
            raise ValueError("release reviewer packet leaks engine output")
        if p["kind"] == "semantic" and any(k in context for k in ("deterministic_blocked", "llm_judge")):
            raise ValueError("semantic reviewer packet leaks verdict")
        if p["kind"] == "domain" and any(k in context for k in ("score", "rule_based_score")):
            raise ValueError("rubric packet leaks provisional score")
    approval = verify_approval_metadata(approval_path, lock)
    if corpus_path is not None:
        raise PermissionError("prospective learner corpus blocked: independently verified faculty and institutional authorization is unavailable")
    if audit_path and not reviews_path:
        raise ValueError("review source required to authenticate an imported audit log")
    if reviews_path:
        review = load_reviews(reviews_path, packets)
        expected_events = review["audit_log"]
        if audit_path:
            supplied = [json.loads(x) for x in audit_path.read_text().splitlines() if x.strip()]
            if supplied != expected_events:
                raise ValueError("imported audit log differs from validated review source")
        audit = verify_audit_log(expected_events, expected_head=review["audit_head"],
                                 packet_ids={p["packet_id"] for p in packets})
        resolved = review["resolved_by_kind"]
        waiting = review["counts"].get("awaiting_adjudication", 0)
        na = sum(1 for p in packets if p["kind"] == "domain" and p["packet_id"] in review["resolved"]
                 and review["resolved"][p["packet_id"]]["score"] == "N/A")
    else:
        audit = verify_audit_log([], expected_head="0"*64, packet_ids={p["packet_id"] for p in packets})
        resolved, waiting, na = {}, 0, 0
    missing = {k: v - resolved.get(k, 0) for k, v in counts.items()}
    report = {"stage": "Notebook 07", "mode": "quality_control_only",
        "source_lock": lock, "packet_manifest_sha256": digest([p["packet_id"] for p in packets]),
        "approval": approval, "review_denominators": {"total_by_kind": counts,
            "resolved_by_kind": resolved, "missing_by_kind": missing,
            "unresolved_disagreements": waiting, "reviewed_na_domain_count": na},
        "audit": audit, "prospective_learners": 0,
        "test_execution_snapshot": json.loads(TEST_EXECUTION.read_text()) if TEST_EXECUTION.exists() else None,
        "reviewed_class_balance": None, "confidence_intervals": None,
        "performance_failure_examples": None,
        "engineering_limitations": ["No verified faculty/ethics authorization or learner cohort.",
            "Metadata, document digests and reviewer role strings do not authenticate institutional approval.",
            "Authored Notebook 04/05 probes are reviewer work items, not learner outcomes.",
            "HTTP API tests require a working TestClient environment; local status is reported separately."],
        "gates": {"source_locked_import_quality": "PASS",
            "approval_and_consent": "NOT EVALUABLE", "trained_action_extraction": "NOT EVALUABLE",
            "prompted_extraction_comparison": "NOT EVALUABLE",
            "clinical_disclosure_accuracy": "NOT EVALUABLE", "semantic_grounding": "NOT EVALUABLE",
            "faculty_feedback_accuracy": "NOT EVALUABLE", "faculty_rubric_agreement": "NOT EVALUABLE",
            "difficulty_calibration": "NOT EVALUABLE", "student_learning": "NOT EVALUABLE"}}
    return report, packets
