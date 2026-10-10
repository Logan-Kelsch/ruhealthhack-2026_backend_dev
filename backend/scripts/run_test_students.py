"""Run test students through the encounter pipeline on the golden cases (PRD S-14, V-01).

    python -m scripts.run_test_students [--case walter_greene] [--level novice] [--offline] [--save]
Same pipeline as a real encounter (classify, disclose, phrase, verify, fallback), no
database. Every reply is audited against the facts the engine allowed; any failure exits
with status 1, so this is the golden-case gate in AGENTS.md. --save writes every turn to
docs/validation/test_students.json.
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.schemas.case import Case
from app.settings import get_settings
from app.studio.preview import LEVELS, run_test_student

ROOT = Path(__file__).resolve().parents[2]
CASES_DIR = ROOT / "cases"
OUT = ROOT / "docs" / "validation" / "test_students.json"


def golden_cases(names: list[str]) -> list[Case]:
    if names:
        paths = [CASES_DIR / f"{n}.json" for n in names]
    else:
        paths = sorted(CASES_DIR.glob("*.json"))
    cases = [Case.model_validate_json(p.read_text(encoding="utf-8")) for p in paths]
    return cases if names else [c for c in cases if c.golden]


def git_commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", action="append", default=[], help="case file name without .json; repeatable (default: all golden cases)")
    ap.add_argument("--level", action="append", default=[], choices=LEVELS, help="repeatable (default: all levels)")
    ap.add_argument("--driver", choices=["scripted", "llm"], default="scripted")
    ap.add_argument("--offline", action="store_true", help="no Bedrock: keyword classifier and template replies")
    ap.add_argument("--transcript", action="store_true", help="print each conversation")
    ap.add_argument("--save", action="store_true", help=f"write all turns to {OUT.relative_to(ROOT).as_posix()}")
    args = ap.parse_args()

    if args.offline:
        if args.driver == "llm":
            ap.error("--driver llm needs Bedrock; drop --offline")
        os.environ["LLM_ENABLED"] = "false"
        os.environ["NLM_LOOKUP_ENABLED"] = "false"
        get_settings.cache_clear()
    s = get_settings()

    runs = []
    print(f"{'case':<16}{'level':<13}{'turns':>5}{'audit ok':>10}{'llm/tmpl':>10}{'blocked':>9}{'facts':>8}{'rubric*':>9}  branch")
    for case in golden_cases(args.case):
        for level in args.level or LEVELS:
            out = run_test_student(case, level, driver=args.driver)
            g = out["grounding"]
            scored = [d["score"] for d in out["rubric"] if isinstance(d["score"], int)]
            runs.append({"case_id": case.case_id, "case_version": case.version, **out})
            print(f"{case.case_id:<16}{level:<13}{g['replies']:>5}{g['replies'] - g['replies_failing_audit']:>6}/{g['replies']:<3}"
                  f"{g['llm_replies']:>6}/{g['template_replies']:<3}{g['attempts_blocked_by_verifier']:>9}"
                  f"{out['facts_found']:>5}/{out['facts_expected']:<2}{sum(scored):>6}/{4 * len(scored):<2}  {out['branch'] or '-'}")
            if args.transcript:
                for t in out["turns"]:
                    print(f"    STUDENT: {t['student_text']}\n    PATIENT: {t['reply_text']}  [{t['verifier']['mode']}: {', '.join(t['cited_fact_ids']) or 'no facts'}]")
                    for p in t["audit_problems"]:
                        print(f"    AUDIT FAILED: {p}")
                print()
    print("* rule-based rubric total, a discussion aid, not a pass/fail grade")

    failing = [(r["case_id"], r["level"], t["idx"], p) for r in runs for t in r["turns"] for p in t["audit_problems"]]
    replies = sum(r["grounding"]["replies"] for r in runs)
    print(f"\n{replies - len({f[:3] for f in failing})}/{replies} replies passed the audit"
          f" ({'LLM on: ' + s.bedrock_model_fast if s.llm_enabled else 'LLM off'}).")
    for case_id, level, idx, problem in failing:
        print(f"  {case_id} {level} turn {idx}: {problem}")

    if args.save:
        summary = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "git_commit": git_commit(),
            "driver": args.driver,
            "llm_enabled": s.llm_enabled,
            "models": {"fast": s.bedrock_model_fast, "strong": s.bedrock_model_strong} if s.llm_enabled else None,
            "replies": replies,
            "replies_failing_audit": len({f[:3] for f in failing}),
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps({"summary": summary, "runs": runs}, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"Saved {OUT.relative_to(ROOT).as_posix()}")

    if failing:
        sys.exit(1)


if __name__ == "__main__":
    main()
