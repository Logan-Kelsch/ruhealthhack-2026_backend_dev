"""Run Notebook 04 offline probes from the repository root.

LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_grounding
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from backend_kelsch.app.grounding.evaluation import (
    CASE_IDS, LEVELS, PRESETS, ROOT, challenges, check_challenges, encounter_runs,
    export_review_queue, load_reviews, release_metrics, semantic_metrics,
)

REPORT = ROOT / "backend_kelsch/docs/validation/grounding_eval.json"
TRACES = ROOT / "backend_kelsch/docs/validation/grounding_traces.json.gz"


def evaluate(*, review_path: Path | None = None, use_llm: bool = False) -> tuple[dict, dict]:
    runs, encounters = encounter_runs()
    challenge_rows = challenges()
    challenge_result = check_challenges(challenge_rows, use_llm=use_llm)
    reviews = load_reviews(review_path, runs, challenge_rows) if review_path else {
        "releases": {}, "semantics": {}, "release_complete": False, "semantic_complete": False,
        "reviewed_release_turns": 0, "total_release_turns": encounters["counts"]["turns"],
        "reviewed_challenges": 0, "total_challenges": len(challenge_rows)}
    disclosure = release_metrics(runs, reviews)
    semantic = semantic_metrics(challenge_rows, reviews)
    ec, cc = encounters["counts"], challenge_result["counts"]
    mechanics_pass = (ec["invariant_violations"] == 0 and ec["replay_matches"] == ec["replays"]
        and cc["mechanical_blocks"] == cc["mechanical_block_attempts"]
        and cc["mechanical_supported_passed"] == cc["mechanical_supported_candidates"])
    discovery = [{"case_id": r["case_id"], "level": r["level"], "preset": r["preset"],
                  "disclosed": r["discovery_count"], "trust": r["final_trust"]} for r in runs]
    pairs = [{"case_id": cid, "level": level,
              "straightforward_minus_difficult": next(d["disclosed"] for d in discovery if d["case_id"] == cid and d["level"] == level and d["preset"] == "straightforward") - next(d["disclosed"] for d in discovery if d["case_id"] == cid and d["level"] == level and d["preset"] == "difficult")}
             for cid in CASE_IDS for level in LEVELS]
    report = {"stage": "Notebook 04", "method": "authored scripts and case facts; no reviewed performance labels",
        "scripts": {"cases": list(CASE_IDS), "levels": list(LEVELS), "presets": list(PRESETS),
                    "script_count": len(runs), "turn_count": ec["turns"]},
        "sources": ["cases/*.json: each run contains case SHA-256 and version",
                    "backend_kelsch/docs/validation/action_data.json",
                    "backend_kelsch/docs/validation/patient_environment.json",
                    "PRD.md §9.1, §9.3, §9.4, §15 (V-01, V-02, V-04)"],
        "mechanics": {"status": "PASS" if mechanics_pass else "FAIL", **encounters,
            "cited_fact_source_coverage": {"numerator": ec["cited_facts"] if ec["invariant_violations"] == 0 else None,
                                           "denominator": ec["cited_facts"]},
            "offline_template_rate": {"numerator": ec["template_replies"], "denominator": ec["turns"]},
            "pipeline_fallback_rate": None},
        "challenge_set": {**challenge_result, "llm_judge_run": use_llm,
                          "semantic_accuracy": semantic},
        "reviews": {k: v for k, v in reviews.items() if k not in ("releases", "semantics")},
        "disclosure_metrics": disclosure,
        "illustrative_difficulty": {"discovery": discovery, "paired_differences": pairs,
            "status": "NOT EVALUABLE", "reason": "Threshold-only vectors and authored scripts are not faculty calibrated or sampled students"},
        "gates": {"offline_mechanics": "PASS" if mechanics_pass else "FAIL",
            "reviewed_disclosure_accuracy": "NOT EVALUABLE" if disclosure is None else ("PASS" if disclosure["fp"] == 0 and disclosure["fn"] == 0 else "FAIL"),
            "semantic_grounding": "NOT EVALUABLE" if semantic is None else ("PASS" if semantic["fp"] == 0 else "FAIL"),
            "trained_action_extraction": "NOT EVALUABLE", "difficulty_calibration": "NOT EVALUABLE",
            "student_learning": "NOT EVALUABLE"},
        "limitations": ["Scripted intent tags are fixture inputs, not reviewed student actions.",
            "Template fact IDs and deterministic checks do not prove sentence-level clinical meaning.",
            "Three unsupported prose candidates pass deterministic checks and are never delivered in these probes.",
            "All 189 offline responses use templates by design; this is not a live pipeline fallback rate.",
            "No independent faculty expected releases or semantic reviews are supplied.",
            "Full S-11 difficulty presets and V-04 student sample are not available."]}
    compact = []
    for run in runs:
        compact.append({k: v for k, v in run.items() if k != "turns"} | {
            "turns": [{k: v for k, v in t.items() if k not in ("state_after", "student_view", "chart_releases")}
                      for t in run["turns"]]})
    trace = {"runs": compact, "challenges": challenge_rows}
    return report, trace


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviews", type=Path, help="Independent faculty-reviewed JSONL")
    parser.add_argument("--export-review-queue", type=Path, help="Write pending labels for faculty review")
    parser.add_argument("--llm-judge", action="store_true", help="Opt in to configured Bedrock judge; record calls")
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--traces", type=Path, default=TRACES)
    args = parser.parse_args()
    report, trace = evaluate(review_path=args.reviews, use_llm=args.llm_judge)
    if args.export_review_queue:
        export_review_queue(args.export_review_queue, trace["runs"], trace["challenges"])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    args.traces.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(trace, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    if args.traces.suffix == ".gz":
        with args.traces.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as stream:
            stream.write(payload)
    else:
        args.traces.write_bytes(payload)
    print(json.dumps({"scripts": report["scripts"], "mechanics": report["mechanics"]["status"],
                      "gates": report["gates"], "challenge_counts": report["challenge_set"]["counts"]}, indent=2))
    if report["gates"]["offline_mechanics"] == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
