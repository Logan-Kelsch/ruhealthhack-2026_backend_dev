"""Versioned pipeline probes on authored student turns, never learner outcomes."""
from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter

from app.encounter import engine, pipeline, verifier
from app.integrations.bedrock import load_prompt, llm_available
from app.settings import get_settings
from backend_kelsch.app.grounding.evaluation import (
    CASE_IDS, LEVELS, ROOT, _case, challenges, check_challenges, scripts,
)
from backend_kelsch.app.patient_environment.runner import with_probe_preset

VERSION = "live_grounding_v1"
PROMPTS = ("classifier", "phraser", "verifier")


def extra_challenges() -> list[dict]:
    """Source-linked hypotheses; none is a faculty-supported semantic label."""
    rows = []
    for case_id in CASE_IDS:
        case, source = _case(case_id)
        fact = next(f for f in case.facts if f.status == "approved" and f.tier == "initial")
        entries = (
            ("negated_history", "I have never had any health concerns.", "What about your health?"),
            ("echoed_invented_value", "My blood sugar is 98765.", "My blood sugar is 98765."),
            ("wrong_unit", f"My blood sugar is {case.profile.age} milligrams per deciliter.", "How is your blood sugar?"),
            ("unsupported_conclusion", "I definitely have cancer.", "What do you think this means?"),
        )
        for kind, reply, utterance in entries:
            rows.append({"challenge_id": f"{case_id}:{kind}", "case_id": case_id,
                "case_version": case.version, "case_source": source,
                "fact_sources": {fact.id: fact.source.model_dump()},
                "kind": kind, "reply": reply, "cited_fact_ids": [fact.id],
                "allowed_fact_ids": [fact.id], "previously_disclosed": [],
                "student_utterance": utterance, "expected_mechanics": "semantic_review_pending",
                "review_status": "pending", "faculty_expected_supported": None})
    return rows


def pricing_snapshot(path: Path | None) -> dict | None:
    if path is None:
        return None
    raw = path.read_bytes()
    data = json.loads(raw)
    if (data.get("currency") != "USD" or not str(data.get("source_url", "")).startswith("https://")
            or not data.get("effective_date") or not data.get("region")
            or not isinstance(data.get("models"), dict) or not data["models"]):
        raise ValueError("pricing requires USD, source_url, effective_date, region and model rates")
    for rates in data["models"].values():
        if not isinstance(rates, dict) or any(type(rates.get(k)) not in (int, float) or rates[k] < 0
                for k in ("input_usd_per_million", "output_usd_per_million")):
            raise ValueError("input/output token rates must be nonnegative numbers")
    return {"sha256": sha256(raw).hexdigest(), **data}


def price_calls(calls: list[dict], prices: dict | None, region: str) -> dict:
    """An incomplete rate or usage record leaves the total unknown."""
    totals = defaultdict(lambda: {"calls": 0, "input_tokens": 0, "output_tokens": 0,
                                  "unknown_usage_calls": 0, "latency_ms": 0})
    unknown = 0
    priced = []
    for call in calls:
        bucket = totals[call["purpose"]]
        bucket["calls"] += 1
        bucket["latency_ms"] += call["latency_ms"]
        incoming, outgoing = call.get("input_tokens"), call.get("output_tokens")
        if type(incoming) is int and type(outgoing) is int and incoming >= 0 and outgoing >= 0:
            bucket["input_tokens"] += incoming
            bucket["output_tokens"] += outgoing
        else:
            bucket["unknown_usage_calls"] += 1
        rates = prices["models"].get(call["model"]) if prices and prices["region"] == region else None
        if (not rates or type(incoming) is not int or type(outgoing) is not int
                or incoming < 0 or outgoing < 0
                or call.get("cache_read_input_tokens") or call.get("cache_write_input_tokens")):
            call["estimated_cost_usd"] = None
            unknown += 1
        else:
            call["estimated_cost_usd"] = round((incoming * rates["input_usd_per_million"]
                + outgoing * rates["output_usd_per_million"]) / 1_000_000, 10)
            priced.append(call["estimated_cost_usd"])
    return {"model_calls": len(calls), "by_purpose": dict(totals),
        "estimated_total_usd": round(sum(priced), 8) if unknown == 0 else None,
        "unpriced_calls": unknown, "pricing_status": "NO_MODEL_CALLS" if not calls
            else "COMPLETE" if unknown == 0 else "INCOMPLETE",
        "pricing_source": None if prices is None else {k: prices[k] for k in ("sha256", "source_url", "effective_date", "region")}}


def credentials_ready() -> bool:
    """No inference or identity request; check only whether the SDK finds credentials."""
    if not llm_available():
        return False
    import boto3
    settings = get_settings()
    try:
        session = boto3.Session(profile_name=settings.aws_profile, region_name=settings.aws_region)
        return session.get_credentials() is not None
    except Exception:
        return False


def evaluate(*, mode: str = "offline", pricing_path: Path | None = None) -> tuple[dict, dict]:
    if mode not in {"offline", "live"}:
        raise ValueError("mode must be offline or live")
    if mode == "offline" and llm_available():
        raise ValueError("offline evaluation requires LLM_ENABLED=false")
    if mode == "live" and not credentials_ready():
        raise ValueError("live evaluation requires configured model access and credentials")
    settings = get_settings()
    prices = pricing_snapshot(pricing_path)
    if prices and prices["region"] != settings.aws_region:
        raise ValueError("price snapshot region differs from configured AWS region")
    code_paths = ("backend_kelsch/app/grounding/live.py",
                  "backend_kelsch/app/grounding/evaluation.py",
                  "backend_kelsch/scripts/eval_live_grounding.py",
                  "backend/app/encounter/pipeline.py", "backend/app/encounter/verifier.py",
                  "backend/app/integrations/bedrock.py")
    sources = {"cases": {}, "prompts": {},
        "code_sha256": {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in code_paths},
        "notebook_04_report_sha256": sha256(
        (ROOT / "backend_kelsch/docs/validation/grounding_eval.json").read_bytes()).hexdigest()}
    for name in PROMPTS:
        path = ROOT / "backend/app/prompts" / f"{name}.md"
        _, version = load_prompt(name)
        sources["prompts"][name] = {"version": version, "sha256": sha256(path.read_bytes()).hexdigest()}
    records = []
    all_calls = []
    violations = []
    for case_id in CASE_IDS:
        base, source = _case(case_id)
        sources["cases"][case_id] = {**source, "version": base.version}
        case = with_probe_preset(base, "typical")
        for level in LEVELS:
            state, history, turns = engine.new_state(case), [], []
            for index, item in enumerate(scripts(case_id)[level], 1):
                previous = set(state.get("disclosed", {}))
                outcome = pipeline.run_turn(case, state, item.utterance, history)
                state = outcome.state
                problems = verifier.deterministic_checks(case, outcome.reply_text,
                    outcome.cited_fact_ids, outcome.engine.allowed_fact_ids,
                    list(previous) + outcome.engine.repeat_fact_ids, item.utterance)
                if set(outcome.cited_fact_ids) - set(state["disclosed"]):
                    problems.append("delivered reply cites an unreleased fact")
                if problems:
                    violations.append({"case_id": case_id, "level": level, "turn": index, "problems": problems})
                calls = outcome.llm_calls
                all_calls.extend(calls)
                reviewed_status = "template_source_linked_unreviewed" if outcome.fallback_used else (
                    "judge_passed_unreviewed" if any(c["purpose"] == "verify" and c["ok"] for c in calls)
                    else "unchecked_generated_reply")
                turns.append({"turn": index, "utterance": item.utterance,
                    "authored_fixture_intent": item.intent.model_dump(),
                    "classified_intent": outcome.intent.model_dump(), "intent_origin": "pipeline_prediction",
                    "allowed_fact_ids": outcome.engine.allowed_fact_ids,
                    "disclosures": [x.model_dump() for x in outcome.engine.disclosures],
                    "trust_events": [x.model_dump() for x in outcome.engine.trust_events],
                    "delivered_reply": outcome.reply_text, "cited_fact_ids": outcome.cited_fact_ids,
                    "cited_fact_sources": {fid: case.fact(fid).source.model_dump() for fid in outcome.cited_fact_ids if case.fact(fid)},
                    "verifier": outcome.verifier, "fallback_used": outcome.fallback_used,
                    "delivery_checks": problems, "semantic_status": reviewed_status,
                    "latency_ms": outcome.latency_ms, "llm_calls": calls})
                history.append((item.utterance, outcome.reply_text))
            records.append({"script_id": f"{case_id}:{level}:typical", "case_id": case_id,
                "case_version": case.version, "case_source": source, "level": level,
                "preset": "typical", "turns": turns})
    challenge_rows = challenges() + extra_challenges()
    challenge_counts = Counter()
    for row in challenge_rows:
        t0 = perf_counter()
        result = check_challenges([row], use_llm=mode == "live")
        row["latency_ms"] = int((perf_counter() - t0) * 1000)
        challenge_counts.update(result["counts"])
        call = row["llm_judge"]["call"]
        row["llm_calls"] = [call] if call else []
        all_calls.extend(row["llm_calls"])
        row["semantic_status"] = "mechanically_blocked" if row["deterministic_blocked"] else (
            "unchecked_semantic" if row["llm_judge"]["status"] != "EVALUATED" else
            "judge_rejected_unreviewed" if row["llm_judge"]["problems"] else "judge_passed_unreviewed")
    cost = price_calls(all_calls, prices, settings.aws_region)
    turns = [t for run in records for t in run["turns"]]
    decision_counts = dict(Counter(t["semantic_status"] for t in turns))
    unchecked = [r["challenge_id"] for r in challenge_rows if r["semantic_status"] == "unchecked_semantic"]
    report = {"version": VERSION, "mode": mode,
        "scope": "authored engineering probes; no reviewed clinical/student labels",
        "sources": sources, "model_config": {"region": settings.aws_region,
            "fast_model_id": settings.bedrock_model_fast, "strong_model_id": settings.bedrock_model_strong,
            "invoked": mode == "live"},
        "scripts": len(records), "turns": len(turns), "cases": len(CASE_IDS),
        "delivered": {"replies": len(turns), "fallback_replies": sum(t["fallback_used"] for t in turns),
            "fallback_rate": sum(t["fallback_used"] for t in turns) / len(turns),
            "verifier_blocked_attempts": sum(t["verifier"]["blocked_attempts"] for t in turns),
            "semantic_status_counts": decision_counts, "delivery_violations": violations},
        "challenges": {"total": len(challenge_rows), "counts": dict(challenge_counts),
            "semantic_status_counts": dict(Counter(r["semantic_status"] for r in challenge_rows)),
            "unchecked_semantic_ids": unchecked}, "usage_and_cost": cost,
        "gates": {"delivered_source_checks": "FAIL" if violations else "PASS",
            "mechanical_challenges": "PASS" if challenge_counts["mechanical_blocks"] == challenge_counts["mechanical_block_attempts"]
                and challenge_counts["mechanical_supported_passed"] == challenge_counts["mechanical_supported_candidates"] else "FAIL",
            "clinical_grounding": "NOT EVALUABLE", "semantic_accuracy": "NOT EVALUABLE",
            "student_performance": "NOT EVALUABLE"},
        "limitations": ["Authored student turns and case text are not observed learners or independent clinical labels.",
            "A mechanically permitted reply, a template citation, or a judge pass is not faculty-reviewed semantic grounding.",
            "Usage is unavailable when a model request fails before Bedrock returns a response.",
            "Cost is unknown unless every call has usage and a sourced rate for its exact model and region."]}
    return report, {"version": VERSION, "mode": mode, "runs": records, "challenges": challenge_rows}
