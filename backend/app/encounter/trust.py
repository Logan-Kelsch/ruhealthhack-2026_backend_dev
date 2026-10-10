"""Trust ledger rules (PRD 9.3). Pure functions: same inputs, same events.

Every event quotes a span from the transcript. An event without a span is not created.
Asking about suicidal thoughts is never penalized (PRD F-10).
"""
from __future__ import annotations

from app import catalogs
from app.schemas.encounter import Intent, TrustEvent

# Caps stop a student from farming trust by repeating the same move.
POSITIVE_CAPS = {"empathic_response": 4, "asked_permission": 2}
CUE_WINDOW_TURNS = 2
INTERRUPT_THRESHOLD_MS = 300
NEVER_PENALIZED_TOPICS = {"suicidal_ideation"}


def _delta(event_id: str) -> int:
    return int(catalogs.trust_events()[event_id]["delta"])


def _count(state: dict, event_id: str) -> int:
    return sum(1 for e in state.get("trust_log", []) if e["event"] == event_id)


def first_words(text: str, n: int = 8) -> str:
    return " ".join(text.split()[:n])


def trust_events_for_turn(
    *,
    intent: Intent,
    utterance: str,
    turn: int,
    state: dict,
    sensitive_topics: set[str],
    barge_in_remaining_ms: int | None = None,
) -> tuple[list[TrustEvent], list[str]]:
    """Return (events, cue fact ids resolved this turn)."""
    events: list[TrustEvent] = []

    def add(event_id: str, span: str, note: str | None = None):
        if not span or not span.strip():
            return
        cap = POSITIVE_CAPS.get(event_id)
        if cap is not None and _count(state, event_id) + sum(1 for e in events if e.event == event_id) >= cap:
            return
        events.append(TrustEvent(event=event_id, delta=_delta(event_id), span=span, turn=turn, note=note))

    topics = {h.id: h for h in intent.topics}
    actions = {h.id: h for h in intent.actions}

    if not state.get("introduced") and turn <= 3 and "greeting_introduction" in topics:
        span = topics["greeting_introduction"].span
        low = utterance.lower()
        if any(k in low for k in ("my name", "i'm ", "i am ")):
            add("introduced_self", span)

    if intent.empathy:
        add("empathic_response", intent.empathy[0].span)

    if "ask_permission" in actions:
        add("asked_permission", actions["ask_permission"].span)

    # Rapport cues the patient raised earlier: followed up, or ignored past the window.
    resolved: list[str] = []
    for cue in state.get("pending_cues", []):
        cue_topics = set(cue.get("topics", []))
        hit = next((topics[t] for t in cue_topics if t in topics), None)
        if hit is None and intent.empathy and turn == cue["turn"] + 1:
            hit = intent.empathy[0]
        if hit is not None:
            add("followed_personal_cue", hit.span, note=f"cue {cue['fact_id']}")
            resolved.append(cue["fact_id"])
        elif turn - cue["turn"] >= CUE_WINDOW_TURNS:
            add("ignored_cue", first_words(utterance), note=f"cue {cue['fact_id']} not acknowledged")
            resolved.append(cue["fact_id"])

    softened = bool(intent.empathy) or "ask_permission" in actions
    for t_id, hit in topics.items():
        if t_id in sensitive_topics and t_id not in NEVER_PENALIZED_TOPICS and not softened and state.get("trust", 0) < 1:
            add("blunt_sensitive_question", hit.span, note=t_id)
            break

    unexplained = [j for j in intent.jargon if not j.explained]
    if unexplained:
        add("unexplained_jargon", unexplained[0].span, note=unexplained[0].term)

    if "confront_or_lecture" in actions:
        add("lectured_or_judged", actions["confront_or_lecture"].span)

    if barge_in_remaining_ms is not None and barge_in_remaining_ms > INTERRUPT_THRESHOLD_MS:
        add("interrupted", first_words(utterance), note=f"patient audio had {barge_in_remaining_ms} ms left")

    return events, resolved


def sensitive_topic_ids() -> set[str]:
    return {t.id for t in catalogs.topics().values() if t.sensitive}
