"""Run deterministic, authored probes; no external dialogue or model calls.

From the repository root: LLM_ENABLED=false PYTHONPATH=backend python -m scripts.eval_patient_environment
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.encounter.verifier import deterministic_checks
from app.patient_environment.runner import (
    PRESET_OFFSETS, case_source, fact_for_role, fingerprint, replay, run_script,
    tagged_turn, with_probe_preset,
)
from app.schemas.case import Case

ROOT = Path(__file__).resolve().parents[2]


def load(case_id: str) -> tuple[Case, dict]:
    path = ROOT / "cases" / f"{case_id}.json"
    source = case_source(path)
    source["path"] = str(path.relative_to(ROOT))
    return Case.model_validate_json(path.read_text()), source


def scenario():
    return [
        tagged_turn("What worries you most about all this?", topics=("fears_worries",), question_type="open"),
        tagged_turn("Hi, I'm Sam, a dietetics student.", introduction=True),
        tagged_turn("That sounds hard.", empathy="validation", question_type="statement"),
        tagged_turn("Thank you for telling me.", empathy="validation", question_type="statement"),
        tagged_turn("What worries you most about all this?", topics=("fears_worries",), question_type="open"),
        tagged_turn("What worries you most about all this?", topics=("fears_worries",), question_type="open"),
    ]


def evaluate() -> dict:
    case, source = load("walter_greene")
    traces = {p: run_script(with_probe_preset(case, p), scenario(), source=source) for p in PRESET_OFFSETS}
    checks = {}

    def check(name: str, passed: bool, detail: str):
        checks[name] = {"status": "PASS" if passed else "FAIL", "detail": detail}

    first = traces["typical"]["turns"][0]
    check("premature_disclosure", "f_failed_family" not in first["allowed_fact_ids"]
          and "f_scared_future" not in first["allowed_fact_ids"]
          and {w["fact_id"] for w in first["withheld"]} >= {"f_failed_family", "f_scared_future"},
          "At trust 0, both guarded facts remain withheld on an on-topic question.")
    fifth = traces["typical"]["turns"][4]
    check("expected_transition", fifth["trust_after"] == 3 and "f_failed_family" in fifth["allowed_fact_ids"]
          and "f_scared_future" not in fifth["allowed_fact_ids"],
          "Three sourced rapport events unlock the reluctant fact, but not the hidden fact.")
    check("memory", traces["typical"]["turns"][5]["is_repeat"]
          and "f_failed_family" not in traces["typical"]["turns"][5]["allowed_fact_ids"],
          "Previously disclosed facts are recalled without a second disclosure entry.")
    check("trust_evidence", all(e["span"] in row["utterance"] for row in traces["typical"]["turns"]
          for e in row["trust_events"]), "Every trust event has a verbatim student span.")
    check("difficulty_order", len(traces["straightforward"]["final_state"]["disclosed"]) >
          len(traces["typical"]["final_state"]["disclosed"]) >
          len(traces["difficult"]["final_state"]["disclosed"]),
          "Same authored script; threshold vectors yield strictly ordered discovery counts.")
    check("deterministic_replay", all(fingerprint(t) == fingerprint(replay(t, with_probe_preset(case, p)))
          for p, t in traces.items()), "Replayed intents reproduce full state and event trace on all three presets.")
    denied = False
    try:
        fact_for_role(case, traces["typical"]["turns"][0]["state_after"], "f_scared_future", "student")
    except PermissionError:
        denied = True
    check("unauthorized_knowledge", denied and "f_scared_future" not in first["student_view"]["disclosed_fact_ids"],
          "Student view and fact lookup deny the undisclosed hidden fact.")
    problems = deterministic_checks(case, "My A1C is 9.4.", ["f_soda"], ["f_soda"], [], "What about soda?")
    citation_problems = deterministic_checks(case, "I'm scared.", ["f_scared_future"], [], [], "How are you?")
    check("unsupported_reply", any("numbers" in p for p in problems) and
          any("not allowed" in p for p in citation_problems),
          "Unbacked numeric claim and citation to a withheld fact are rejected.")
    alina, alina_source = load("alina_reyes")
    a = run_script(alina, [
        tagged_turn("Have you had thoughts of ending your life?", topics=("suicidal_ideation",)),
        tagged_turn("Hi, I'm Sam, a medical student.", introduction=True),
        tagged_turn("Have you had thoughts of ending your life?", topics=("suicidal_ideation",)),
        tagged_turn("Have you thought about how you would end your life, or made a plan?", topics=("suicidal_ideation",)),
    ], source=alina_source)
    check("dependency_and_screening", "f_passive_si" not in a["turns"][0]["allowed_fact_ids"]
          and not any(e["delta"] < 0 for e in a["turns"][0]["trust_events"])
          and "f_passive_si" in a["turns"][2]["allowed_fact_ids"]
          and "f_no_plan" in a["turns"][3]["allowed_fact_ids"],
          "SI screening costs no trust; prerequisite fact appears before plan detail.")
    check("provenance", all(row["fact_sources"].get(fid, {}).get("kind") for t in traces.values()
          for row in t["turns"] for fid in row["cited_fact_ids"]),
          "Every cited fact links to a source entry in the authored case.")
    counts = {p: len(t["final_state"]["disclosed"]) for p, t in traces.items()}
    passed = sum(c["status"] == "PASS" for c in checks.values())
    return {"stage": "Notebook 03", "method": "authored deterministic probes; no trained extractor",
        "sources": [source, alina_source, "PRD.md §9.1, §9.3, §9.4, V-01/V-02/V-04", "docs/validation/action_data.json"],
        "checks": checks, "passed": passed, "total": len(checks),
        "discovery_counts_by_probe_preset": counts,
        "gates": {
            "controlled_environment": "PASS" if passed == len(checks) else "FAIL",
            "trained_action_extraction": "NOT EVALUABLE",
            "clinical_semantic_grounding": "NOT EVALUABLE",
            "difficulty_calibration": "NOT EVALUABLE",
            "student_learning": "NOT EVALUABLE",
        },
        "limitations": ["The intents and expected transitions are authored probes, not reviewed student labels.",
          "Preset vectors adjust trust thresholds only; explicit per-fact min_trust overrides remain unchanged. Faculty calibration and V-04 significance are pending.",
          "Deterministic checks catch uncited facts and stray numbers, not arbitrary unsupported prose. No LLM judge was invoked.",
          "The local role view demonstrates fact visibility; production API authorization was not evaluated.",
          "Notebook 02 trained model gates remain blocked by absent reviewed labels and unlicensed external content."],
        "next_notebook": "Notebook 04: scripted test students and verifier challenge set; measure grounded template delivery and disclosure against independent faculty reviewed expectations, keep trained extraction blocked until reviewed split data exist."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="JSON report path")
    args = parser.parse_args()
    report = evaluate()
    body = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body)
    print(body)
    if report["gates"]["controlled_environment"] == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
