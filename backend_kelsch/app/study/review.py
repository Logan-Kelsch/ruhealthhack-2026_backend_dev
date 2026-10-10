"""Validate two independent blinded reviews and a third-party adjudication.

Reviewer metadata is a technical check. Organizational independence and consent
must also be verified by the study coordinator outside this module.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path

from app.schemas.case import Case
from backend_kelsch.app.action_data.preparation import validate_annotations
from backend_kelsch.app.debrief_probe.evaluation import ROOT
from backend_kelsch.app.study.protocol import VOCAB, digest


def _time(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("timezone required")
    except (AttributeError, ValueError) as exc:
        raise ValueError("review timestamp must include timezone") from exc


def _answer(packet: dict, answer: dict) -> dict:
    if not isinstance(answer, dict):
        raise ValueError("answer must be an object")
    kind = packet["kind"]
    if kind == "release":
        ids = answer.get("expected_fact_ids")
        case = Case.model_validate_json((ROOT / "cases" / f"{packet['case_id']}.json").read_text())
        allowed = {f.id for f in case.facts if f.status == "approved"}
        if not isinstance(ids, list) or len(ids) != len(set(ids)) or not set(ids) <= allowed:
            raise ValueError("expected release IDs must be unique approved case facts")
        return {"expected_fact_ids": sorted(ids)}
    if kind in {"semantic", "claim"}:
        if not isinstance(answer.get("expected_supported"), bool):
            raise ValueError("supported/unsupported label must be boolean")
        return {"expected_supported": answer["expected_supported"]}
    if kind == "domain":
        score = answer.get("score")
        if type(score) is not int and score != "N/A":
            raise ValueError("domain score must be 1–4 or N/A")
        if type(score) is int and score not in range(1, 5):
            raise ValueError("domain score must be 1–4 or N/A")
        evidence = answer.get("evidence", [])
        if not isinstance(evidence, list):
            raise ValueError("domain evidence must be a list")
        transcript = {t["turn"]: t for t in packet["context"]["transcript"]}
        if score == "N/A":
            if not answer.get("na_reason") or evidence:
                raise ValueError("N/A requires a reason and no evidence")
            return {"score": score, "na_reason": answer["na_reason"], "evidence": []}
        if not evidence:
            raise ValueError("scored domain needs transcript evidence")
        for ref in evidence:
            if (ref.get("kind") != "transcript_span" or
                ref.get("turn") not in transcript or ref.get("speaker") not in {"student", "patient"}):
                raise ValueError("domain evidence must cite transcript span")
            text = transcript[ref["turn"]][ref["speaker"]]
            a, b = ref.get("start"), ref.get("end")
            if not isinstance(a, int) or not isinstance(b, int) or not 0 <= a < b <= len(text) or text[a:b] != ref.get("quote"):
                raise ValueError("domain evidence quote/offset mismatch")
        return {"score": score, "evidence": sorted(evidence, key=digest)}
    if kind == "action":
        annotations = answer.get("annotations")
        if not isinstance(annotations, list) or not annotations:
            raise ValueError("review a negative with an exact-span other label")
        text = packet["context"]["text"]
        vocab = set(json.loads(VOCAB.read_text())["student_skill"])
        seen = set()
        normalized = []
        for a in annotations:
            start, end, labels = a.get("start"), a.get("end"), a.get("labels")
            domains = a.get("rubric_mapping")
            if (not isinstance(start, int) or not isinstance(end, int) or
                not 0 <= start < end <= len(text) or text[start:end] != a.get("span") or
                not isinstance(labels, list) or not labels or len(labels) != len(set(labels)) or
                not set(labels) <= vocab or ("other" in labels and len(labels) != 1) or
                not isinstance(domains, list) or len(domains) != len(set(domains)) or
                any(type(d) is not int or d not in range(1, 8) for d in domains) or
                (start, end) in seen):
                raise ValueError("invalid action span, namespace labels or rubric mapping")
            seen.add((start, end))
            normalized.append({"start": start, "end": end, "span": a["span"],
                               "labels": sorted(labels), "rubric_mapping": sorted(domains)})
        return {"annotations": sorted(normalized, key=lambda a: (a["start"], a["end"]))}
    raise ValueError("unknown packet kind")


def load_reviews(path: Path, packets: list[dict]) -> dict:
    """Only consensus/adjudicated packets advance; partial coverage stays visible."""
    index = {p["packet_id"]: p for p in packets}
    entries: dict[str, list[dict]] = {}
    for line_no, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        packet = index.get(row.get("packet_id"))
        if packet is None:
            raise ValueError(f"unknown packet on line {line_no}")
        if (row.get("protocol_lock") != packet["protocol_lock"] or
            row.get("case_sha256") != packet["case_sha256"] or
            row.get("case_version") != packet["case_version"]):
            raise ValueError("review source/protocol lock mismatch")
        if (row.get("reviewer_role") != "faculty" or not row.get("reviewer_id") or
            row["reviewer_id"] == "notebook_fixture" or
            row.get("review_status") != "approved" or
            row.get("phase") not in {"independent", "adjudication"} or
            not row.get("reviewed_at")):
            raise ValueError("independent faculty reviewer metadata required")
        _time(row["reviewed_at"])
        normalized = _answer(packet, row.get("answer"))
        entries.setdefault(packet["packet_id"], []).append({"reviewer_id": row["reviewer_id"],
            "phase": row["phase"], "answer": normalized, "reviewed_at": row["reviewed_at"]})
    resolved = {}
    raw_pairs: dict[str, tuple[dict, dict]] = {}
    counts = Counter()
    log = []
    previous = "0" * 64
    for packet in packets:  # stable blinded order, reproducible regardless of input row order
        pid = packet["packet_id"]
        rows = entries.get(pid, [])
        independent = sorted((r for r in rows if r["phase"] == "independent"), key=lambda r: r["reviewer_id"])
        adjudication = [r for r in rows if r["phase"] == "adjudication"]
        if len(independent) > 2 or len(adjudication) > 1 or len({r["reviewer_id"] for r in rows}) != len(rows):
            raise ValueError("each packet needs two distinct raters and at most one distinct adjudicator")
        if adjudication and len(independent) != 2:
            raise ValueError("adjudication needs both independent reviews")
        if len(independent) == 2:
            raw_pairs[pid] = (independent[0]["answer"], independent[1]["answer"])
            if independent[0]["answer"] == independent[1]["answer"]:
                if adjudication:
                    raise ValueError("adjudication submitted without disagreement")
                resolved[pid] = independent[0]["answer"]
                counts["agreements"] += 1
            elif adjudication:
                resolved[pid] = adjudication[0]["answer"]
                counts["adjudicated"] += 1
            else:
                counts["awaiting_adjudication"] += 1
        counts["review_rows"] += len(rows)
        for r in sorted(rows, key=lambda x: (x["phase"] == "adjudication", x["reviewer_id"])):
            event = {"packet_id": pid, "phase": r["phase"], "reviewer_sha256": sha256(r["reviewer_id"].encode()).hexdigest(),
                     "reviewed_at": r["reviewed_at"], "answer_sha256": digest(r["answer"])}
            previous = digest({"previous": previous, "event": event})
            log.append({"sequence": len(log) + 1, **event, "chain_sha256": previous})
    by_kind = Counter(index[pid]["kind"] for pid in resolved)
    total = Counter(p["kind"] for p in packets)
    return {"resolved": resolved, "raw_pairs": raw_pairs, "counts": dict(counts),
            "resolved_by_kind": dict(by_kind), "total_by_kind": dict(total),
            "complete_by_kind": {k: by_kind[k] == v for k, v in total.items()},
            "audit_log": log, "audit_head": previous}


def action_annotations(packets: list[dict], mapping: dict, reviews: dict, conversations: list[dict]) -> list[dict]:
    """Create Notebook 02 input only from resolved human action-span labels."""
    by_conv = {c["conversation_id"]: c for c in conversations}
    rows = []
    for p in packets:
        if p["kind"] != "action" or p["packet_id"] not in reviews["resolved"]:
            continue
        conv_id, turn_id = mapping[p["packet_id"]]["key"].split(":", 1)
        conv = by_conv[conv_id]
        for i, span in enumerate(reviews["resolved"][p["packet_id"]]["annotations"]):
            rows.append({"annotation_id": f"{p['packet_id']}:{i}", "conversation_id": conv_id,
                "turn_id": turn_id, "speaker": "student", **span, "namespace": "student_skill",
                "review_status": "approved", "reviewer_type": "human",
                "reviewer_id": "independent_pair_and_adjudicator", "reviewed_at": "source_review_log"})
    vocab = json.loads(VOCAB.read_text())
    validate_annotations(rows, conversations, vocab)
    return rows
