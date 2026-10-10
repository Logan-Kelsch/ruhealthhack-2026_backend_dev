"""Scores the official 7-domain rubric with evidence (PRD F-01, F-05, F-10).

LLM path: a stronger Claude model scores each domain and must quote the transcript.
Quotes are checked against the transcript; a scored domain without a valid quote is
retried once, then scored by the deterministic rules below (marked "rule-based").
"""
from __future__ import annotations

import json
import re

from app import catalogs
from app.integrations.bedrock import LLMCall, LLMUnavailable, complete_json, last_failed_call
from app.schemas.case import Case

EVIDENCE_FIELDS = ("strength_demonstrated", "important_gap_or_missed_opportunity", "safety_or_accuracy_concern")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip(" .,!?;:\"'")


def quote_valid(quote: str, turn: int, turns: list[dict]) -> bool:
    t = next((x for x in turns if x["idx"] == turn), None)
    if t is None or not _norm(quote):
        return False
    return _norm(quote) in _norm(t["student_text"]) or _norm(quote) in _norm(t["reply_text"])


# ---------- deterministic rules (fallback, and the baseline the LLM is compared to) ----------

def _first_span(turns: list[dict], key: str, ids: set[str], within: int | None = None) -> tuple[int, str] | None:
    for t in turns:
        if within is not None and t["idx"] > within:
            break
        for h in t["intent"].get(key, []):
            if h["id"] in ids:
                return t["idx"], h["span"]
    return None


def _events(turns: list[dict], event_ids: set[str]) -> list[tuple[int, str]]:
    return [(t["idx"], e["span"]) for t in turns for e in t["engine"].get("trust_events", []) if e["event"] in event_ids]


def rule_based_scores(case: Case, turns: list[dict], signals: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}

    def put(key, score, evidence, strength="", gap="", concern=""):
        out[key] = {
            "score": score,
            "evidence": [{"turn": i, "quote": q} for i, q in evidence if q][:3],
            "strength_demonstrated": strength,
            "important_gap_or_missed_opportunity": gap,
            "safety_or_accuracy_concern": concern,
            "method": "rule-based",
        }

    intro = _events(turns, {"introduced_self"})
    purpose = _first_span(turns, "topics", {"purpose_agenda"}, within=4)
    concern = _first_span(turns, "topics", {"chief_complaint", "patient_expectations"}, within=4)
    parts = [p for p in (intro[0] if intro else None, purpose, concern) if p]
    gaps = [g for g, ok in (("introduce yourself and your role", intro), ("state the purpose or agenda", purpose), ("ask about the main concern early", concern)) if not ok]
    put("opening_and_purpose", 1 + len(parts), parts, "Opened with " + str(len(parts)) + " of 3 opening elements." if parts else "", ("Next time: " + "; ".join(gaps) + ".") if gaps else "")

    empathy = [(t["idx"], h["span"]) for t in turns for h in t["intent"].get("empathy", [])]
    negative = _events(turns, {"lectured_or_judged", "blunt_sensitive_question", "ignored_cue"})
    e, n = len(empathy), len(negative)
    score = 4 if e >= 3 and n == 0 else 3 if e >= 1 and n <= 1 else 2 if (e >= 1 or n <= 1) else 1
    put("rapport_respect_empathy", score, empathy + negative, f"{e} empathic statements." if e else "", "Moments that cost trust: " + "; ".join(q for _, q in negative) if negative else ("Acknowledge feelings out loud more often." if e < 2 else ""))

    expected = [f for o in signals["elicited"] for f in o["found"] + o["missed"]]
    found = [f for o in signals["elicited"] for f in o["found"]]
    ratio = len(found) / len(expected) if expected else 0.0
    score = 4 if ratio >= 0.75 else 3 if ratio >= 0.5 else 2 if ratio >= 0.25 else 1
    open_spans = [(t["idx"], t["student_text"]) for t in turns if t["intent"].get("question_type") == "open"][:2]
    put("information_gathering", score, open_spans, f"Found {len(found)} of {len(expected)} key facts.", "Missed: " + "; ".join(m["text"] for o in signals["elicited"] for m in o["missed"])[:400] if len(found) < len(expected) else "")

    followed = _events(turns, {"followed_personal_cue"})
    ignored = _events(turns, {"ignored_cue", "interrupted"})
    score = 4 if followed and not ignored else 3 if not ignored else 2 if len(ignored) <= 1 else 1
    put("listening_and_response_to_cues", score, followed + ignored, "Followed up on personal cues." if followed else "", "Ignored cues or interrupted: " + "; ".join(q for _, q in ignored) if ignored else "")

    explain_ids = {"give_information", "check_understanding", "ask_permission", "plan_next_steps"}
    got = {}
    for t in turns:
        for h in t["intent"].get("actions", []):
            if h["id"] in explain_ids and h["id"] not in got:
                got[h["id"]] = (t["idx"], h["span"])
    c = len(got)
    score = 4 if c >= 3 and "check_understanding" in got else 3 if c >= 2 else 2 if c == 1 else 1
    if signals["metrics"]["unexplained_jargon"] and score > 1:
        score -= 1
    put("explanation_and_shared_decisions", score, list(got.values()), "", "Check understanding (teach-back) and explain terms in plain words." if "check_understanding" not in got else "")

    items = [r for r in signals["decision_points"] if r["affects"] == "patient"] + [s for s in signals["safety"] if s["addressed"] is not None]
    good = [r for r in signals["decision_points"] if r["affects"] == "patient" and r["value"]] + [s for s in signals["safety"] if s["addressed"]]
    if items:
        r = len(good) / len(items)
        score = 3 if r == 1 else 2 if r >= 0.5 else 1
        ev = [(e["turn"], e["quote"]) for d in signals["decision_points"] for e in d["evidence"]][:3]
        put("clinical_reasoning_and_synthesis", score, ev, "Rule-based estimates cap at 3; faculty review needed for 4.", "; ".join(d["feedback"] for d in signals["decision_points"] if not d["value"] and d.get("feedback")))
    else:
        out["clinical_reasoning_and_synthesis"] = {"score": "N/A", "evidence": [], "strength_demonstrated": "", "important_gap_or_missed_opportunity": "", "safety_or_accuracy_concern": "", "method": "rule-based"}

    close_ids = {"summarize", "plan_next_steps", "safety_netting", "closing"}
    got = {}
    for t in turns:
        for h in t["intent"].get("actions", []):
            if h["id"] in close_ids and h["id"] not in got:
                got[h["id"]] = (t["idx"], h["span"])
    c = len(got)
    score = 4 if c >= 3 else 3 if c == 2 else 2 if c == 1 else 1
    concern_text = ""
    si_missed = [s for s in signals["safety"] if not s["discovered"] and "suicid" in s["text"].lower()]
    si_asked = any(h["id"] == "suicidal_ideation" for t in turns for h in t["intent"].get("topics", []))
    if si_missed and not si_asked:
        score, concern_text = 1, "Suicidal thoughts were not asked about. Screening for safety is expected in this case."
    put("professionalism_safety_closure", score, list(got.values()), "", "Close with a summary, a shared plan and when to come back." if c < 3 else "", concern_text)
    return out


# ---------- LLM scoring ----------

def _transcript(turns: list[dict]) -> str:
    return "\n".join(f"[T{t['idx']}] STUDENT: {t['student_text']}\n[T{t['idx']}] PATIENT: {t['reply_text']}" for t in turns)


def _signals_text(signals: dict) -> str:
    slim = {
        "metrics": signals["metrics"],
        "trust_events": [{"turn": e["turn"], "event": e["event"], "quote": e["span"]} for p in signals["trust_timeline"] for e in p["events"]],
        "elicited_vs_missed": [{"objective": o["objective"], "found": [f["text"] for f in o["found"]], "missed": [m["text"] for m in o["missed"]], "actions": o["actions"]} for o in signals["elicited"]],
        "decision_points": [{"label": d["label"], "result": d["result"]} for d in signals["decision_points"]],
        "safety_items": signals["safety"],
        "communication_notes": signals["communication_notes"],
    }
    return json.dumps(slim, ensure_ascii=False)


def llm_scores(case: Case, turns: list[dict], signals: dict, retry_problems: list[str] | None = None) -> tuple[dict, LLMCall]:
    rub = catalogs.rubric(case.rubric_id)
    domains = "\n".join(
        f"- {d['key']} ({d['name']}): " + " | ".join(f"{s}: {d['descriptors'][s]}" for s in ("4", "3", "2", "1")) for d in rub["domains"]
    )
    objectives = "\n".join(f"- {o.text}" for o in case.objectives)
    user = (
        f"CASE: {case.title}. Student role: {case.briefing.student_role}. Goal: {case.briefing.goal}\n"
        f"LEARNING OBJECTIVES:\n{objectives}\n\n"
        f"RUBRIC DOMAINS (score descriptors):\n{domains}\n\n"
        f"MEASURED SIGNALS (computed by code, trust them):\n{_signals_text(signals)}\n\n"
        f"TRANSCRIPT:\n{_transcript(turns)}"
    )
    if retry_problems:
        user += "\n\nYOUR PREVIOUS ANSWER HAD PROBLEMS, fix them: " + "; ".join(retry_problems)
    try:
        data, call = complete_json(purpose="rubric", prompt_name="rubric", user=user, strong=True, max_tokens=3500)
    except LLMUnavailable:
        failed = last_failed_call("rubric")
        raise LLMUnavailable(failed.error if failed else "rubric scoring failed") from None
    if not isinstance(data, dict):
        raise LLMUnavailable("rubric output was not an object")
    return data, call


def validate_llm_domains(data: dict, turns: list[dict]) -> tuple[dict[str, dict], list[str]]:
    keys = [d["key"] for d in catalogs.rubric()["domains"]]
    by_key = {d.get("key"): d for d in data.get("domains", []) if isinstance(d, dict)}
    good: dict[str, dict] = {}
    problems: list[str] = []
    for k in keys:
        d = by_key.get(k)
        if d is None:
            problems.append(f"{k}: missing")
            continue
        score = d.get("score")
        if score not in (1, 2, 3, 4, "N/A"):
            problems.append(f"{k}: invalid score {score!r}")
            continue
        evidence = [e for e in d.get("evidence", []) if isinstance(e, dict) and quote_valid(str(e.get("quote", "")), int(e.get("turn", -1) or -1), turns)]
        # A 1 needs a span too. N/A is the only score that can stand without one.
        if score != "N/A" and not evidence:
            problems.append(f"{k}: no quote found verbatim in the transcript")
            continue
        good[k] = {
            "score": score,
            "evidence": [{"turn": int(e["turn"]), "quote": str(e["quote"])} for e in evidence][:3],
            **{f: str(d.get(f, "") or "") for f in EVIDENCE_FIELDS},
            "method": "llm",
        }
    return good, problems


def _first_student_quote(turns: list[dict]) -> dict | None:
    """The first thing the student actually said, used only when a narrower span is missing."""
    for turn in turns:
        text = str(turn.get("student_text") or "").strip()
        if text and quote_valid(text, int(turn["idx"]), turns):
            return {"turn": int(turn["idx"]), "quote": text}
    return None


def _with_citation(chosen: dict, turns: list[dict]) -> dict:
    """Keep a numeric score only when its quote is in the transcript. Otherwise the score is N/A."""
    evidence: list[dict] = []
    for item in chosen.get("evidence") or []:
        if not isinstance(item, dict):
            continue
        turn = item.get("turn")
        quote = str(item.get("quote") or "")
        if isinstance(turn, int) and quote_valid(quote, turn, turns):
            evidence.append({"turn": turn, "quote": quote})
    if chosen.get("score") != "N/A" and not evidence:
        # The rule found no shorter span. The student's own words are still a real span.
        spoken = _first_student_quote(turns)
        if spoken is not None:
            evidence = [spoken]
    if chosen.get("score") != "N/A" and not evidence:
        return {**chosen, "score": "N/A", "evidence": []}
    return {**chosen, "evidence": evidence[:3]}


def score_rubric(case: Case, turns: list[dict], signals: dict, use_llm: bool) -> tuple[dict, list[dict]]:
    """Return (rubric_result, llm_calls)."""
    rub = catalogs.rubric(case.rubric_id)
    rules = rule_based_scores(case, turns, signals)
    calls: list[dict] = []
    llm_domains: dict[str, dict] = {}
    extras: dict = {}
    if use_llm and turns:
        problems = None
        for _ in range(2):
            try:
                data, call = llm_scores(case, turns, signals, problems)
                calls.append(call.to_dict())
            except LLMUnavailable:
                break
            got, problems = validate_llm_domains(data, turns)
            llm_domains.update(got)
            extras = {k: data.get(k) for k in ("strengths", "improvements", "next_attempt")}
            if not problems:
                break
    domains = []
    for d in rub["domains"]:
        chosen = _with_citation(llm_domains.get(d["key"]) or rules[d["key"]], turns)
        domains.append({"key": d["key"], "name": d["name"], "id": d["id"], **chosen, "rule_based_score": rules[d["key"]]["score"]})
    numeric = [x["score"] for x in domains if isinstance(x["score"], int)]
    review = [x["name"] for x in domains if x["id"] in rub["scoring"]["review_trigger_domain_ids"] and x["score"] == 1]
    result = {
        "rubric_title": rub["title"],
        "domains": domains,
        "total": sum(numeric),
        "max_total": 4 * len(numeric),
        "review_flag": bool(review),
        "review_reasons": review,
        "interpretation": rub["scoring"]["interpretation"],
        "strengths": _valid_items(extras.get("strengths"), turns),
        "improvements": _valid_items(extras.get("improvements"), turns),
        "next_attempt": [str(x) for x in (extras.get("next_attempt") or [])][:3],
    }
    return result, calls


def _valid_items(items, turns: list[dict]) -> list[dict]:
    out = []
    for it in items or []:
        if not isinstance(it, dict) or not it.get("text"):
            continue
        quote, turn = str(it.get("quote", "")), it.get("turn")
        ok = isinstance(turn, int) and quote_valid(quote, turn, turns)
        out.append({"text": str(it["text"]), "turn": turn if ok else None, "quote": quote if ok else None})
    return out[:3]
