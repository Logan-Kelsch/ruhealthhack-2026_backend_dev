"""Intent classifier: maps one student utterance onto closed label sets.

Primary path: Claude on Bedrock at temperature 0 with a fixed output shape.
Fallback path: keyword rules from the vocab files (used offline and in tests).
Every label must carry a span that appears verbatim in the utterance, or it is dropped.
"""
from __future__ import annotations

import json
import re

from app import catalogs
from app.integrations.bedrock import LLMCall, LLMUnavailable, complete_json, last_failed_call
from app.schemas.case import Case
from app.schemas.encounter import Hit, Intent, JargonHit

OPEN_RE = re.compile(
    r"^\s*(?:(?:so|and|okay|ok|alright|well),?\s+)*(what|how|why|tell me|describe|can you (?:tell|describe|walk|share)|"
    r"could you (?:tell|describe|walk|share)|walk me through|help me understand|in what way|what's|how's)\b",
    re.IGNORECASE,
)
CLOSED_RE = re.compile(
    r"^\s*(?:(?:so|and|okay|ok|alright|well),?\s+)*(do|does|did|are|is|was|were|have|has|had|can|could|will|would|any|should)\b",
    re.IGNORECASE,
)
REFLECTION_RES = [
    re.compile(p, re.IGNORECASE)
    for p in [r"\b(it )?sounds like\b", r"\bso you(?:'re| are) (feeling|saying|worried)", r"\byou feel\b", r"\bwhat i(?:'m| am) hearing\b", r"\byou(?:'ve| have) been (feeling|dealing)"]
]
VALIDATION_RES = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bthat (must|sounds|would) (be )?(really )?(hard|difficult|frustrating|tough|scary|overwhelming|stressful)",
        r"\bi (can )?(understand|imagine|see why)",
        r"\bmakes (a lot of )?sense\b",
        r"\bi(?:'m| am) (so )?sorry (to hear|that|you)",
        r"\bthank you for (sharing|telling|being)",
        r"\bthat(?:'s| is) (completely |totally )?(understandable|normal|okay to feel)",
    ]
]
EXPLAIN_RE = re.compile(r"\b(which means|that means|in other words|meaning|basically|in plain terms)\b", re.IGNORECASE)
EXAM_VERB_RE = re.compile(r"\b(look|listen|feel|check|examine|exam|press|tap|test|take a look|palpate|percuss|auscultate)\b", re.IGNORECASE)
ORDER_VERB_RE = re.compile(r"\b(order|check|run|draw|get|test|send|look at)\b", re.IGNORECASE)

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip(" .,!?;:\"'")


def span_ok(span: str, utterance: str) -> bool:
    n = _norm(span)
    return bool(n) and n in _norm(utterance)


def _sentence_of(utterance: str, start: int) -> str:
    pos = 0
    for sent in SENTENCE_SPLIT.split(utterance):
        end = pos + len(sent)
        if pos <= start <= end:
            return sent.strip()
        pos = end + 1
    return utterance.strip()


def case_topics(case: Case) -> dict[str, catalogs.Label]:
    out = dict(catalogs.topics())
    for t in case.topics:
        out[t.id] = catalogs.Label(t.id, t.description, tuple(t.keywords))
    return out


def case_actions(case: Case) -> dict[str, catalogs.Label]:
    out = dict(catalogs.actions())
    for a in case.actions:
        out[a.id] = catalogs.Label(a.id, a.description, tuple(a.keywords))
    return out


def question_type(utterance: str) -> str:
    sentences = [s for s in SENTENCE_SPLIT.split(utterance.strip()) if s]
    if any(OPEN_RE.search(s) and s.rstrip().endswith("?") or OPEN_RE.search(s) and s.lower().startswith(("tell me", "describe", "walk me")) for s in sentences):
        return "open"
    if any(s.rstrip().endswith("?") or CLOSED_RE.search(s) for s in sentences):
        return "closed"
    return "statement"


def detect_jargon(utterance: str) -> list[JargonHit]:
    hits = []
    explained_anywhere = bool(EXPLAIN_RE.search(utterance))
    low = utterance.lower()
    for entry in catalogs.lay_lexicon():
        term = entry["term"]
        m = re.search(rf"\b{re.escape(term)}", low)
        if m:
            explained = explained_anywhere or entry["lay"].lower() in low
            hits.append(JargonHit(term=term, span=_sentence_of(utterance, m.start()), explained=explained))
    return hits


def _negated_critical_action(utterance: str, start: int, action_id: str) -> bool:
    """Suppress explicit refusals in the keyword fallback, not inferred clinical intent."""
    if action_id not in {"prescribe_antibiotic", "start_medication", "safety_netting"}:
        return False
    prefix = re.split(r"[.;!?\n]|\b(?:but|however|and)\b", utterance[:start], flags=re.IGNORECASE)[-1]
    if re.search(r"\b(?:not|never|won't|wouldn't|don't|doesn't|didn't|can't|cannot|shouldn't)\s+(?:(?:going|planning|able|ready|want|intend|plan)\s+to\s+)?$", prefix, re.IGNORECASE):
        return True
    return action_id == "safety_netting" and bool(re.search(
        r"\b(?:not|never)\s+(?:explained|discussed|provided|given)\s+(?:(?:any|the|these)\s+)?$", prefix, re.IGNORECASE))


def keyword_classify(utterance: str, case: Case) -> Intent:
    def match_labels(labels: dict[str, catalogs.Label], *, action: bool = False) -> list[Hit]:
        hits = []
        for label in labels.values():
            for pat in label.patterns():
                m = next((m for m in pat.finditer(utterance)
                          if not action or not _negated_critical_action(utterance, m.start(), label.id)), None)
                if m is not None:
                    hits.append(Hit(id=label.id, span=_sentence_of(utterance, m.start()), confidence="low"))
                    break
        return hits

    topics = match_labels(case_topics(case))
    actions = match_labels(case_actions(case), action=True)
    maneuvers: list[Hit] = []
    if EXAM_VERB_RE.search(utterance):
        for m_id, m in catalogs.maneuvers().items():
            for k in m.get("keywords", []):
                mm = re.search(k, utterance, re.IGNORECASE)
                if mm:
                    maneuvers.append(Hit(id=m_id, span=_sentence_of(utterance, mm.start()), confidence="low"))
                    break
    orders: list[Hit] = []
    if ORDER_VERB_RE.search(utterance) or "order_test" in {a.id for a in actions}:
        for p_id, p in catalogs.lab_catalog()["panels"].items():
            for k in p.get("keywords", []):
                mm = re.search(k, utterance, re.IGNORECASE)
                if mm:
                    orders.append(Hit(id=p_id, span=_sentence_of(utterance, mm.start()), confidence="low"))
                    break
    empathy: list[Hit] = []
    for kind, pats in (("reflection", REFLECTION_RES), ("validation", VALIDATION_RES)):
        for pat in pats:
            m = pat.search(utterance)
            if m:
                empathy.append(Hit(id=kind, span=_sentence_of(utterance, m.start()), confidence="low"))
                break
    return Intent(
        topics=topics,
        actions=actions,
        maneuvers=maneuvers,
        orders=orders,
        empathy=empathy,
        jargon=detect_jargon(utterance),
        question_type=question_type(utterance),  # type: ignore[arg-type]
        source="keywords",
    )


def _validate_llm(data: dict, utterance: str, case: Case) -> Intent:
    topics = case_topics(case)
    acts = case_actions(case)
    mans = catalogs.maneuvers()
    panels = catalogs.lab_catalog()["panels"]

    def hits(key: str, allowed) -> list[Hit]:
        out = []
        for h in data.get(key) or []:
            if not isinstance(h, dict):
                continue
            hid, span = str(h.get("id", "")), str(h.get("span", ""))
            if hid in allowed and span_ok(span, utterance):
                conf = "low" if h.get("confidence") == "low" else "high"
                out.append(Hit(id=hid, span=span, confidence=conf))
        return out

    jargon = []
    for j in data.get("jargon") or []:
        if isinstance(j, dict) and span_ok(str(j.get("span", "")), utterance):
            jargon.append(JargonHit(term=str(j.get("term", "")), span=str(j["span"]), explained=bool(j.get("explained"))))
    qt = data.get("question_type")
    return Intent(
        topics=hits("topics", topics),
        actions=hits("actions", acts),
        maneuvers=hits("maneuvers", mans),
        orders=hits("orders", panels),
        empathy=hits("empathy", {"reflection", "validation"}),
        jargon=jargon or detect_jargon(utterance),
        question_type=qt if qt in ("open", "closed", "statement") else question_type(utterance),
        source="llm",
    )


def _catalog_text(case: Case) -> str:
    lines = ["TOPICS:"]
    lines += [f"- {t.id}: {t.description}" for t in case_topics(case).values()]
    lines.append("ACTIONS:")
    lines += [f"- {a.id}: {a.description}" for a in case_actions(case).values()]
    lines.append("MANEUVERS (physical exam):")
    lines += [f"- {m_id}: {m['label']}" for m_id, m in catalogs.maneuvers().items()]
    lines.append("ORDERS (lab or test panels):")
    lines += [f"- {p_id}: {p['label']}" for p_id, p in catalogs.lab_catalog()["panels"].items()]
    return "\n".join(lines)


def classify(utterance: str, case: Case, last_patient_line: str | None = None) -> tuple[Intent, list[LLMCall]]:
    calls: list[LLMCall] = []
    user = (
        f"{_catalog_text(case)}\n\n"
        f"PATIENT'S PREVIOUS LINE: {json.dumps(last_patient_line or '')}\n"
        f"STUDENT UTTERANCE: {json.dumps(utterance)}"
    )
    try:
        data, call = complete_json(purpose="classify", prompt_name="classifier", user=user, max_tokens=900)
        calls.append(call)
        intent = _validate_llm(data if isinstance(data, dict) else {}, utterance, case)
        return intent, calls
    except LLMUnavailable:
        failed = last_failed_call("classify")
        if failed:
            calls.append(failed)
        return keyword_classify(utterance, case), calls
