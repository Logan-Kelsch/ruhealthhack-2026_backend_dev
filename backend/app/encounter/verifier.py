"""Verifier (PRD 9.1 step 5). Fails closed: a reply that cannot be checked is not sent.

Deterministic checks: cited ids are allowed, every number is backed by a cited fact,
no clinical jargon the patient would not use. Then an LLM judge checks that each
sentence is supported by the facts.
"""
from __future__ import annotations

import json
import re

from app import catalogs
from app.encounter.phraser import fact_line
from app.integrations.bedrock import LLMCall, LLMUnavailable, complete_json, last_failed_call
from app.schemas.case import Case, Fact

WORD_NUMBERS = {
    "zero": 0, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "twice": 2,
}  # "one" is left out on purpose: "no one", "the one I take"
SCALES = {"hundred": 100, "thousand": 1000}
NUM_RE = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")
TOKEN_RE = re.compile(r"[a-z]+|[^\sa-z]")


def _word_numbers(text: str) -> set[float]:
    """Spoken numbers as values: "two thousand" is 2000, "twenty five" is 25, "two, three" is 2 and 3."""
    out: set[float] = set()
    total, cur = 0, None

    def flush():
        nonlocal total, cur
        if cur is not None:
            out.add(float(total + cur))
        total, cur = 0, None

    for tok in TOKEN_RE.findall(text.lower()):
        if tok in WORD_NUMBERS and tok != "twice":
            v = WORD_NUMBERS[tok]
            joins = cur is not None and (cur % 100 == 0 or (v < 10 and cur % 10 == 0 and cur % 100 >= 20))
            if not joins:
                flush()
                cur = 0
            cur += v
        elif tok in SCALES:
            if tok == "hundred":
                cur = (cur or 1) * 100
            else:
                total, cur = total + (cur or 1) * 1000, 0
        elif tok == "and" and cur is not None and total + cur >= 100:
            continue
        else:
            flush()
            if tok == "twice":
                out.add(2.0)
    flush()
    return out


def numbers_in(text: str) -> set[float]:
    return {float(n.replace(",", "")) for n in NUM_RE.findall(text)} | _word_numbers(text)


def _fact_texts(f: Fact) -> str:
    parts = [f.text, f.say or "", str(f.value or "")]
    if f.belief:
        parts += [f.belief.text, f.belief.say or ""]
    return " ".join(parts)


def deterministic_checks(
    case: Case, reply: str, cited: list[str], allowed: list[str], previously_disclosed: list[str], utterance: str
) -> list[str]:
    problems: list[str] = []
    permitted = set(allowed) | set(previously_disclosed)
    bad = [c for c in cited if c not in permitted]
    if bad:
        problems.append(f"cited facts not allowed this turn: {bad}")
    cited_facts = [case.fact(c) for c in cited if c in permitted]
    cited_facts = [f for f in cited_facts if f is not None]
    backing = " ".join(_fact_texts(f) for f in cited_facts) + f" {utterance} {case.profile.age}"
    allowed_numbers = numbers_in(backing)
    stray = sorted(n for n in numbers_in(reply) if n not in allowed_numbers)
    if stray:
        problems.append(f"numbers not backed by a cited fact: {[int(n) if n.is_integer() else n for n in stray]}")
    if case.profile.personality.health_literacy != "high":
        fact_vocab = " ".join(fact_line(f).lower() for f in case.facts)
        low = reply.lower()
        for entry in catalogs.lay_lexicon():
            term = entry["term"]
            if re.search(rf"\b{re.escape(term)}", low) and term not in fact_vocab:
                problems.append(f"clinical term '{term}' the patient would not use; say '{entry['lay']}'")
    if re.search(r"(^|\n)\s*[-*\d]+[.)]\s", reply) or "**" in reply:
        problems.append("reply uses list or markdown formatting")
    return problems


def judge(case: Case, reply: str, allowed: list[str], previously_disclosed: list[str], student_said: str = "") -> tuple[list[str], LLMCall]:
    facts = [case.fact(i) for i in list(dict.fromkeys(allowed + previously_disclosed))]
    facts_payload = [{"id": f.id, "say": fact_line(f), "chart_truth": f.text} for f in facts if f is not None]
    pers = case.profile.personality
    user = (
        f"APPROVED FACTS:\n{json.dumps(facts_payload, ensure_ascii=False)}\n\n"
        f"PATIENT BASICS (allowed): name {case.profile.name}, age {case.profile.age}. Personality (style only): {pers.summary}\n\n"
        f"WHAT THE STUDENT SAID (the patient may repeat or react to this):\n{json.dumps(student_said, ensure_ascii=False)}\n\n"
        f"REPLY TO CHECK:\n{json.dumps(reply)}"
    )
    try:
        data, call = complete_json(purpose="verify", prompt_name="verifier", user=user, max_tokens=500)
    except LLMUnavailable as exc:
        failed = last_failed_call("verify")
        raise LLMUnavailable(failed.error if failed else "verifier failed", call=failed or exc.call) from None
    if not isinstance(data, dict) or not isinstance(data.get("unsupported"), list):
        return ["unreadable judge output"], call
    problems = []
    for u in data.get("unsupported", []):
        if not isinstance(u, dict):
            problems.append(f"unsupported: {u}")
        elif isinstance(u.get("new_claim"), str) and u["new_claim"].strip():
            problems.append(f"unsupported: {u.get('sentence', '')} (new claim: {u['new_claim']})")
        else:
            problems.append("judge flagged unsupported content without a named claim")
    return problems, call
