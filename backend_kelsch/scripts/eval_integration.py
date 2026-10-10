"""Notebook 07 quality-only preflight; no student outcome analysis.

LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_integration
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend_kelsch.app.debrief_probe.evaluation import ROOT
from backend_kelsch.app.integration.quality import preflight

REPORT = ROOT / "backend_kelsch/docs/validation/integration_readiness.json"


def evaluate(*, approval_path: Path | None = None, reviews_path: Path | None = None,
             audit_path: Path | None = None, corpus_path: Path | None = None) -> dict:
    report, _ = preflight(approval_path=approval_path, reviews_path=reviews_path,
                          audit_path=audit_path, corpus_path=corpus_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval-bundle", type=Path, help="Private metadata and document hashes; does not establish authenticity")
    parser.add_argument("--reviews", type=Path, help="Private independent review JSONL for source/audit quality checks only")
    parser.add_argument("--audit-log", type=Path, help="Compare against audit reconstructed from private review source")
    parser.add_argument("--corpus", type=Path, help="Prospective import deliberately blocked pending external approval verification")
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    report = evaluate(approval_path=args.approval_bundle, reviews_path=args.reviews,
                      audit_path=args.audit_log, corpus_path=args.corpus)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"mode": report["mode"], "approval": report["approval"],
                      "review_denominators": report["review_denominators"],
                      "audit": report["audit"], "gates": report["gates"]}, indent=2))


if __name__ == "__main__":
    main()
