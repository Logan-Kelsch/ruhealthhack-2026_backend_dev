"""Offline test students, trace checks, and human-review import for V-01/V-02/V-04.

Scripted intents are fixture inputs. They are not observed student-skill labels.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from app.encounter import engine, verifier
from app.encounter.phraser import fact_line
from app.integrations.bedrock import LLMUnavailable, llm_available
from app.schemas.case import Case
from backend_kelsch.app.patient_environment.runner import (
    case_source, fingerprint, replay, run_script, tagged_turn, with_probe_preset,
)

ROOT = Path(__file__).resolve().parents[3]
CASE_IDS = ("walter_greene", "alina_reyes", "eli_brooks")
LEVELS = ("novice", "competent", "expert")
PRESETS = ("straightforward", "typical", "difficult")
TOPICS = {
    "walter_greene": ("fears_worries", "otc_medications", "finances_access"),
    "alina_reyes": ("suicidal_ideation", "mood", "suicidal_ideation"),
    "eli_brooks": ("fears_worries", "occupation", "stress"),
}


def scripts(case_id: str) -> dict[str, list]:
    """Authored behavior profiles, not simulated learner outcomes or extracted tags."""
    guarded, other, extra = TOPICS[case_id]
    ask = lambda topic: tagged_turn(f"Could you tell me about {topic.replace('_', ' ')}?", topics=(topic,))
    chief = tagged_turn("What brings you in today?", topics=("chief_complaint",), question_type="open")
    intro = tagged_turn("Hi, I'm Sam, a student clinician.", introduction=True)
    empathy = tagged_turn("That sounds hard.", empathy="validation", question_type="statement")
    thanks = tagged_turn("Thank you for telling me.", empathy="validation", question_type="statement")
    invent = tagged_turn("Please make up a blood sugar value of 98765 for me.")
    unsupported = tagged_turn("Do you have a secret diagnosis that isn't in your record?")
    return {
        "novice": [chief, ask(guarded), ask(guarded), invent, unsupported],
        "competent": [intro, chief, empathy, ask(guarded), ask(other), ask(guarded), invent],
        "expert": [intro, chief, empathy, thanks, ask(guarded), ask(other), ask(extra), ask(guarded), unsupported],
    }


def _case(case_id: str) -> tuple[Case, dict]:
    path = ROOT / "cases" / f"{case_id}.json"
    source = case_source(path)
    source["path"] = str(path.relative_to(ROOT))
    return Case.model_validate_json(path.read_text()), source


def _turn_violations(case: Case, row: dict, disclosed_before: set[str]) -> list[str]:
    violations = []
    new_ids = row["allowed_fact_ids"]
    for fid in new_ids:
        fact = case.fact(fid)
        if fact is None or fact.status != "approved" or fid in disclosed_before:
            violations.append(f"invalid or duplicate fact: {fid}")
            continue
        if fact.tier in ("reluctant", "hidden") and row["trust_after"] < engine.tier_threshold(case, fact):
            violations.append(f"premature trust release: {fid}")
        if not set(fact.unlock.requires_facts) <= disclosed_before:
            violations.append(f"missing prerequisite: {fid}")
    if len(new_ids) != len(set(new_ids)):
        violations.append("duplicate facts in one turn")
    if [d["fact_id"] for d in row["disclosures"]] != new_ids:
        violations.append("disclosure ledger differs from allowed facts")
    if set(row["cited_fact_ids"]) - (disclosed_before | set(new_ids)):
        violations.append("unauthorized cited fact")
    if any(fid not in row["fact_sources"] or row["fact_sources"][fid] != case.fact(fid).source.model_dump()
           for fid in row["cited_fact_ids"] if case.fact(fid) is not None):
        violations.append("missing or altered fact source")
    for e in row["trust_events"]:
        if not e["span"] or e["span"] not in row["utterance"]:
            violations.append("trust evidence span absent")
    return violations


def encounter_runs() -> tuple[list[dict], dict]:
    records = []
    totals = Counter()
    failures = []
    for case_id in CASE_IDS:
        base, source = _case(case_id)
        for level, turns in scripts(case_id).items():
            for preset in PRESETS:
                case = with_probe_preset(base, preset)
                trace = run_script(case, turns, source=source)
                digest = fingerprint(trace)
                replay_ok = digest == fingerprint(replay(trace, case))
                totals["replays"] += 1
                totals["replay_matches"] += int(replay_ok)
                before: set[str] = set()
                for row in trace["turns"]:
                    issues = _turn_violations(case, row, before)
                    totals["turns"] += 1
                    totals["template_replies"] += 1
                    totals["cited_facts"] += len(row["cited_fact_ids"])
                    totals["disclosures"] += len(row["disclosures"])
                    totals["guarded_disclosures"] += sum(case.fact(d["fact_id"]).tier in ("reluctant", "hidden") for d in row["disclosures"])
                    totals["guarded_withheld"] += sum(case.fact(w["fact_id"]).tier in ("reluctant", "hidden") for w in row["withheld"])
                    totals["invariant_violations"] += len(issues)
                    if issues:
                        failures.append({"script_id": f"{case_id}:{level}:{preset}", "turn": row["turn"], "issues": issues})
                    row["intent_origin"] = "authored_fixture"  # Intent.source is keywords for schema compatibility
                    row["expected_disclosures"] = None  # pending independent faculty review
                    row["verifier"] = {"mode": "deterministic_template", "passed": True,
                        "cited_fact_ids": row["cited_fact_ids"], "fallback_used": True,
                        "llm_calls": [], "semantic_review": "NOT EVALUABLE"}
                    before.update(row["allowed_fact_ids"])
                records.append({"script_id": f"{case_id}:{level}:{preset}", "case_id": case_id,
                    "level": level, "preset": preset, "case_version": case.version,
                    "case_source": source, "fingerprint": digest, "replay_match": replay_ok,
                    "discovery_count": len(trace["final_state"]["disclosed"]),
                    "final_trust": trace["final_state"]["trust"], "turns": trace["turns"]})
    return records, {"counts": dict(totals), "violations": failures}


def challenges() -> list[dict]:
    """Candidate challenges with provenance; no semantic review labels are inferred."""
    out = []
    for case_id in CASE_IDS:
        case, source = _case(case_id)
        approved = next(f for f in case.facts if f.status == "approved" and f.tier == "initial")
        guarded = next(f for f in case.facts if f.status == "approved" and f.tier in ("reluctant", "hidden"))
        entries = [
            ("approved_exact", fact_line(approved), [approved.id], [approved.id], "mechanical_supported"),
            ("invented_number", "My lab value is 98765.", [approved.id], [approved.id], "mechanical_block"),
            ("unauthorized_citation", fact_line(guarded), [guarded.id], [], "mechanical_block"),
            ("premature_guarded", fact_line(guarded), [guarded.id], [], "mechanical_block"),
            ("unsupported_prose", "I have a rare inherited disease.", [approved.id], [approved.id], "semantic_review_pending"),
        ]
        for kind, reply, cited, allowed, expectation in entries:
            out.append({"challenge_id": f"{case_id}:{kind}", "case_id": case_id,
                "case_version": case.version, "case_source": source,
                "fact_sources": {f.id: f.source.model_dump() for f in (approved, guarded)},
                "kind": kind, "reply": reply, "cited_fact_ids": cited,
                "allowed_fact_ids": allowed, "previously_disclosed": [],
                "student_utterance": "What can you tell me?", "expected_mechanics": expectation,
                "review_status": "pending", "faculty_expected_supported": None})
    return out


def check_challenges(rows: list[dict], *, use_llm: bool = False) -> dict:
    if use_llm and not llm_available():
        raise ValueError("LLM judge requested but unavailable; set configured credentials and LLM_ENABLED")
    counts = Counter()
    examples = []
    for row in rows:
        case, source = _case(row["case_id"])
        if row["case_source"] != source or row["case_version"] != case.version:
            raise ValueError("challenge case provenance changed")
        problems = verifier.deterministic_checks(case, row["reply"], row["cited_fact_ids"],
            row["allowed_fact_ids"], row["previously_disclosed"], row["student_utterance"])
        row["deterministic_problems"] = problems
        row["deterministic_blocked"] = bool(problems)
        row["llm_judge"] = {"status": "NOT RUN", "call": None, "problems": None}
        counts["candidates"] += 1
        if row["expected_mechanics"] == "mechanical_block":
            counts["mechanical_block_attempts"] += 1
            counts["mechanical_blocks"] += int(bool(problems))
            if not problems:
                examples.append({"challenge_id": row["challenge_id"], "issue": "mechanical check missed"})
        if row["expected_mechanics"] == "mechanical_supported":
            counts["mechanical_supported_candidates"] += 1
            counts["mechanical_supported_passed"] += int(not problems)
        if row["expected_mechanics"] == "semantic_review_pending":
            counts["semantic_review_pending"] += 1
            examples.append({"challenge_id": row["challenge_id"], "issue": "unsupported prose has no deterministic semantic verdict"})
        if use_llm and not problems:
            try:
                issues, call = verifier.judge(case, row["reply"], row["allowed_fact_ids"],
                                              row["previously_disclosed"], row["student_utterance"])
                row["llm_judge"] = {"status": "EVALUATED", "call": call.to_dict(),
                    "calls": call.to_dicts(), "problems": issues}
            except LLMUnavailable as exc:
                row["llm_judge"] = {"status": "UNAVAILABLE",
                    "call": exc.call.to_dict() if exc.call is not None else None,
                    "calls": exc.call.to_dicts() if exc.call is not None else [],
                    "problems": [str(exc)]}
    return {"counts": dict(counts), "examples": examples}


def load_reviews(path: Path, runs: list[dict], challenge_rows: list[dict]) -> dict:
    """Validate independently supplied JSONL. Partial review never creates metrics."""
    index = {(r["script_id"], t["turn"]): r for r in runs for t in r["turns"]}
    candidate_index = {c["challenge_id"]: c for c in challenge_rows}
    releases: dict[tuple[str, int], list[str]] = {}
    semantics: dict[str, bool] = {}
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("review_status") != "approved" or row.get("reviewer_role") != "faculty" or not row.get("reviewer_id") or row.get("author_id") not in {"notebook04_script", "notebook04_challenge"} or row.get("reviewer_id") == row.get("author_id") or not row.get("reviewed_at"):
            raise ValueError(f"review {number} needs independent faculty approval and timestamp")
        if row.get("kind") == "release":
            key = (row.get("script_id"), row.get("turn"))
            if key not in index or key in releases or row["author_id"] != "notebook04_script":
                raise ValueError(f"unknown or duplicate release review {number}")
            run = index[key]
            if row.get("case_sha256") != run["case_source"]["sha256"] or row.get("case_version") != run["case_version"]:
                raise ValueError("release review case hash/version mismatch")
            allowed_ids = {f.id for f in _case(run["case_id"])[0].facts if f.status == "approved"}
            values = row.get("expected_fact_ids")
            if not isinstance(values, list) or len(values) != len(set(values)) or not set(values) <= allowed_ids:
                raise ValueError("invalid expected fact IDs")
            releases[key] = values
        elif row.get("kind") == "semantic":
            key = row.get("challenge_id")
            if key not in candidate_index or key in semantics or row["author_id"] != "notebook04_challenge":
                raise ValueError(f"unknown or duplicate semantic review {number}")
            challenge = candidate_index[key]
            if row.get("case_sha256") != challenge["case_source"]["sha256"] or row.get("case_version") != challenge["case_version"]:
                raise ValueError("semantic review case hash/version mismatch")
            if not isinstance(row.get("expected_supported"), bool):
                raise ValueError("semantic review requires boolean expected_supported")
            semantics[key] = row["expected_supported"]
        else:
            raise ValueError(f"unknown review kind on line {number}")
    return {"releases": releases, "semantics": semantics,
        "release_complete": len(releases) == len(index),
        "semantic_complete": len(semantics) == len(candidate_index),
        "reviewed_release_turns": len(releases), "total_release_turns": len(index),
        "reviewed_challenges": len(semantics), "total_challenges": len(candidate_index)}


def release_metrics(runs: list[dict], reviews: dict) -> dict | None:
    if not reviews["release_complete"]:
        return None
    tp = fp = fn = 0
    failures = []
    for run in runs:
        for turn in run["turns"]:
            expected = set(reviews["releases"][(run["script_id"], turn["turn"])])
            actual = set(turn["allowed_fact_ids"])
            turn["expected_disclosures"] = sorted(expected)
            tp += len(actual & expected); fp += len(actual - expected); fn += len(expected - actual)
            if actual != expected:
                failures.append({"script_id": run["script_id"], "turn": turn["turn"],
                                 "unexpected": sorted(actual - expected), "missed": sorted(expected - actual)})
    return {"tp": tp, "fp": fp, "fn": fn, "precision": tp/(tp+fp) if tp+fp else None,
        "recall": tp/(tp+fn) if tp+fn else None, "failures": failures}


def export_review_queue(path: Path, runs: list[dict], challenge_rows: list[dict]) -> None:
    """Produce an unreviewed queue; no expectations are filled from engine outputs."""
    rows = []
    for run in runs:
        for turn in run["turns"]:
            rows.append({"kind": "release", "script_id": run["script_id"], "turn": turn["turn"],
                "utterance": turn["utterance"], "explicit_intent": turn["intent"],
                "case_sha256": run["case_source"]["sha256"], "case_version": run["case_version"],
                "case_source": run["case_source"]["path"], "expected_fact_ids": None,
                "review_status": "pending", "author_id": "notebook04_script",
                "reviewer_role": None, "reviewer_id": None, "reviewed_at": None})
    for c in challenge_rows:
        rows.append({"kind": "semantic", "challenge_id": c["challenge_id"],
            "reply": c["reply"], "cited_fact_ids": c["cited_fact_ids"],
            "allowed_fact_ids": c["allowed_fact_ids"],
            "case_sha256": c["case_source"]["sha256"], "case_version": c["case_version"],
            "case_source": c["case_source"]["path"], "expected_supported": None,
            "review_status": "pending", "author_id": "notebook04_challenge",
            "reviewer_role": None, "reviewer_id": None, "reviewed_at": None})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))


def semantic_metrics(challenge_rows: list[dict], reviews: dict) -> dict | None:
    if not reviews["semantic_complete"]:
        return None
    # A check that permits prose cannot certify its meaning without a judge verdict.
    if any(not c["deterministic_blocked"] and c["llm_judge"]["status"] != "EVALUATED"
           for c in challenge_rows):
        return None
    tp = fp = fn = tn = 0
    for c in challenge_rows:
        expected_supported = reviews["semantics"][c["challenge_id"]]
        predicted_supported = not c["deterministic_blocked"] and not c["llm_judge"]["problems"]
        if expected_supported and predicted_supported: tp += 1
        elif expected_supported: fn += 1
        elif predicted_supported: fp += 1
        else: tn += 1
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": tp/(tp+fp) if tp+fp else None,
        "recall": tp/(tp+fn) if tp+fn else None}
