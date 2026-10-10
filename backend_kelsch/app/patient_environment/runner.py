"""Run an authored encounter and retain replayable, source-linked state traces.

Intents are inputs, not inferred labels. This module does not train or grade a model.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

from app.encounter import engine, phraser, verifier
from app.schemas.case import Case
from app.schemas.encounter import Hit, Intent


@dataclass(frozen=True)
class ScriptTurn:
    utterance: str
    intent: Intent


def tagged_turn(utterance: str, *, topics: tuple[str, ...] = (),
                empathy: str | None = None, introduction: bool = False,
                question_type: str = "closed") -> ScriptTurn:
    """Tag a test utterance explicitly; spans quote the supplied student words."""
    hits = [Hit(id=t, span=utterance) for t in topics]
    if introduction:
        hits.append(Hit(id="greeting_introduction", span=utterance))
    return ScriptTurn(utterance, Intent(topics=hits,
        empathy=[Hit(id=empathy, span=utterance)] if empathy else [],
        question_type=question_type))


# Engineering probes only. Faculty has not calibrated or published these vectors.
PRESET_OFFSETS = {"straightforward": -2, "typical": 0, "difficult": 2}


def with_probe_preset(case: Case, preset: str) -> Case:
    if preset not in PRESET_OFFSETS:
        raise ValueError(f"unsupported probe preset: {preset}")
    changed = case.model_copy(deep=True)
    offset = PRESET_OFFSETS[preset]
    for tier in ("reluctant", "hidden"):
        changed.trust.thresholds[tier] = case.trust.thresholds[tier] + offset
    changed.difficulty.preset = preset
    changed.difficulty.params = {"probe_threshold_offset": offset}
    return changed


def case_source(path: Path) -> dict:
    raw = path.read_bytes()
    return {"path": str(path), "sha256": sha256(raw).hexdigest()}


def student_view(state: dict) -> dict:
    """Information visible to a student at this point, excluding hidden engine state."""
    return {"disclosed_fact_ids": sorted(state["disclosed"]),
            "chart": deepcopy(state["chart"])}


def fact_for_role(case: Case, state: dict, fact_id: str, role: str):
    """Deny unknown roles and unreleased facts; faculty sees approved source material."""
    if role not in {"faculty", "student"}:
        raise PermissionError(f"unknown role: {role}")
    fact = case.fact(fact_id)
    if fact is None or fact.status != "approved":
        raise PermissionError(f"fact unavailable: {fact_id}")
    if role == "student" and fact_id not in state["disclosed"]:
        raise PermissionError(f"fact not disclosed: {fact_id}")
    return fact


def run_script(case: Case, turns: list[ScriptTurn], *, source: dict | None = None) -> dict:
    """Replay the disclosure engine with fixed intents and deterministic template speech."""
    state = engine.new_state(case)
    trace = []
    for item in turns:
        before = deepcopy(state)
        result, state = engine.process_turn(case, state, item.intent, item.utterance)
        reply, cited = phraser.template_reply(case, result, item.intent.topic_ids(),
                                                 item.intent.action_ids(), bool(item.intent.empathy))
        problems = verifier.deterministic_checks(case, reply, cited,
            result.allowed_fact_ids, list(before["disclosed"]) + result.repeat_fact_ids, item.utterance)
        if problems or not set(cited) <= set(state["disclosed"]):
            raise ValueError(f"template grounding failure: {problems} {cited}")
        for event in result.trust_events:
            if not event.span or event.span not in item.utterance:
                raise ValueError("trust event lacks an exact student span")
        trace.append({"turn": state["turn"], "utterance": item.utterance,
            "intent": item.intent.model_dump(), "trust_before": before["trust"],
            "trust_after": state["trust"], "trust_events": [e.model_dump() for e in result.trust_events],
            "allowed_fact_ids": result.allowed_fact_ids,
            "disclosures": [d.model_dump() for d in result.disclosures],
            "withheld": [w.model_dump() for w in result.withheld],
            "reply": reply, "cited_fact_ids": cited,
            "fact_sources": {fid: case.fact(fid).source.model_dump() for fid in cited},
            "chart_releases": [r.model_dump() for r in result.chart_releases],
            "repeat_fact_ids": result.repeat_fact_ids, "is_repeat": result.is_repeat,
            "student_view": student_view(state),
            "state_after": deepcopy(state)})
    return {"case_id": case.case_id, "case_version": case.version,
            "difficulty": case.difficulty.model_dump(), "source": source,
            "turns": trace, "final_state": deepcopy(state)}


def fingerprint(trace: dict) -> str:
    """Stable digest of the complete state and turn events, excluding timing and file paths."""
    payload = {k: v for k, v in trace.items() if k != "source"}
    return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def replay(trace: dict, case: Case) -> dict:
    if trace["case_id"] != case.case_id or trace["case_version"] != case.version:
        raise ValueError("case identity/version differs from replay log")
    turns = [ScriptTurn(row["utterance"], Intent.model_validate(row["intent"]))
             for row in trace["turns"]]
    return run_script(case, turns, source=trace.get("source"))
