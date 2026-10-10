"""Replay authored students through the real turn pipeline and verifier.

Offline: LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_live_grounding
Live: PYTHONPATH=backend python -m backend_kelsch.scripts.eval_live_grounding --live --pricing private_rates.json
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
from pathlib import Path

from app.settings import get_settings
from backend_kelsch.app.grounding.evaluation import ROOT
from backend_kelsch.app.grounding.live import credentials_ready, evaluate

REPORT = ROOT / "backend_kelsch/docs/validation/live_grounding_v1.json"
TRACES = ROOT / "backend_kelsch/docs/validation/live_grounding_v1_traces.json.gz"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Run configured Bedrock calls only when credentials are detected")
    parser.add_argument("--pricing", type=Path, help="Private, dated USD per-million-token rate snapshot for exact model IDs")
    parser.add_argument("--report", type=Path, help="Explicit private path required for live runs")
    parser.add_argument("--traces", type=Path, help="Explicit private path required for live runs")
    args = parser.parse_args()
    if args.live and (args.report is None or args.traces is None):
        parser.error("--live requires explicit --report and --traces paths outside the committed fixtures")
    report_path = args.report or REPORT
    traces_path = args.traces or TRACES
    can_run_live = args.live and credentials_ready()
    if not can_run_live:
        os.environ["LLM_ENABLED"] = "false"
        get_settings.cache_clear()
    report, traces = evaluate(mode="live" if can_run_live else "offline", pricing_path=args.pricing)
    report["requested_live"] = args.live
    report["live_status"] = "EVALUATED" if can_run_live else "NOT EVALUABLE"
    if args.live and not can_run_live:
        report["live_reason"] = "Configured Bedrock credentials and LLM_ENABLED=true are required; no model call was attempted"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    traces_path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(traces, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    if traces_path.suffix == ".gz":
        with traces_path.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as stream:
            stream.write(payload)
    else:
        traces_path.write_bytes(payload)
    print(json.dumps({k: report[k] for k in ("version", "mode", "live_status", "scripts", "turns",
                                          "delivered", "challenges", "usage_and_cost", "gates")}, indent=2))
    if "FAIL" in report["gates"].values():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
