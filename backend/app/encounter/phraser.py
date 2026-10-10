"""Phraser: turns the facts the engine allowed into the patient's words, in character.

The LLM only phrases. It receives the allowed facts and the personality, never the
hidden ones. The template fallback speaks each fact's approved `say` text verbatim.
"""
from __future__ import annotations

import json

from app.integrations.bedrock import LLMCall, LLMUnavailable, complete_json, last_failed_call
from app.schemas.case import Case, Fact
from app.schemas.encounter import EngineResult


def fact_line(f: Fact) -> str:
    """The lay sentence for a fact: the belief's spoken form when set, else `say`, else the text.
    belief.text is a chart note about the belief, so it is never spoken."""
    if f.belief is not None and f.belief.say:
        return f.belief.say
    return f.say or f.text


def _persona_block(case: Case, mood: str) -> str:
    p = case.profile
    pers = p.personality
    lines = [
        f"You are {p.name}, age {p.age}." + (f" Occupation: {p.occupation}." if p.occupation else ""),
    ]
    if p.speaker:
        lines.append(f"The person speaking is {p.speaker}, talking about the patient.")
    if pers.summary:
        lines.append(f"Personality: {pers.summary}")
    if pers.communication_style:
        lines.append(f"Communication style: {pers.communication_style}")
    if pers.traits:
        lines.append("Traits (0 to 1): " + ", ".join(f"{k} {v}" for k, v in pers.traits.items()))
    lines.append(f"Health literacy: {pers.health_literacy}.")
    lines.append(f"Current mood toward the student: {mood}.")
    if pers.example_lines:
        lines.append("Example lines in your voice (style only, not facts): " + " | ".join(pers.example_lines[:6]))
    lines.append(f"Setting: {case.briefing.setting}. You are talking to a {case.briefing.student_role or 'student'}.")
    return "\n".join(lines)


ACK_BY_ACTION = [
    ("closing", "Okay. Thanks."),
    ("ask_permission", "Sure."),
    ("check_understanding", "I think so."),
    ("summarize", "Yeah, that's about right."),
    ("give_information", "Okay."),
    ("plan_next_steps", "Okay."),
    ("safety_netting", "Okay."),
]


def template_reply(
    case: Case, res: EngineResult, topic_ids: set[str], action_ids: set[str] | frozenset = frozenset(), empathy: bool = False
) -> tuple[str, list[str]]:
    """Deterministic reply built only from approved fact text. Used when the LLM is down or fails checks."""
    facts = [case.fact(i) for i in res.allowed_fact_ids]
    facts = [f for f in facts if f is not None]
    parts: list[str] = []
    cited: list[str] = []
    if res.is_repeat:
        parts.append("I already told you that.")
        rep = case.fact(res.repeat_fact_ids[0]) if res.repeat_fact_ids else None
        if rep is not None:
            parts.append(fact_line(rep))
            cited.append(rep.id)
    for f in facts:
        parts.append(fact_line(f))
        cited.append(f.id)
    if not parts:
        if res.deflect:
            parts.append("I'd rather not get into that right now.")
        elif res.exam_only:
            parts.append("Okay, go ahead.")
        elif "greeting_introduction" in topic_ids:
            parts.append("Hi.")
        elif empathy:
            parts.append("Yeah. Thanks for saying that.")
        elif ack := next((line for a, line in ACK_BY_ACTION if a in action_ids), None):
            parts.append(ack)
        elif "purpose_agenda" in topic_ids or (case.actions and action_ids & {a.id for a in case.actions}):
            parts.append("Okay.")
        elif res.repeat_fact_ids:
            rep = case.fact(res.repeat_fact_ids[0])
            if rep is not None:
                parts.append(fact_line(rep))
                cited.append(rep.id)
        else:
            parts.append("I'm not sure. I don't really know about that.")
    return " ".join(parts), cited


def phrase(
    case: Case,
    res: EngineResult,
    utterance: str,
    history: list[tuple[str, str]],
    previously_disclosed: list[str],
    retry_reason: str | None = None,
) -> tuple[str, list[str], list[LLMCall]]:
    """Return (reply_text, cited_fact_ids, calls). Raises LLMUnavailable on failure."""
    allowed = [case.fact(i) for i in res.allowed_fact_ids]
    allowed = [f for f in allowed if f is not None]
    earlier = [case.fact(i) for i in previously_disclosed if i not in res.allowed_fact_ids]
    earlier = [f for f in earlier if f is not None]

    def facts_json(fs: list[Fact]) -> str:
        return json.dumps([{"id": f.id, "say": fact_line(f), "chart_truth": f.text} for f in fs], ensure_ascii=False)

    situation = []
    if res.is_repeat:
        situation.append("The student asked something you already answered. Show mild annoyance in character ('I already told you...') and repeat the answer briefly.")
    if res.deflect:
        situation.append("The student asked about something you are not ready to talk about. Deflect or change the subject in character. Do not reveal anything.")
    if res.exam_only:
        situation.append("The student is examining you. Reply with a short acknowledgement or reaction only. Never describe exam findings.")
    if not allowed and not res.is_repeat and not res.deflect and not res.exam_only:
        situation.append("No new facts are available. Answer in character without stating any new medical or personal facts; say you're not sure if asked for something not listed.")

    convo = "\n".join(f"Student: {s}\nYou: {p}" for s, p in history[-6:])
    user = (
        f"PERSONA\n{_persona_block(case, res.mood)}\n\n"
        f"NEW FACTS YOU MAY SAY NOW (cite their ids):\n{facts_json(allowed)}\n\n"
        f"FACTS YOU ALREADY SAID (may refer back, cite ids if you restate):\n{facts_json(earlier)}\n\n"
        f"SITUATION: {' '.join(situation) or 'Answer the student using the new facts.'}\n\n"
        f"RECENT CONVERSATION:\n{convo or '(start of visit)'}\n\n"
        f"STUDENT JUST SAID: {json.dumps(utterance)}"
    )
    if retry_reason:
        user += f"\n\nYOUR PREVIOUS REPLY WAS REJECTED: {retry_reason}. Fix it."
    try:
        data, call = complete_json(purpose="phrase", prompt_name="phraser", user=user, max_tokens=400, temperature=0.6)
    except LLMUnavailable:
        failed = last_failed_call("phrase")
        raise LLMUnavailable(failed.error if failed else "phraser failed") from None
    if not isinstance(data, dict) or not isinstance(data.get("reply_text"), str):
        raise LLMUnavailable("phraser returned an unexpected shape")
    cited = [str(c) for c in data.get("cited_fact_ids") or []]
    return data["reply_text"].strip(), cited, [call]
