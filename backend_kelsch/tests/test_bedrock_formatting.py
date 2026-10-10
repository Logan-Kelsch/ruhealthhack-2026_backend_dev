"""Formatting retries preserve fail-closed behavior and every paid attempt."""
import json

import pytest

from app.encounter import engine, phraser, pipeline, verifier
from app.integrations import bedrock
from app.schemas.encounter import Intent
from app.settings import get_settings
from backend_kelsch.app.grounding.evaluation import _case, challenges, check_challenges
from backend_kelsch.app.grounding.live import price_calls


@pytest.fixture
def fake_bedrock(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "true")
    get_settings.cache_clear()

    class Client:
        responses = []
        requests = []

        def converse(self, **kwargs):
            self.requests.append(kwargs)
            value = self.responses.pop(0)
            if isinstance(value, Exception):
                raise value
            return {"output": {"message": {"content": [{"text": value}]}},
                    "stopReason": "end_turn",
                    "usage": {"inputTokens": 20, "outputTokens": 7, "totalTokens": 27}}

    client = Client()
    monkeypatch.setattr(bedrock, "_client", lambda: client)
    yield client
    get_settings.cache_clear()
    bedrock.last_failed_call("verify")
    bedrock.last_failed_call("phrase")


@pytest.mark.parametrize("invalid", [
    '[]', '```json\n[]\n```',
    '{"unsupported": []}\n\nExplanation: supported.',
    '{"unsupported": "none"}',
    '{"unsupported": [{"sentence": "Something"}]}',
])
def test_verifier_retries_format_only_and_keeps_usage(fake_bedrock, invalid):
    fake_bedrock.responses = [invalid, '{"unsupported": []}']
    case, _ = _case("walter_greene")
    problems, call = verifier.judge(case, "Hi.", [], [])
    assert problems == []
    records = call.to_dicts()
    assert len(records) == 2 and [r["ok"] for r in records] == [False, True]
    assert sum(r["input_tokens"] for r in records) == 40
    assert "ONE JSON OBJECT" in fake_bedrock.requests[1]["system"][0]["text"]
    assert fake_bedrock.requests[0]["messages"] == fake_bedrock.requests[1]["messages"]
    assert bedrock.last_failed_call("verify") is None


@pytest.mark.parametrize("invalid", [
    '{"reply_text": "Hi."}, [""]',
    '{"reply_text": "Hi."}, {"cited_fact_ids": []}',
    '{"reply_text": "Hi."}',
    '{"reply_text": "Hi.", "cited_fact_ids": "f_example"}',
    '{"reply_text": "Hi.", "cited_fact_ids": [null]}',
    '{"reply_text": " ", "cited_fact_ids": []}',
])
def test_phraser_does_not_repair_or_accept_malformed_fields(fake_bedrock, invalid):
    fake_bedrock.responses = [invalid, '{"reply_text": "Hi.", "cited_fact_ids": []}']
    case, _ = _case("walter_greene")
    res, _ = engine.process_turn(case, engine.new_state(case), Intent(), "Hi.")
    reply, cited, calls = phraser.phrase(case, res, "Hi.", [], [])
    assert reply == "Hi." and cited == []
    assert len(calls[0].to_dicts()) == 2


def test_supported_and_unsupported_verdicts_are_not_retried(fake_bedrock):
    case, _ = _case("walter_greene")
    fake_bedrock.responses = [json.dumps({"unsupported": [{
        "sentence": "I have cancer.", "new_claim": "cancer diagnosis",
        "reason": "No approved fact gives that diagnosis",
    }]})]
    problems, call = verifier.judge(case, "I have cancer.", [], [])
    assert problems and len(fake_bedrock.requests) == 1
    assert call.ok and len(call.to_dicts()) == 1


def test_access_failure_is_not_a_format_retry(fake_bedrock):
    fake_bedrock.responses = [RuntimeError("AccessDeniedException: model access denied")]
    case, _ = _case("walter_greene")
    with pytest.raises(bedrock.LLMUnavailable) as caught:
        verifier.judge(case, "Hi.", [], [])
    assert len(fake_bedrock.requests) == 1
    assert len(caught.value.call.to_dicts()) == 1


def test_exhausted_phrase_retry_falls_back_and_counts_both_calls(fake_bedrock, monkeypatch):
    fake_bedrock.responses = ["not JSON", "still not JSON"]
    monkeypatch.setattr(pipeline.classifier, "classify", lambda *args: (Intent(), []))
    case, _ = _case("walter_greene")
    result = pipeline.run_turn(case, engine.new_state(case), "Hi.", [])
    assert result.fallback_used and result.reply_text
    assert len(result.llm_calls) == 2
    assert all(not call["ok"] for call in result.llm_calls)


def test_pipeline_counts_phrase_and_verifier_retries(fake_bedrock, monkeypatch):
    case, _ = _case("walter_greene")
    intent = Intent(topics=[{"id": "chief_complaint", "span": "What brings you in today?", "confidence": "high"}])
    monkeypatch.setattr(pipeline.classifier, "classify", lambda *args: (intent, []))
    phrase = json.dumps({"reply_text": case.fact("f_complains_pills").say,
                         "cited_fact_ids": ["f_complains_pills"]})
    fake_bedrock.responses = ["not JSON", phrase, '[]', '{"unsupported": []}']
    result = pipeline.run_turn(case, engine.new_state(case), "What brings you in today?", [])
    assert not result.fallback_used
    assert [c["purpose"] for c in result.llm_calls] == ["phrase", "phrase", "verify", "verify"]
    assert [c["ok"] for c in result.llm_calls] == [False, True, False, True]


def test_challenge_retry_is_in_usage_totals(fake_bedrock):
    fake_bedrock.responses = ['[]', '{"unsupported": []}']
    row = next(r for r in challenges() if r["kind"] == "approved_exact")
    check_challenges([row], use_llm=True)
    calls = row["llm_judge"]["calls"]
    assert len(calls) == 2
    totals = price_calls(calls, None, "us-east-1")
    assert totals["model_calls"] == 2
    assert totals["by_purpose"]["verify"]["input_tokens"] == 40


def test_exhausted_verifier_retry_never_approves(fake_bedrock):
    fake_bedrock.responses = ['[]', '[]']
    case, _ = _case("walter_greene")
    with pytest.raises(bedrock.LLMUnavailable) as caught:
        verifier.judge(case, "Hi.", [], [])
    assert len(caught.value.call.to_dicts()) == 2
    assert all(not c["ok"] for c in caught.value.call.to_dicts())
