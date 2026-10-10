"""Turn timing samples (E-04, P-01, V-05).

The pipeline already records how long classify, disclosure, phrasing, and verification
took. This module adds the client clock: reply arrival, the speech request, the first
audio bytes, and the moment playback actually starts. Those are different events.
"""

from __future__ import annotations

import math
from typing import Literal

from app.schemas.latency import TurnTimingCapture, TurnTimingSample

# Client marks, in the order a turn reaches them. The report lists gaps in this order.
CLIENT_MARKS = (
    "verified_reply_arrival_ms",
    "speech_request_ms",
    "first_audio_bytes_ms",
    "first_playback_ms",
)

FallbackKind = Literal["template", "browser_voice"]


def public_pipeline(latency_ms: dict) -> dict[str, int]:
    """Copy the stored step durations under the names the reply already uses.

    The row calls the disclosure pass "engine". The student reply calls it "disclosure".
    A step that did not run is left out rather than stored as zero.
    """
    steps: dict[str, int] = {}
    for key, value in latency_ms.items():
        # Booleans are ints in Python. A flag is not a duration.
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        name = "disclosure" if key == "engine" else str(key)
        steps[name] = value
    return steps


def retry_count(verifier: dict) -> int:
    """How many phrasing attempts the verifier blocked. No attempt log means no counted retry."""
    blocked = verifier.get("blocked_attempts")
    if isinstance(blocked, int) and not isinstance(blocked, bool) and blocked >= 0:
        return blocked
    attempts = verifier.get("attempts")
    if isinstance(attempts, list):
        return sum(1 for item in attempts if isinstance(item, dict) and item.get("problems"))
    return 0


def _mark(value: int | None) -> int | None:
    """Keep a non-negative offset. A missing or negative mark is not a duration."""
    if value is None or value < 0:
        return None
    return value


def _clear_incomparable(marks: dict[str, int | None]) -> dict[str, int | None]:
    """Drop marks that cannot sit on one clock. They stay missing instead of being repaired."""
    cleaned = dict(marks)
    speech = cleaned["speech_request_ms"]
    audio = cleaned["first_audio_bytes_ms"]
    # Bytes cannot arrive before the speech request that asked for them.
    if speech is not None and audio is not None and audio < speech:
        cleaned["speech_request_ms"] = None
        cleaned["first_audio_bytes_ms"] = None
    audio = cleaned["first_audio_bytes_ms"]
    playback = cleaned["first_playback_ms"]
    # Playback cannot start before the first byte when both were observed.
    if audio is not None and playback is not None and playback < audio:
        cleaned["first_audio_bytes_ms"] = None
        cleaned["first_playback_ms"] = None
    reply = cleaned["verified_reply_arrival_ms"]
    playback = cleaned["first_playback_ms"]
    # Playback that precedes the verified reply is not the same turn's clock.
    if reply is not None and playback is not None and playback < reply:
        cleaned["verified_reply_arrival_ms"] = None
        cleaned["first_playback_ms"] = None
    return cleaned


def assemble_sample(
    *,
    encounter_id: str,
    turn_id: int,
    capture: TurnTimingCapture,
    latency_ms: dict,
    verifier: dict,
) -> TurnTimingSample:
    """Build the sample that will be stored. First audio bytes are never copied into playback."""
    marks = _clear_incomparable({name: _mark(getattr(capture, name)) for name in CLIENT_MARKS})
    # Playback stays whatever was observed. It is not filled from the first byte.
    kinds: list[FallbackKind] = []
    if verifier.get("mode") == "template":
        kinds.append("template")
    if capture.speech_path == "browser":
        kinds.append("browser_voice")
    unavailable = [name for name in CLIENT_MARKS if marks[name] is None]
    return TurnTimingSample(
        encounter_id=encounter_id,
        turn_id=turn_id,
        verified_reply_arrival_ms=marks["verified_reply_arrival_ms"],
        speech_request_ms=marks["speech_request_ms"],
        first_audio_bytes_ms=marks["first_audio_bytes_ms"],
        first_playback_ms=marks["first_playback_ms"],
        pipeline_ms=public_pipeline(latency_ms),
        retries=retry_count(verifier),
        fallback=bool(kinds),
        fallback_kinds=kinds,
        error=capture.error,
        speech_path=capture.speech_path,
        unavailable=unavailable,
        origin=capture.origin,
    )


def normalize_sample(sample: dict) -> dict:
    """Apply the same missing-mark rules to a sample the report is about to summarize.

    A fixture file can contain an impossible order. The summary does not invent a
    replacement duration, and it does not treat the first byte as playback.
    """
    marks = _clear_incomparable({name: _mark(_as_int(sample.get(name))) for name in CLIENT_MARKS})
    updated = dict(sample)
    updated.update(marks)
    # Unavailable is recomputed from what survived. A cleared mark is missing, not repaired.
    updated["unavailable"] = [name for name in CLIENT_MARKS if marks[name] is None]
    return updated


def _as_int(value: object) -> int | None:
    """Accept a stored millisecond count. Anything else is a missing mark."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


# Steps the pipeline records. A step that did not run is reported as missing, not zero.
PIPELINE_STEPS = ("classify", "disclosure", "phrase_1", "phrase_2", "verify_1", "verify_2", "total")

# The PRD states this as a goal. A report may repeat the number. It may not say the goal was met.
COMMIT_TO_FIRST_AUDIO_GOAL_MS = 2000


def _duration_summary(values: list[int]) -> dict[str, int] | None:
    """Median and 90th percentile for one mark. No values means the summary stays missing."""
    if not values:
        return None
    ordered = sorted(values)
    count = len(ordered)
    if count % 2 == 1:
        median = ordered[count // 2]
    else:
        # Average of the two middle values. These durations average to a whole number of milliseconds.
        pair = ordered[count // 2 - 1] + ordered[count // 2]
        median = pair // 2
    # Nearest-rank 90th percentile: the smallest value at or above 90 percent of the list.
    index = math.ceil(0.9 * count) - 1
    return {"count": count, "median": median, "p90": ordered[index]}


def _pipeline_summary(samples: list[dict]) -> dict[str, dict[str, int] | None]:
    """Per-step durations for one origin. Live and fixture clocks are not mixed here."""
    summary: dict[str, dict[str, int] | None] = {}
    for step in PIPELINE_STEPS:
        values: list[int] = []
        for sample in samples:
            pipeline = sample.get("pipeline_ms") or {}
            # Older rows named the disclosure pass "engine". The report uses the public name.
            raw = pipeline.get("disclosure", pipeline.get("engine")) if step == "disclosure" else pipeline.get(step)
            parsed = _as_int(raw)
            if parsed is not None and parsed >= 0:
                values.append(parsed)
        summary[step] = _duration_summary(values)
    return summary


def _origin_block(samples: list[dict]) -> dict:
    """Counts and percentiles for one clock. A mark with no comparable values is null."""
    block: dict = {"samples": len(samples)}
    unavailable = {name: 0 for name in CLIENT_MARKS}
    for name in CLIENT_MARKS:
        values: list[int] = []
        for sample in samples:
            parsed = _as_int(sample.get(name))
            if parsed is None:
                unavailable[name] += 1
                continue
            values.append(parsed)
        block[name] = _duration_summary(values)
    block["unavailable"] = unavailable
    block["pipeline_ms"] = _pipeline_summary(samples)
    return block


def _limitations(live_samples: list[dict]) -> list[str]:
    """Say what this file is not. The wording is the claim boundary for the video and the PR."""
    lines = [
        "Samples marked fixture use a controlled clock. They are not live vendor performance.",
        "The median commit-to-first-audio target is a measured goal. This report does not claim it is met.",
        "No HTTP-versus-WebSocket delay was measured.",
    ]
    live_playback = [sample for sample in live_samples if _as_int(sample.get("first_playback_ms")) is not None]
    if not live_samples:
        lines.append("No live timing sample is in this report.")
    elif not live_playback:
        lines.append(
            "The live sample has no commit-to-first-playback measurement, so live vendor performance is not shown."
        )
    return lines


def summarize(samples: list[dict]) -> dict:
    """Build the validation report. It never fills a gap from a different mark or a different clock."""
    normalized = [normalize_sample(sample) for sample in samples]
    grouped: dict[str, list[dict]] = {"fixture": [], "live": []}
    for sample in normalized:
        origin = sample.get("origin")
        if origin in grouped:
            grouped[origin].append(sample)
    retries = []
    fallbacks = []
    errors = []
    for sample in normalized:
        retry = _as_int(sample.get("retries"))
        if retry is not None and retry > 0:
            retries.append({"encounter_id": sample.get("encounter_id"), "turn_id": sample.get("turn_id"), "retries": retry})
        if sample.get("fallback") is True:
            fallbacks.append(
                {
                    "encounter_id": sample.get("encounter_id"),
                    "turn_id": sample.get("turn_id"),
                    "fallback_kinds": list(sample.get("fallback_kinds") or []),
                }
            )
        error = sample.get("error")
        if isinstance(error, str) and error:
            errors.append({"encounter_id": sample.get("encounter_id"), "turn_id": sample.get("turn_id"), "error": error})
    by_origin = {origin: _origin_block(rows) for origin, rows in grouped.items() if rows}
    live_playback = [sample for sample in grouped["live"] if _as_int(sample.get("first_playback_ms")) is not None]
    return {
        "counts": {"samples": len(normalized), "live": len(grouped["live"]), "fixture": len(grouped["fixture"])},
        "retries": retries,
        "fallbacks": fallbacks,
        "errors": errors,
        # Repeated so a reader sees the goal. This is not set from the median.
        "commit_to_first_audio_goal_ms": COMMIT_TO_FIRST_AUDIO_GOAL_MS,
        "target_claimed_met": False,
        # Left null on purpose. These samples do not measure an HTTP-versus-WebSocket delay.
        "http_versus_websocket_ms": None,
        "live_vendor_performance": bool(live_playback),
        "limitations": _limitations(grouped["live"]),
        "by_origin": by_origin,
        "samples": normalized,
    }
