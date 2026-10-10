"""Run Notebook 05 sourced feedback probes from the repository root.

LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_debrief
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from backend_kelsch.app.debrief_probe.evaluation import ROOT, import_reviews, review_queue, run_all

REPORT = ROOT / "backend_kelsch/docs/validation/debrief_eval.json"
TRACES = ROOT / "backend_kelsch/docs/validation/debrief_traces.json.gz"


def evaluate(reviews: Path | None = None) -> tuple[dict, list[dict]]:
    report, traces = run_all()
    checked = import_reviews(reviews, traces) if reviews else {
        "reviewed_claims": 0, "total_claims": report["counts"]["claims"],
        "complete": False, "feedback_accuracy": None}
    report["reviews"] = checked
    if checked["complete"]:
        report["gates"]["faculty_feedback_accuracy"] = "PASS" if checked["feedback_accuracy"] == 1 else "FAIL"
    return report, traces


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviews", type=Path, help="Independently faculty-reviewed JSONL")
    parser.add_argument("--export-review-queue", type=Path, help="Pending claim review JSONL")
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--traces", type=Path, default=TRACES)
    args = parser.parse_args()
    report, traces = evaluate(args.reviews)
    if args.export_review_queue:
        args.export_review_queue.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in review_queue(traces)))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    args.traces.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(traces, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    with args.traces.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as z:
        z.write(payload)
    print(json.dumps({"counts": report["counts"], "gates": report["gates"], "reviews": report["reviews"]}, indent=2))
    if report["gates"]["evidence_linkage_and_replay"] == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
