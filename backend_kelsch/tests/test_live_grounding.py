"""Versioned pipeline probes keep model attempts separate from clinical truth."""
import json

import pytest

from app.encounter import engine, pipeline, verifier
from app.integrations import bedrock
from app.schemas.encounter import Intent
from app.settings import get_settings
from backend_kelsch.app.grounding.evaluation import _case
from backend_kelsch.app.grounding.live import (
    CASE_IDS, evaluate, extra_challenges, price_calls, pricing_snapshot,
)


def test_offline_evaluation_uses_pipeline_and_never_calls_semantics_grounded():
    report, trace = evaluate()
    assert report["version"] == trace["version"] == "live_grounding_v1"
    assert report["scripts"] == 9 and report["turns"] == 63
    assert report["delivered"]["fallback_replies"] == 63
    assert report["delivered"]["delivery_violations"] == []
    assert report["usage_and_cost"]["model_calls"] == 0
    assert report["gates"]["clinical_grounding"] == "NOT EVALUABLE"
    assert report["challenges"]["total"] == 27
    assert report["challenges"]["counts"]["mechanical_blocks"] == 9
    assert len(report["challenges"]["unchecked_semantic_ids"]) == 18
    assert all(t["intent_origin"] == "pipeline_prediction" and
               t["semantic_status"] == "template_source_linked_unreviewed"
               for run in trace["runs"] for t in run["turns"])


def test_echoed_number_and_wrong_units_remain_semantically_unchecked():
    rows = extra_challenges()
    assert len(rows) == 12 and {r["case_id"] for r in rows} == set(CASE_IDS)
    for kind in ("negated_history", "echoed_invented_value", "wrong_unit", "unsupported_conclusion"):
        assert sum(r["kind"] == kind for r in rows) == 3
    report, trace = evaluate()
    for row in trace["challenges"]:
        if row["kind"] in {"echoed_invented_value", "wrong_unit"}:
            assert row["deterministic_problems"] == []
            assert row["semantic_status"] == "unchecked_semantic"
            assert row["faculty_expected_supported"] is None
    assert report["gates"]["semantic_accuracy"] == "NOT EVALUABLE"


def test_bedrock_converse_usage_survives_success_and_invalid_json(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "true")
    get_settings.cache_clear()
    class FakeClient:
        reply = '{"unsupported": []}'
        def converse(self, **kwargs):
            return {"output": {"message": {"content": [{"text": self.reply}]}},
                    "usage": {"inputTokens": 20, "outputTokens": 7, "totalTokens": 27}}
    fake = FakeClient()
    monkeypatch.setattr(bedrock, "_client", lambda: fake)
    try:
        data, call = bedrock.complete_json(purpose="verify", prompt_name="verifier", user="toy")
        assert data == {"unsupported": []}
        assert (call.input_tokens, call.output_tokens, call.total_tokens) == (20, 7, 27)
        assert call.model == get_settings().bedrock_model_fast and call.prompt_version
        fake.reply = "not json"
        with pytest.raises(bedrock.LLMUnavailable) as exc:
            bedrock.complete_json(purpose="verify", prompt_name="verifier", user="toy")
        assert exc.value.call.input_tokens == 20 and exc.value.call.output_tokens == 7
        assert not exc.value.call.ok
    finally:
        get_settings.cache_clear()
        bedrock.last_failed_call("verify")


def test_failed_phrase_call_is_counted_and_fallback_delivered(monkeypatch):
    case, _ = _case("walter_greene")
    monkeypatch.setattr(pipeline.classifier, "classify", lambda *args: (Intent(), []))
    monkeypatch.setattr(pipeline, "llm_available", lambda: True)
    failed = bedrock.LLMCall("phrase", "toy-model", "phraser", "1", 3, False,
                             "simulated failure", input_tokens=8, output_tokens=2)
    def bad_phrase(*args):
        raise bedrock.LLMUnavailable("simulated failure", call=failed)
    monkeypatch.setattr(pipeline.phraser, "phrase", bad_phrase)
    result = pipeline.run_turn(case, engine.new_state(case), "What brings you in today?", [])
    assert result.fallback_used and result.verifier["mode"] == "template"
    assert len(result.llm_calls) == 1 and result.llm_calls[0]["input_tokens"] == 8
    assert result.verifier["attempts"][0]["error"] == "simulated failure"
    assert result.reply_text


def test_unreadable_or_incomplete_judge_verdict_cannot_approve_reply(monkeypatch):
    case, _ = _case("walter_greene")
    call = bedrock.LLMCall("verify", "toy-model", "verifier", "5", 1, True,
                           input_tokens=20, output_tokens=3)
    for output in ({}, {"unsupported": [{"sentence": "I have cancer."}]},
                   {"unsupported": "none"}):
        monkeypatch.setattr(verifier, "complete_json", lambda **kwargs: (output, call))
        problems, used = verifier.judge(case, "I have cancer.", [], [])
        assert problems and used is call
    monkeypatch.setattr(pipeline.classifier, "classify", lambda *args: (Intent(), []))
    monkeypatch.setattr(pipeline, "llm_available", lambda: True)
    phrase_call = bedrock.LLMCall("phrase", "toy-model", "phraser", "1", 1, True,
                                  input_tokens=12, output_tokens=4)
    monkeypatch.setattr(pipeline.phraser, "phrase", lambda *args: ("I have cancer.", [], [phrase_call]))
    monkeypatch.setattr(verifier, "complete_json", lambda **kwargs: ({}, call))
    result = pipeline.run_turn(case, engine.new_state(case), "What brings you in today?", [])
    assert result.fallback_used and result.reply_text != "I have cancer."
    assert result.verifier["blocked_attempts"] == 2
    assert len(result.llm_calls) == 4


def test_sourced_cost_requires_exact_model_region_complete_usage_and_no_cache(tmp_path):
    rates = {"currency": "USD", "region": "us-east-1", "effective_date": "2026-10-10",
             "source_url": "https://aws.amazon.com/bedrock/pricing/",
             "models": {"toy-model": {"input_usd_per_million": 2, "output_usd_per_million": 10}}}
    path = tmp_path / "prices.json"
    path.write_text(json.dumps(rates))
    snapshot = pricing_snapshot(path)
    call = {"purpose": "phrase", "model": "toy-model", "latency_ms": 17,
            "input_tokens": 200, "output_tokens": 40}
    result = price_calls([call], snapshot, "us-east-1")
    assert result["estimated_total_usd"] == 0.0008
    assert result["by_purpose"]["phrase"]["calls"] == 1
    assert price_calls([{**call, "cache_read_input_tokens": 1}], snapshot, "us-east-1")["estimated_total_usd"] is None
    assert price_calls([call.copy()], snapshot, "us-west-2")["unpriced_calls"] == 1
    assert price_calls([{**call, "output_tokens": None}], snapshot, "us-east-1")["estimated_total_usd"] is None
    rates["models"]["toy-model"]["input_usd_per_million"] = -1
    path.write_text(json.dumps(rates))
    with pytest.raises(ValueError, match="nonnegative"):
        pricing_snapshot(path)
