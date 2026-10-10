"""Guided intake (PRD S-02): a short list of questions for whatever the case is missing.

Kept simple on purpose. The gap list is computed by code from the case document, the
faculty member answers in plain words (typed in V1; an optional voice conversation can be
added later on the same endpoint), and each answer becomes draft facts.
"""
from __future__ import annotations

import re

from app.integrations.bedrock import LLMUnavailable, complete_json
from app.schemas.case import Case, Fact, Source, Unlock
from app.studio.drafting import clean_facts

# id, question, fact category, topics the new fact unlocks on, test for "already covered"
FACT_GAPS: list[tuple[str, str, str, list[str], callable]] = [
    ("chief_complaint", "In the patient's own words, why are they here today?", "presenting", ["chief_complaint"],
     lambda c: any(f.tier == "initial" for f in c.facts)),
    ("medications", "What medicines does the patient take, and do they take them as prescribed?", "medication", ["medication_list", "medication_adherence"],
     lambda c: bool(c.medications) or any(f.category == "medication" for f in c.facts)),
    ("allergies", "Any allergies? If none, say \"no known allergies\".", "allergy", ["allergies"],
     lambda c: bool(c.allergies) or any(f.category == "allergy" for f in c.facts)),
    ("social", "Who do they live with, and what is daily life like (work, money, support)?", "social", ["social_living", "social_support", "occupation"],
     lambda c: any(f.category == "social" for f in c.facts)),
    ("personal_cue", "What is one personal detail the patient might mention in passing (a pet, a hobby, a person)?", "personal", ["hobbies_personal"],
     lambda c: any(f.cue for f in c.facts)),
    ("hidden", "What does the patient only share once they trust the student?", "personal", ["fears_worries", "stress"],
     lambda c: any(f.tier in ("reluctant", "hidden") for f in c.facts)),
    ("goals_fears", "What does the patient want from this visit, and what worries them?", "goal", ["goals", "fears_worries", "patient_expectations"],
     lambda c: any(f.category in ("goal", "fear") for f in c.facts)),
]


def gaps(case: Case) -> list[dict]:
    out: list[dict] = []
    p, b = case.profile, case.briefing
    if not p.name or p.name.lower() in ("new patient", "unknown"):
        out.append({"id": "name", "question": "What is the patient's name?", "kind": "field", "blocking": True})
    if not p.age:
        out.append({"id": "age", "question": "How old is the patient?", "kind": "field", "blocking": True})
    if not b.reason_for_visit:
        out.append({"id": "reason_for_visit", "question": "What is the reason for the visit, as it would appear on the schedule?", "kind": "field", "blocking": True})
    if not b.student_role:
        out.append({"id": "student_role", "question": "Who is the student in this encounter (profession and training level)?", "kind": "field", "blocking": True})
    if not b.goal:
        out.append({"id": "goal", "question": "What should the student accomplish in this visit?", "kind": "field", "blocking": True})
    for gid, question, _cat, _topics, covered in FACT_GAPS:
        if not covered(case):
            out.append({"id": gid, "question": question, "kind": "facts", "blocking": gid in ("chief_complaint",)})
    if not case.objectives:
        out.append({"id": "objectives", "question": "What are one to three things the student should learn from this case?", "kind": "objectives", "blocking": True})
    if not case.vitals:
        out.append({"id": "vitals", "question": "No vital signs yet. Use auto-fill, or type them in.", "kind": "autofill", "blocking": False})
    return out


def _next_id(case: Case, prefix: str) -> str:
    n = 1
    while case.fact(f"{prefix}_{n}"):
        n += 1
    return f"{prefix}_{n}"


def answer(case: Case, gap_id: str, text: str, faculty: str | None, use_llm: bool) -> tuple[Case, list[dict]]:
    """Apply one answer. Returns the updated case and any LLM call records."""
    text = text.strip()
    calls: list[dict] = []
    if not text:
        return case, calls
    p, b = case.profile, case.briefing
    if gap_id == "name":
        p.name = text
    elif gap_id == "age":
        m = re.search(r"\d{1,3}", text)
        if m:
            p.age = int(m.group(0))
    elif gap_id in ("reason_for_visit", "student_role", "goal"):
        setattr(b, gap_id, text)
    elif gap_id == "objectives":
        from app.schemas.case import Objective

        for i, line in enumerate([s.strip(" -•") for s in re.split(r"[\n;]+", text) if s.strip()], len(case.objectives) + 1):
            case.objectives.append(Objective(id=f"obj_{i}", text=line, status="draft"))
    else:
        spec = next((g for g in FACT_GAPS if g[0] == gap_id), None)
        category, topics = (spec[2], spec[3]) if spec else ("other", [])
        tier = "reluctant" if gap_id == "hidden" else "initial" if gap_id == "chief_complaint" else "discoverable"
        new_facts: list[Fact] = []
        if use_llm:
            try:
                data, call = complete_json(
                    purpose="intake", prompt_name="intake",
                    user=f"PATIENT: {p.name}, {p.age}, {p.sex}\nQUESTION: {spec[1] if spec else gap_id}\nFACULTY ANSWER: {text}\nDEFAULT TIER: {tier}\nDEFAULT TOPICS: {topics}",
                )
                calls.append(call.to_dict())
                new_facts = clean_facts(data.get("facts", []) if isinstance(data, dict) else [], prefix=f"f_{gap_id}", existing=case)
            except LLMUnavailable:
                new_facts = []
        if not new_facts:
            new_facts = [Fact(id=_next_id(case, f"f_{gap_id}"), category=category, text=text, tier=tier, cue=gap_id == "personal_cue",
                              unlock=Unlock(topics=topics, min_trust=2 if tier == "reluctant" else None), status="draft")]
        for f in new_facts:
            f.source = Source(kind="faculty", by=faculty, ref=f"intake:{gap_id}")
            f.status = "draft"
            if not f.unlock.topics:
                f.unlock.topics = topics
        case.facts.extend(new_facts)
    return case, calls
