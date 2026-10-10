"""Turns a faculty member's plain-language description into a draft case (PRD S-01).

The LLM only proposes structure and wording: facts, tiers, topics, objectives. It never
proposes lab or vital values; those come from auto-fill. Everything comes back as a draft
with source "llm_draft" until faculty approve it. Without the LLM, the description is kept
and the guided intake asks for the rest.
"""
from __future__ import annotations

import re

from app import catalogs
from app.integrations.bedrock import LLMUnavailable, complete_json
from app.schemas.case import (
    Allergy, Briefing, Case, Diagnosis, ExamFinding, Fact, Medication, Objective, Personality, Profile, Source, Unlock,
)

TIERS = {"initial", "discoverable", "reluctant", "hidden"}
CATEGORIES = {"presenting", "history", "medication", "allergy", "social", "diet", "family", "psych", "ros", "personal", "goal", "fear", "small_talk", "other"}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:40] or "case"


def clean_facts(raw: list, prefix: str, existing: Case | None = None) -> list[Fact]:
    """Validate LLM-proposed facts against the closed vocabularies."""
    topic_ids = set(catalogs.topics())
    taken = {f.id for f in existing.facts} if existing else set()
    out: list[Fact] = []
    for i, r in enumerate(raw, 1):
        if not isinstance(r, dict) or not str(r.get("text", "")).strip():
            continue
        fid = _slug(str(r.get("id") or f"{prefix}_{i}"))
        fid = fid if fid.startswith("f_") else f"f_{fid}"
        while fid in taken:
            fid += "_x"
        taken.add(fid)
        tier = r.get("tier") if r.get("tier") in TIERS else "discoverable"
        out.append(Fact(
            id=fid,
            category=r.get("category") if r.get("category") in CATEGORIES else "other",
            text=str(r["text"]).strip(),
            say=str(r.get("say") or "").strip() or None,
            tier=tier,
            unlock=Unlock(topics=[t for t in r.get("topics", []) if t in topic_ids][:4], min_trust=2 if tier == "reluctant" else None),
            cue=bool(r.get("cue")),
            safety=bool(r.get("safety")),
            source=Source(kind="llm_draft", ref="prompts/drafting.md"),
            status="draft",
        ))
    return out


def blank_case(description: str, faculty: str | None) -> Case:
    age = re.search(r"\b(\d{1,3})[- ]?(year|yo|y/o)", description, re.IGNORECASE)
    sex = "female" if re.search(r"\b(woman|female|girl|mother|she)\b", description, re.IGNORECASE) else "male" if re.search(r"\b(man|male|boy|father|he)\b", description, re.IGNORECASE) else "other"
    return Case(
        case_id=_slug(description[:40]),
        title="New case (draft)",
        description=description,
        profile=Profile(name="New patient", age=int(age.group(1)) if age else 0, sex=sex),
        created_by=faculty,
    )


def draft_case(description: str, faculty: str | None, use_llm: bool) -> tuple[Case, list[dict]]:
    case = blank_case(description, faculty)
    if not use_llm:
        return case, []
    maneuvers = catalogs.maneuvers()
    user = (
        f"FACULTY DESCRIPTION:\n{description}\n\n"
        f"TOPIC IDS (use only these): {', '.join(catalogs.topics())}\n"
        f"EXAM MANEUVER IDS (use only these): {', '.join(maneuvers)}\n"
    )
    try:
        data, call = complete_json(purpose="drafting", prompt_name="drafting", user=user, strong=True, max_tokens=4000)
    except LLMUnavailable:
        return case, []
    if not isinstance(data, dict):
        return case, [call.to_dict()]
    src = Source(kind="llm_draft", ref="prompts/drafting.md")
    p = data.get("profile", {}) or {}
    case.profile = Profile(
        name=str(p.get("name") or case.profile.name),
        age=int(p["age"]) if str(p.get("age", "")).isdigit() else case.profile.age,
        sex=p.get("sex") if p.get("sex") in ("male", "female", "other") else case.profile.sex,
        occupation=p.get("occupation"),
        speaker=p.get("speaker"),
        summary=description,
        personality=Personality(
            summary=str(p.get("personality", "")),
            communication_style=str(p.get("communication_style", "")),
            health_literacy=p.get("health_literacy") if p.get("health_literacy") in ("low", "medium", "high") else "medium",
            mood=str(p.get("mood") or "neutral"),
        ),
    )
    b = data.get("briefing", {}) or {}
    case.briefing = Briefing(**{k: str(b.get(k, "")) for k in ("setting", "reason_for_visit", "goal", "student_role")})
    case.title = str(data.get("title") or f"{case.profile.name}: {case.briefing.reason_for_visit}")
    case.case_id = _slug(f"{case.profile.name} {case.briefing.reason_for_visit}")
    case.facts = clean_facts(data.get("facts", []), prefix="f_draft")
    case.diagnoses = [Diagnosis(name=str(d), source=src) for d in data.get("diagnoses", []) if str(d).strip()]
    case.medications = [Medication(name=str(m.get("name")), dose=m.get("dose"), frequency=m.get("frequency"), purpose=m.get("purpose"), source=src)
                        for m in data.get("medications", []) if isinstance(m, dict) and m.get("name")]
    case.allergies = [Allergy(substance=str(a.get("substance")), reaction=a.get("reaction"), source=src)
                      for a in data.get("allergies", []) if isinstance(a, dict) and a.get("substance")]
    case.exam = [ExamFinding(maneuver=e["maneuver"], finding=str(e.get("finding", "")), source=src)
                 for e in data.get("exam", []) if isinstance(e, dict) and e.get("maneuver") in maneuvers and e.get("finding")]
    fact_ids = {f.id for f in case.facts}
    case.objectives = [Objective(id=f"obj_{i}", text=str(o.get("text")), expected_discoveries=[x for x in o.get("expected_discoveries", []) if x in fact_ids])
                       for i, o in enumerate(data.get("objectives", []), 1) if isinstance(o, dict) and o.get("text")]
    if data.get("documentation_template") in ("PES", "ADIME", "SBAR", "SOAP"):
        case.documentation_template = data["documentation_template"]
    return case, [call.to_dict()]
