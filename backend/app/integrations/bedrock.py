"""AWS Bedrock (Claude) client. One function: ask for JSON, get JSON back.

Every call returns an LLMCall record (model id, prompt version, latency, ok) so the
encounter log can record exactly which model and prompt produced each output.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.settings import get_settings

log = logging.getLogger(__name__)
PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


class LLMUnavailable(Exception):
    pass


@dataclass
class LLMCall:
    purpose: str
    model: str
    prompt: str
    prompt_version: str
    latency_ms: int
    ok: bool
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def load_prompt(name: str) -> tuple[str, str]:
    """Return (text, version). Prompt files start with a `version: N` line."""
    text = (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")
    first, _, rest = text.partition("\n")
    version = first.split(":", 1)[1].strip() if first.startswith("version:") else "0"
    return rest.strip(), version


@lru_cache
def _client():
    import boto3
    from botocore.config import Config

    s = get_settings()
    session = boto3.Session(profile_name=s.aws_profile, region_name=s.aws_region) if s.aws_profile else boto3.Session(region_name=s.aws_region)
    return session.client("bedrock-runtime", config=Config(read_timeout=s.llm_timeout_s, connect_timeout=5, retries={"max_attempts": 1}))


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


def complete_json(
    *,
    purpose: str,
    prompt_name: str,
    user: str,
    strong: bool = False,
    max_tokens: int = 1200,
    temperature: float = 0.0,
    system_extra: str = "",
) -> tuple[Any, LLMCall]:
    """Call Claude on Bedrock and parse a JSON reply. Raises LLMUnavailable on any failure."""
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
        text = "".join(block.get("text", "") for block in resp["output"]["message"]["content"])
        data = _extract_json(text)
        call.ok = True
        return data, call
    except Exception as exc:  # network, auth, throttling, bad JSON: all mean "use the fallback"
        call.error = f"{type(exc).__name__}: {str(exc)[:200]}"
        log.warning("bedrock %s failed: %s", purpose, call.error)
        raise LLMUnavailable(call.error) from exc
    finally:
        call.latency_ms = int((time.perf_counter() - t0) * 1000)
        if not call.ok:
            _last_failed_call[purpose] = call


# Keeps the most recent failed call per purpose so callers can log it after catching.
_last_failed_call: dict[str, LLMCall] = {}


def last_failed_call(purpose: str) -> LLMCall | None:
    return _last_failed_call.pop(purpose, None)
