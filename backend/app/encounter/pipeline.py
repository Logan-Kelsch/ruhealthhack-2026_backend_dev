"""One turn: classify -> engine -> phrase -> verify -> (retry once) -> template fallback.

No database access here; services.py persists the outcome.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.encounter import classifier, engine, phraser, verifier
from app.integrations.bedrock import LLMUnavailable, llm_available
from app.schemas.case import Case
from app.schemas.encounter import EngineResult, Intent


@dataclass
class TurnOutcome:
    intent: Intent
    engine: EngineResult
    state: dict
    reply_text: str
    cited_fact_ids: list[str]
    verifier: dict
    audio_tags: list[str]
    latency_ms: dict
    llm_calls: list[dict] = field(default_factory=list)
    fallback_used: bool = False


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


def run_turn(
    case: Case,
    state: dict,
    utterance: str,
    history: list[tuple[str, str]],
    barge_in_remaining_ms: int | None = None,
) -> TurnOutcome:
    latency: dict[str, int] = {}
    calls: list[dict] = []
    t_all = time.perf_counter()

    t0 = time.perf_counter()
    last_patient = history[-1][1] if history else None
    intent, c_calls = classifier.classify(utterance, case, last_patient)
    calls += [c.to_dict() for c in c_calls]
    latency["classify"] = _ms(t0)

    t0 = time.perf_counter()
    previously = list(state.get("disclosed", {}).keys())
    res, new_state = engine.process_turn(case, state, intent, utterance, barge_in_remaining_ms)
    latency["engine"] = _ms(t0)

    attempts: list[dict] = []
    reply, cited, fallback = "", [], False
    if llm_available():
        retry_reason = None
        for attempt in range(2):
            t0 = time.perf_counter()
            try:
                text, cit, p_calls = phraser.phrase(case, res, utterance, history, previously, retry_reason)
                calls += [c.to_dict() for c in p_calls]
            except LLMUnavailable as exc:
                attempts.append({"attempt": attempt + 1, "error": str(exc)})
                latency[f"phrase_{attempt + 1}"] = _ms(t0)
                break
            latency[f"phrase_{attempt + 1}"] = _ms(t0)
            t0 = time.perf_counter()
            permitted_prev = previously + res.repeat_fact_ids
            problems = verifier.deterministic_checks(case, text, cit, res.allowed_fact_ids, permitted_prev, utterance)
            if not problems:
                try:
                    judge_problems, j_call = verifier.judge(case, text, res.allowed_fact_ids, permitted_prev)
                    calls.append(j_call.to_dict())
                    problems = judge_problems
                except LLMUnavailable as exc:
                    problems = [f"judge unavailable: {exc}"]  # fail closed
            latency[f"verify_{attempt + 1}"] = _ms(t0)
            attempts.append({"attempt": attempt + 1, "reply": text, "cited": cit, "problems": problems})
            if not problems:
                reply, cited = text, cit
                break
            retry_reason = "; ".join(problems)
    if not reply:
        reply, cited = phraser.template_reply(case, res, intent.topic_ids(), intent.action_ids(), bool(intent.empathy))
        fallback = True

    blocked = sum(1 for a in attempts if a.get("problems"))
    verdict = {
        "passed": True,
        "mode": "template" if fallback else "llm",
        "attempts": attempts,
        "blocked_attempts": blocked,
    }
    latency["total"] = _ms(t_all)
    return TurnOutcome(
        intent=intent,
        engine=res,
        state=new_state,
        reply_text=reply,
        cited_fact_ids=cited,
        verifier=verdict,
        audio_tags=res.audio_tags,
        latency_ms=latency,
        llm_calls=calls,
        fallback_used=fallback,
    )
