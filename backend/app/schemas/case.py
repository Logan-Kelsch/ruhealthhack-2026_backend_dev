"""The case document: one JSON document per patient, validated here.

This is the source of truth for the case format (PRD section 8.1). Change the schema
here first, then regenerate frontend types. Terms follow context.md section 14.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Tier = Literal["initial", "discoverable", "reluctant", "hidden"]
ItemStatus = Literal["draft", "approved"]
SourceKind = Literal["faculty", "vhs_import", "reference", "rule", "computed", "default", "llm_draft", "nhanes"]


class Source(BaseModel):
    kind: SourceKind = "faculty"
    ref: str | None = None  # citation, guideline, formula, or import path
    by: str | None = None  # faculty name when kind == "faculty"


class Code(BaseModel):
    system: Literal["ICD-10-CM", "LOINC", "RxNorm", "SNOMED-CT"]
    code: str
    display: str


class Unlock(BaseModel):
    topics: list[str] = Field(default_factory=list)  # any of these topics makes the fact eligible
    min_trust: int | None = None  # overrides the tier threshold
    requires_facts: list[str] = Field(default_factory=list)  # all must be disclosed first


class Belief(BaseModel):
    """What the patient believes when it differs from the chart (unreliable narrator)."""

    text: str
    say: str | None = None


class Fact(BaseModel):
    id: str
    category: str = "history"  # presenting, history, medication, allergy, social, diet, family, psych, ros, personal, goal, fear, small_talk, other
    text: str  # third-person chart truth
    say: str | None = None  # first-person lay phrasing; the template fallback speaks this verbatim
    value: float | str | None = None
    unit: str | None = None
    tier: Tier = "discoverable"
    unlock: Unlock = Field(default_factory=Unlock)
    belief: Belief | None = None
    cue: bool = False  # a personal rapport cue; following up earns trust
    safety: bool = False  # a safety teaching point (for example NSAID use with heart failure)
    chart_section: str | None = None  # when disclosed, show under this chart heading
    codes: list[Code] = Field(default_factory=list)
    source: Source = Field(default_factory=Source)
    status: ItemStatus = "draft"


class Release(BaseModel):
    on: Literal["visit_start", "order", "topic", "fact"] = "order"
    topics: list[str] = Field(default_factory=list)
    fact_id: str | None = None


class Vital(BaseModel):
    key: str  # bp, hr, rr, temp_c, spo2, weight, height, bmi
    label: str
    value: str
    unit: str = ""
    source: Source = Field(default_factory=Source)
    status: ItemStatus = "draft"


class ValueRange(BaseModel):
    low: float
    high: float


class LabResult(BaseModel):
    id: str
    key: str  # catalog key, for example "na"
    name: str
    loinc: str | None = None
    panel: str | None = None
    value: float | str
    unit: str = ""
    ref_low: float | None = None
    ref_high: float | None = None
    ref_source: str | None = None
    range: ValueRange | None = None  # faculty range, sampled with the case seed
    collected: str | None = None  # for example "3 days ago"
    release: Release = Field(default_factory=Release)
    source: Source = Field(default_factory=Source)
    status: ItemStatus = "draft"

    def flag(self) -> str | None:
        if not isinstance(self.value, (int, float)):
            return None
        if self.ref_low is not None and self.value < self.ref_low:
            return "low"
        if self.ref_high is not None and self.value > self.ref_high:
            return "high"
        return None


class ExamFinding(BaseModel):
    maneuver: str  # id from vocab/maneuvers.yaml
    finding: str
    abnormal: bool = True
    source: Source = Field(default_factory=Source)
    status: ItemStatus = "draft"


class Artifact(BaseModel):
    id: str
    kind: Literal["prior_note", "referral", "lab_report", "ecg", "xray", "ct", "image", "questionnaire", "other"] = "other"
    title: str
    body: str | None = None
    url: str | None = None
    release: Release = Field(default_factory=lambda: Release(on="visit_start"))
    license: str | None = None
    attribution: str | None = None
    source: Source = Field(default_factory=Source)
    status: ItemStatus = "draft"


class Diagnosis(BaseModel):
    name: str
    codes: list[Code] = Field(default_factory=list)
    release: Release = Field(default_factory=lambda: Release(on="visit_start"))
    source: Source = Field(default_factory=Source)
    status: ItemStatus = "draft"


class Medication(BaseModel):
    name: str
    dose: str | None = None
    frequency: str | None = None
    purpose: str | None = None
    codes: list[Code] = Field(default_factory=list)
    release: Release = Field(default_factory=lambda: Release(on="visit_start"))
    source: Source = Field(default_factory=Source)
    status: ItemStatus = "draft"


class Allergy(BaseModel):
    substance: str
    reaction: str | None = None
    release: Release = Field(default_factory=lambda: Release(on="visit_start"))
    source: Source = Field(default_factory=Source)
    status: ItemStatus = "draft"


class Objective(BaseModel):
    id: str
    text: str
    expected_discoveries: list[str] = Field(default_factory=list)  # fact ids
    expected_actions: list[str] = Field(default_factory=list)  # action ids
    rubric_domains: list[str] = Field(default_factory=list)
    status: ItemStatus = "draft"


class CaseVocabItem(BaseModel):
    """A case-specific topic or action, added to the classifier's closed label set."""

    id: str
    description: str
    keywords: list[str] = Field(default_factory=list)


class Personality(BaseModel):
    summary: str = ""
    communication_style: str = ""
    traits: dict[str, float] = Field(default_factory=dict)  # irritability, verbosity, humor, openness (0-1)
    health_literacy: Literal["low", "medium", "high"] = "medium"
    mood: str = "neutral"
    example_lines: list[str] = Field(default_factory=list)


class Profile(BaseModel):
    name: str
    age: int
    sex: Literal["male", "female", "other"] = "other"
    pronouns: str | None = None
    portrait: str | None = None  # file name in data/portraits
    voice_id: str | None = None
    occupation: str | None = None
    summary: str = ""  # faculty-facing one-paragraph summary, never spoken
    speaker: str | None = None  # who talks, when not the patient (for example a parent)
    personality: Personality = Field(default_factory=Personality)


class Briefing(BaseModel):
    setting: str = ""
    reason_for_visit: str = ""
    goal: str = ""
    student_role: str = ""
    show_doorway_vitals: bool = True


class DecisionPoint(BaseModel):
    """A yes/no condition checked at the end of a visit (PRD L-03).

    predicate grammar (JSON):
      {"topic": id} | {"action": id} | {"maneuver": id} | {"order": panel}
      {"fact_disclosed": fact_id} | {"any": [p, ...]} | {"all": [p, ...]} | {"not": p}
      {"before": [p_first, p_second]}  # p_first happened in an earlier turn than p_second
    """

    id: str
    label: str
    predicate: dict[str, Any]
    affects: Literal["patient", "score"] = "patient"
    rubric_domain: str | None = None
    feedback_if_yes: str | None = None
    feedback_if_no: str | None = None


class VisitChanges(BaseModel):
    add_facts: list[Fact] = Field(default_factory=list)
    update_facts: dict[str, dict[str, Any]] = Field(default_factory=dict)
    remove_facts: list[str] = Field(default_factory=list)
    vitals: list[Vital] = Field(default_factory=list)  # replaces by key
    labs: list[LabResult] = Field(default_factory=list)  # replaces by key
    exam: list[ExamFinding] = Field(default_factory=list)  # replaces by maneuver
    artifacts: list[Artifact] = Field(default_factory=list)  # replaces by id
    medications: list[Medication] | None = None  # replaces the whole list when set
    briefing: Briefing | None = None
    mood: str | None = None


class Branch(BaseModel):
    """A faculty-written outcome applied to the next visit when its conditions match."""

    id: str
    label: str
    when: dict[str, bool] = Field(default_factory=dict)  # decision point id -> required result
    # Only eligible if the previous visit took one of these branches (empty = any path).
    after_branches: list[str] = Field(default_factory=list)
    summary: str = ""  # one or two sentences: what happens
    tag: Literal["common", "rare"] | None = None
    changes: VisitChanges = Field(default_factory=VisitChanges)
    status: ItemStatus = "draft"


class Visit(BaseModel):
    id: str
    label: str
    day: int = 0
    changes: VisitChanges = Field(default_factory=VisitChanges)
    decision_points: list[DecisionPoint] = Field(default_factory=list)
    branches: list[Branch] = Field(default_factory=list)  # first match wins; applied to the next visit


class TrustConfig(BaseModel):
    start: int = 0
    thresholds: dict[str, int] = Field(default_factory=lambda: {"reluctant": 3, "hidden": 5})


class Difficulty(BaseModel):
    preset: Literal["straightforward", "typical", "difficult", "custom"] = "typical"
    params: dict[str, Any] = Field(default_factory=dict)


class ConsistencyFinding(BaseModel):
    id: str
    rule: str
    severity: Literal["review", "info"] = "review"
    message: str
    refs: list[str] = Field(default_factory=list)
    dismissed: bool = False


class Credit(BaseModel):
    what: str
    source: str
    license: str | None = None


class Case(BaseModel):
    case_id: str
    version: int = 1
    status: Literal["draft", "published", "archived"] = "draft"
    title: str
    description: str = ""  # the faculty member's original plain-language description
    seed: int = 1
    profile: Profile
    briefing: Briefing = Field(default_factory=Briefing)
    facts: list[Fact] = Field(default_factory=list)
    vitals: list[Vital] = Field(default_factory=list)
    labs: list[LabResult] = Field(default_factory=list)
    exam: list[ExamFinding] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)
    diagnoses: list[Diagnosis] = Field(default_factory=list)
    medications: list[Medication] = Field(default_factory=list)
    allergies: list[Allergy] = Field(default_factory=list)
    objectives: list[Objective] = Field(default_factory=list)
    topics: list[CaseVocabItem] = Field(default_factory=list)
    actions: list[CaseVocabItem] = Field(default_factory=list)
    rubric_id: str = "shp_patient_encounter_v1"
    documentation_template: Literal["PES", "ADIME", "SBAR", "SOAP"] = "SOAP"
    trust: TrustConfig = Field(default_factory=TrustConfig)
    difficulty: Difficulty = Field(default_factory=Difficulty)
    visits: list[Visit] = Field(default_factory=lambda: [Visit(id="v1", label="Visit 1")])
    consistency_findings: list[ConsistencyFinding] = Field(default_factory=list)
    credits: list[Credit] = Field(default_factory=list)
    created_by: str | None = None
    golden: bool = False  # a fully authored, clinically reviewed case

    def fact(self, fact_id: str) -> Fact | None:
        return next((f for f in self.facts if f.id == fact_id), None)

    def visit(self, visit_id: str) -> Visit | None:
        return next((v for v in self.visits if v.id == visit_id), None)
