"""Build Notebook 06 packets and report; optional private human-review imports.

LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_study
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from backend_kelsch.app.debrief_probe.evaluation import ROOT
from backend_kelsch.app.study.analysis import planning_n_per_arm, reviewed_metrics
from backend_kelsch.app.study.protocol import lock_manifest, make_packets, validate_corpus
from backend_kelsch.app.study.review import load_reviews

REPORT = ROOT / "backend_kelsch/docs/validation/study_protocol.json"
TEST_EXECUTION = ROOT / "backend_kelsch/docs/validation/study_test_execution.json"


def _predictions(path: Path | None, key: str) -> dict | None:
    if path is None:
        return None
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if any(not r.get(key) for r in rows) or len({r[key] for r in rows}) != len(rows):
        raise ValueError(f"missing or duplicate prediction {key}")
    return {r[key]: {k:v for k,v in r.items() if k != key} for r in rows}


def evaluate(*, corpus_path: Path | None = None, reviews_path: Path | None = None,
             llm_path: Path | None = None, judge_path: Path | None = None) -> tuple[dict, list[dict], list[dict]]:
    lock = lock_manifest()
    corpus = json.loads(corpus_path.read_text()) if corpus_path else None
    conversations = validate_corpus(corpus, lock) if corpus else []
    packets, mapping = make_packets(lock, corpus)
    if reviews_path:
        review = load_reviews(reviews_path, packets)
    else:
        counts = Counter(p["kind"] for p in packets)
        review = {"resolved": {}, "raw_pairs": {}, "counts": {"review_rows": 0},
                  "resolved_by_kind": {}, "total_by_kind": dict(counts),
                  "complete_by_kind": {kind: False for kind in counts},
                  "audit_log": [], "audit_head": "0" * 64}
    if llm_path and not review["complete_by_kind"].get("action"):
        raise ValueError("LLM comparison requires complete independent action review")
    if judge_path and not review["complete_by_kind"].get("semantic"):
        raise ValueError("semantic judge comparison requires complete independent semantic review")
    # Notebook 02 evaluates reviewed spans, while semantic judgments address
    # one packet/reply. Both require complete, independently logged coverage.
    llm = _predictions(llm_path, "annotation_id")
    judge = _predictions(judge_path, "packet_id")
    measured = reviewed_metrics(packets, mapping, review, conversations,
                                llm_predictions=llm, judge_predictions=judge)
    report = {"stage": "Notebook 06", "protocol": lock,
        "source_note": "Prior authored fixtures are queue inputs, never prospective learner outcomes",
        "packet_counts": dict(Counter(p["kind"] for p in packets)),
        "blindness": {"actual_disclosures_visible": False, "verifier_verdict_visible": False,
                      "provisional_rubric_scores_visible": False, "script_level_visible": False},
        "reviews": {"submitted_rows": review["counts"].get("review_rows",0),
                    "resolved_by_kind": review["resolved_by_kind"],
                    "total_by_kind": review["total_by_kind"],
                    "complete_by_kind": review["complete_by_kind"],
                    "disagreements_waiting": review["counts"].get("awaiting_adjudication",0),
                    "adjudicated": review["counts"].get("adjudicated",0),
                    "audit_head": review["audit_head"]},
        "prospective_conversations": len(conversations),
        "planning_n_per_arm": planning_n_per_arm(),
        "test_execution_snapshot": json.loads(TEST_EXECUTION.read_text()) if TEST_EXECUTION.exists() else None,
        **measured,
        "limitations": ["Protocol is proposed, pending faculty and ethics approval; no learner cohort or human review files bundled.",
            "Metadata checks cannot authenticate a reviewer's professional identity or genuine independence.",
            "Authored script expectations cannot establish student-performance ground truth.",
            "With only three authored patient cases, patient-group splits are too small for a trained model study.",
            "Wilson fact-level intervals assume independent units; case/turn clustering requires a larger reviewed cohort.",
            "Scoring agreement needs at least 20 distinct encounters per domain; six authored scenarios cannot satisfy it."]}
    return report, packets, review["audit_log"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, help="Private, consented deidentified synthetic-case learner corpus")
    parser.add_argument("--reviews", type=Path, help="Two independent reviews per packet, adjudication for disagreements")
    parser.add_argument("--llm-predictions", type=Path, help="Logged held-out action predictions, after reviews")
    parser.add_argument("--judge-predictions", type=Path, help="Logged semantic judge predictions, after reviews")
    parser.add_argument("--export-packets", type=Path, help="Write blinded pending reviewer JSONL")
    parser.add_argument("--audit-log", type=Path, help="Write hash-chained redacted review audit JSONL")
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    report, packets, events = evaluate(corpus_path=args.corpus, reviews_path=args.reviews,
        llm_path=args.llm_predictions, judge_path=args.judge_predictions)
    if args.export_packets:
        args.export_packets.parent.mkdir(parents=True, exist_ok=True)
        args.export_packets.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in packets))
    if args.audit_log:
        args.audit_log.parent.mkdir(parents=True, exist_ok=True)
        args.audit_log.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"lock_id": report["protocol"]["lock_id"], "packets": report["packet_counts"],
                      "reviews": report["reviews"], "gates": report["gates"]}, indent=2))


if __name__ == "__main__":
    main()
