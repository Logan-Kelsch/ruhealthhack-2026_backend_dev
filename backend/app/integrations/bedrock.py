"""AWS Bedrock (Claude) client. One function: ask for JSON, get JSON back.

Every call returns an LLMCall record (model id, prompt version, latency, ok) so the
encounter log can record exactly which model and prompt produced each output.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from app.settings import aws_session, get_settings

log = logging.getLogger(__name__)
PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


class LLMUnavailable(Exception):
    def __init__(self, message: str, *, call: LLMCall | None = None):
        super().__init__(message)
        self.call = call


@dataclass
class LLMCall:
    purpose: str
    model: str
    prompt: str
    prompt_version: str
    latency_ms: int
    ok: bool
    error: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cache_read_input_tokens: int | None = None
    cache_write_input_tokens: int | None = None
    previous_calls: list[LLMCall] = field(default_factory=list, repr=False)

    def to_dict(self) -> dict:
        record = asdict(self)
        record.pop("previous_calls")
        return record

    def to_dicts(self) -> list[dict]:
        """Keep each paid request separate, including a failed formatting attempt."""
        return [c.to_dict() for c in self.previous_calls] + [self.to_dict()]


def load_prompt(name: str) -> tuple[str, str]:
    """Return (text, version). Prompt files start with a `version: N` line."""
    text = (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")
    first, _, rest = text.partition("\n")
    version = first.split(":", 1)[1].strip() if first.startswith("version:") else "0"
    return rest.strip(), version


@lru_cache
def _client():
    from botocore.config import Config

    s = get_settings()
    return aws_session().client("bedrock-runtime", config=Config(read_timeout=s.llm_timeout_s, connect_timeout=5, retries={"max_attempts": 1}))


def llm_available() -> bool:
    return get_settings().llm_enabled


def _extract_json(text: str) -> Any:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
    if start > 0:
        text = text[start:]
    return json.loads(text)


def _complete_json_once(
    *,
    purpose: str,
    prompt_name: str,
    user: str,
    strong: bool = False,
    max_tokens: int = 1200,
    temperature: float = 0.0,
    system_extra: str = "",
) -> tuple[Any, LLMCall]:
    """Make one Converse request and strictly parse its JSON response."""
    s = get_settings()
    model = s.bedrock_model_strong if strong else s.bedrock_model_fast
    system, version = load_prompt(prompt_name)
    if system_extra:
        system = f"{system}\n\n{system_extra}"
    if not s.llm_enabled:
        raise LLMUnavailable("LLM disabled by config")
    t0 = time.perf_counter()
    call = LLMCall(purpose=purpose, model=model, prompt=prompt_name, prompt_version=version, latency_ms=0, ok=False)
    try:
        resp = _client().converse(
            modelId=model,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user}]}],
            inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
        )
        usage = resp.get("usage") or {}
        call.input_tokens = usage.get("inputTokens")
        call.output_tokens = usage.get("outputTokens")
        call.total_tokens = usage.get("totalTokens")
        call.cache_read_input_tokens = usage.get("cacheReadInputTokens")
        call.cache_write_input_tokens = usage.get("cacheWriteInputTokens")
        text = "".join(block.get("text", "") for block in resp["output"]["message"]["content"])
        data = _extract_json(text)
        call.ok = True
        return data, call
    except Exception as exc:  # network, auth, throttling, bad JSON: all mean "use the fallback"
        call.error = f"{type(exc).__name__}: {str(exc)[:200]}"
        log.warning("bedrock %s failed: %s", purpose, call.error)
        raise LLMUnavailable(call.error, call=call) from exc
    finally:
        call.latency_ms = int((time.perf_counter() - t0) * 1000)
        if not call.ok:
            _last_failed_call[purpose] = call


def complete_json(
    *,
    purpose: str,
    prompt_name: str,
    user: str,
    strong: bool = False,
    max_tokens: int = 1200,
    temperature: float = 0.0,
    system_extra: str = "",
    response_validator: Callable[[Any], bool] | None = None,
) -> tuple[Any, LLMCall]:
    """Retry encounter output formatting once; never retry an access/network error.

    No malformed output is repaired or treated as approval. Callers without a
    response validator retain the existing single-request behavior.
    """
    previous: list[LLMCall] = []
    for attempt in range(2 if response_validator is not None else 1):
        instruction = system_extra
        if attempt:
            instruction += (
                "\nYour previous response had invalid JSON formatting or fields. "
                "Return exactly ONE JSON OBJECT with every field required by the "
                "output contract. No bare arrays, code fences, explanation, or text "
                "before or after the object. Reevaluate the original input; do not "
                "change a factual verdict just to satisfy the format."
            )
        try:
            data, call = _complete_json_once(
                purpose=purpose, prompt_name=prompt_name, user=user, strong=strong,
                max_tokens=max_tokens, temperature=temperature, system_extra=instruction,
            )
        except LLMUnavailable as exc:
            call = exc.call
            if call is None:
                raise
            call.previous_calls = previous.copy()
            if attempt == 0 and response_validator is not None and (call.error or "").startswith("JSONDecodeError:"):
                previous.append(call)
                continue
            raise
        call.previous_calls = previous.copy()
        if response_validator is None or response_validator(data):
            _last_failed_call.pop(purpose, None)
            return data, call
        call.ok = False
        call.error = "ResponseShapeError: response does not match the required JSON fields"
        _last_failed_call[purpose] = call
        if attempt == 0:
            previous.append(call)
            continue
        raise LLMUnavailable(call.error, call=call)
    raise AssertionError("format retry exhausted without a result")


# Keeps the most recent failed call per purpose so callers can log it after catching.
_last_failed_call: dict[str, LLMCall] = {}


def last_failed_call(purpose: str) -> LLMCall | None:
    return _last_failed_call.pop(purpose, None)
