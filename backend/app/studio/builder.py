"""Guided case builder (PRD S-01 to S-04): the form faculty fill in, step by step.

Three pieces, all reusing the existing Studio rules:
- suggest(): the fast model reads the description and proposes words for the form fields.
  It never proposes vital signs or lab values (AGENTS rule 3). Faculty edit every field.
- typical_vitals(): resting vitals from the reference bands and condition rules in auto-fill,
  each with its source. No model involved.
- build(): turns the finished form into a draft case. History answers go through the same
  intake mapping as the guided questions, so the gap list and publish blockers still apply.
"""
from __future__ import annotations

import re
import zlib
from typing import Literal

from pydantic import BaseModel, Field

from app.integrations.bedrock import LLMUnavailable, complete_json
from app.schemas.case import (
    Allergy, Briefing, Case, Code, Diagnosis, Difficulty, Fact, Medication, Personality, Profile, Source, Unlock, Vital,
)
from app.studio import intake
from app.studio.autofill import autofill_vitals
from app.studio.drafting import _slug, blank_case

Sex = Literal["male", "female", "other"]
Literacy = Literal["low", "medium", "high"]
Template = Literal["PES", "ADIME", "SBAR", "SOAP"]
Preset = Literal["straightforward", "typical", "difficult"]


class BuilderCondition(BaseModel):
    name: str
    code: str | None = None  # ICD-10-CM code from the lookup, when faculty picked one


class BuilderMedication(BaseModel):
    name: str
    dose: str | None = None
    frequency: str | None = None
    purpose: str | None = None


class BuilderAllergy(BaseModel):
    substance: str
    reaction: str | None = None


class BuilderVital(BaseModel):
    key: str  # bp, hr, rr, temp_c, spo2, height, weight
    label: str
    value: str
    unit: str = ""
    source: Source = Field(default_factory=Source)


class BuilderForm(BaseModel):
    """Everything the builder asks. Empty strings mean the faculty member left it blank."""

    description: str = Field(min_length=10, max_length=8000)
    notes: str = Field(default="", max_length=8000)
    name: str = ""
    age: int | None = Field(default=None, ge=0, le=120)
    sex: Sex = "other"
    pronouns: str = ""
    occupation: str = ""
    speaker: str = ""  # who talks when it is not the patient, for example a parent
    setting: str = ""
    reason_for_visit: str = ""
    student_role: str = ""
    goal: str = ""
    chief_complaint: str = ""
    social: str = ""
    goals_fears: str = ""
    hidden: str = ""
    personal_cue: str = ""
    objectives: str = ""
    conditions: list[BuilderCondition] = Field(default_factory=list)
    medications: list[BuilderMedication] = Field(default_factory=list)
    allergies: list[BuilderAllergy] = Field(default_factory=list)
    no_known_allergies: bool = False
    personality: str = ""
    communication_style: str = ""
    health_literacy: Literacy = "medium"
    mood: str = ""
    difficulty: Preset = "typical"
    documentation_template: Template = "SOAP"
    show_doorway_vitals: bool = True
    vitals: list[BuilderVital] = Field(default_factory=list)


class BuilderSuggestion(BaseModel):
    """Proposed words for the form. Fields the description does not support stay empty."""

    form: BuilderForm
    used_model: bool
    note: str | None = None


# Fields the model may fill. Numbers other than age are not on this list on purpose.
TEXT_FIELDS = (
    "name", "pronouns", "occupation", "speaker", "setting", "reason_for_visit", "student_role", "goal",
    "chief_complaint", "social", "goals_fears", "hidden", "personal_cue", "objectives",
    "personality", "communication_style", "mood",
)


def suggest(description: str, notes: str, use_llm: bool) -> tuple[BuilderSuggestion, list[dict]]:
    base = blank_case(description, None)
    form = BuilderForm(description=description, notes=notes, age=base.profile.age or None, sex=base.profile.sex)
    if not use_llm:
        return BuilderSuggestion(form=form, used_model=False, note="Suggestions are off, so only the age and sex were read from the description."), []
    user = f"DESCRIPTION:\n{description}\n\nFACULTY NOTES:\n{notes.strip() or '(none)'}\n"
    try:
        data, call = complete_json(purpose="builder_suggest", prompt_name="builder_suggest", user=user, max_tokens=2000)
    except LLMUnavailable as exc:
        calls = exc.call.to_dicts() if exc.call else []
        return BuilderSuggestion(form=form, used_model=False, note="The suggestion service did not answer. Fill in the fields yourself."), calls
    if not isinstance(data, dict):
        return BuilderSuggestion(form=form, used_model=False, note="The suggestion came back unreadable. Fill in the fields yourself."), call.to_dicts()
    for key in TEXT_FIELDS:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            setattr(form, key, value.strip())
        elif isinstance(value, list) and key == "objectives":
            form.objectives = "\n".join(str(v).strip() for v in value if str(v).strip())
    age = data.get("age")
    if isinstance(age, int) and 0 < age <= 120:
        form.age = age
    if data.get("sex") in ("male", "female", "other"):
        form.sex = data["sex"]
    if data.get("health_literacy") in ("low", "medium", "high"):
        form.health_literacy = data["health_literacy"]
    if data.get("documentation_template") in ("PES", "ADIME", "SBAR", "SOAP"):
        form.documentation_template = data["documentation_template"]
    form.conditions = [BuilderCondition(name=str(c).strip()) for c in data.get("conditions", []) if str(c).strip()]
    form.medications = [BuilderMedication(**{k: (str(m.get(k)).strip() if m.get(k) else None) for k in ("dose", "frequency", "purpose")}, name=str(m["name"]).strip())
                        for m in data.get("medications", []) if isinstance(m, dict) and m.get("name")]
    form.allergies = [BuilderAllergy(substance=str(a["substance"]).strip(), reaction=(str(a.get("reaction")).strip() if a.get("reaction") else None))
                      for a in data.get("allergies", []) if isinstance(a, dict) and a.get("substance")]
    form.no_known_allergies = data.get("no_known_allergies") is True and not form.allergies
    return BuilderSuggestion(form=form, used_model=True), call.to_dicts()


def typical_vitals(age: int, sex: Sex, conditions: list[BuilderCondition], description: str) -> tuple[list[BuilderVital], list[str]]:
    """Resting vitals for this age, shifted by any matching condition rule. Same seed, same numbers."""
    case = blank_case(description, None)
    case.seed = _seed(description)
    case.profile = Profile(name="draft", age=age, sex=sex)
    case.diagnoses = [Diagnosis(name=c.name, codes=_codes(c)) for c in conditions]
    vitals, notes = autofill_vitals(case)
    return [BuilderVital(key=v.key, label=v.label, value=v.value, unit=v.unit, source=v.source) for v in vitals], notes


def _codes(condition: BuilderCondition) -> list[Code]:
    if not condition.code:
        return []
    return [Code(system="ICD-10-CM", code=condition.code, display=condition.name)]


def build(form: BuilderForm, faculty: str | None) -> Case:
    """The finished form as a draft case. Every item is a draft until faculty approve it in Studio."""
    by = Source(kind="faculty", by=faculty, ref="case builder")
    name = form.name.strip() or "New patient"
    case = blank_case(form.description, faculty)
    case.seed = _seed(form.description)
    case.profile = Profile(
        name=name,
        age=form.age or 0,
        sex=form.sex,
        pronouns=form.pronouns.strip() or None,
        occupation=form.occupation.strip() or None,
        speaker=form.speaker.strip() or None,
        summary="\n\n".join(part for part in (form.description.strip(), _notes(form.notes)) if part),
        personality=Personality(
            summary=form.personality.strip(),
            communication_style=form.communication_style.strip(),
            health_literacy=form.health_literacy,
            mood=form.mood.strip() or "neutral",
        ),
    )
    case.briefing = Briefing(
        setting=form.setting.strip(),
        reason_for_visit=form.reason_for_visit.strip(),
        goal=form.goal.strip(),
        student_role=form.student_role.strip(),
        show_doorway_vitals=form.show_doorway_vitals,
    )
    reason = case.briefing.reason_for_visit
    case.title = f"{name}: {reason}" if reason else f"{name} (draft)"
    case.case_id = _slug(f"{name} {reason}") if name != "New patient" else _slug(form.description[:40])
    case.difficulty = Difficulty(preset=form.difficulty)
    case.documentation_template = form.documentation_template
    case.diagnoses = [Diagnosis(name=c.name.strip(), codes=_codes(c), source=by) for c in form.conditions if c.name.strip()]
    case.medications = [Medication(name=m.name.strip(), dose=m.dose, frequency=m.frequency, purpose=m.purpose, source=by)
                        for m in form.medications if m.name.strip()]
    case.allergies = [Allergy(substance=a.substance.strip(), reaction=a.reaction, source=by) for a in form.allergies if a.substance.strip()]
    if form.no_known_allergies and not case.allergies:
        case.facts.append(Fact(id="f_no_known_allergies", category="allergy", text="No known allergies.", say="No allergies that I know of.",
                               unlock=Unlock(topics=["allergies"]), source=by))
    case.vitals = [Vital(key=v.key, label=v.label, value=v.value.strip(), unit=v.unit, source=v.source) for v in form.vitals if v.value.strip()]
    # Same mapping as the guided questions, so facts get the same categories, tiers and topics.
    for gap_id in ("chief_complaint", "social", "goals_fears", "hidden", "personal_cue", "objectives"):
        text = getattr(form, gap_id).strip()
        if text:
            case, _ = intake.answer(case, gap_id, text, faculty, use_llm=False)
    return case


def _seed(description: str) -> int:
    """One seed per description, so a builder preview and the saved case sample the same numbers."""
    return zlib.crc32(description.strip().encode()) % 100_000 + 1


def _notes(notes: str) -> str:
    notes = re.sub(r"\s+\n", "\n", notes.strip())
    return f"Faculty notes: {notes}" if notes else ""
