"""Versioned demo contracts; these do not change production Case or Encounter."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class PatientMetadata(StrictModel):
    name: str
    age_years: int = Field(ge=0, le=120)
    sex: Literal["male", "female"]
    presenting_concern: str
    history: list[str]

class SourceSpan(StrictModel):
    category: str
    text: str
    start: int
    end: int

class MetadataExtraction(StrictModel):
    schema_version: Literal["demo_metadata_v1"] = "demo_metadata_v1"
    description: str
    name: str | None
    age_years: int | None
    sex: Literal["male", "female"] | None
    categorized_spans: list[SourceSpan]
    unmatched_spans: list[SourceSpan]
    method: Literal["deterministic_explicit_text_rules"] = "deterministic_explicit_text_rules"

class PrepareRequest(StrictModel):
    scenario_id: int = Field(ge=1, le=3)
    description: str = Field(min_length=1, max_length=12000)

class Preparation(StrictModel):
    preparation_id: str
    scenario_id: int
    fixture_version: int
    fixture_sha256: str
    patient: PatientMetadata
    extracted_metadata: MetadataExtraction
    warnings: list[str]
    execution_mode: Literal["scripted_playback"] = "scripted_playback"
    clinical_review_status: Literal["pending"] = "pending"
    simulated_delay_ms: int = 1600
    actual_model_calls: int = 0

class StartRequest(StrictModel):
    preparation_id: str
    accept_fixed_script: Literal[True]

class DemoTurnRequest(StrictModel):
    expected_step: int = Field(ge=1, le=100)
    request_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    text: str = Field(min_length=1, max_length=2000)

class ChartItem(StrictModel):
    id: str
    label: str
    text: str
    source: str
    provenance: Literal["authored_synthetic_finding"]
    urgent: bool

class TranscriptTurn(StrictModel):
    step: int
    student_text: str
    patient_text: str
    fact_ids: list[str]
    simulated_delay_ms: int

class DemoSession(StrictModel):
    session_id: str
    scenario_id: int
    fixture_sha256: str
    status: Literal["student", "ready_to_end", "ended"]
    patient_name: str
    age_years: int
    presenting_concern: str
    next_step: int | None
    total_steps: int
    transcript: list[TranscriptTurn]
    chart: list[ChartItem]
    execution_mode: Literal["scripted_playback"] = "scripted_playback"
    input_handling: Literal["sequence_position_only"] = "sequence_position_only"
    actual_model_calls: int = 0

class DemoTurnResult(StrictModel):
    session_id: str
    turn: TranscriptTurn
    chart_added: list[ChartItem]
    safety_notice: str | None  # Compatibility field: always null; coaching is in DemoDebrief.
    next_step: int | None
    complete: bool
    execution_mode: Literal["scripted_playback"] = "scripted_playback"
    actual_model_calls: int = 0

class Reflection(StrictModel):
    id: str
    domain_id: int
    domain_name: str
    question: str

class DemoDebrief(StrictModel):
    session_id: str
    delivery: Literal["after_dialogue"] = "after_dialogue"
    method: Literal["scripted_guided_reflection"] = "scripted_guided_reflection"
    reflections: list[Reflection]
    transcript: list[TranscriptTurn]
    completed_steps: int
    total_steps: int
    follows_rehearsal_script: bool
    assessment_status: Literal["not_scored"] = "not_scored"
    interpretation: str
    safety_notice: str | None

class EducatorScenario(StrictModel):
    scenario_id: int
    fixture_version: int
    title: str
    patient: PatientMetadata
    goal: str
    example_description: str
    suggested_student_sequence: list[str]
    sources: list[dict[str, str]]
    clinical_review_status: Literal["pending"] = "pending"

# These models define the replaceable fixture format, not the production Case format.
class ScriptFact(StrictModel):
    text: str
    provenance: Literal["authored_synthetic_dialogue"]

class ScriptTurn(StrictModel):
    step: int = Field(ge=1)
    suggested_student_text: str = Field(min_length=1)
    patient_text: str = Field(min_length=1)
    fact_ids: list[str] = Field(min_length=1)
    release_chart_ids: list[str]
    simulated_delay_ms: int = Field(ge=0, le=5000)

class ScriptChart(ChartItem):
    release_step: int = Field(ge=1)

class ScriptReflection(StrictModel):
    id: str
    domain_id: int = Field(ge=1, le=7)
    question: str

class ScriptDebrief(StrictModel):
    delivery: Literal["after_dialogue"]
    questions: list[ScriptReflection]

class ScriptEducator(StrictModel):
    goal: str
    example_description: str
    learner_role: str
    teaching_notes: list[str]
    sources: list[dict[str, str]]

class ScriptCase(StrictModel):
    schema_version: Literal["scripted_clinical_demo_v1"]
    scenario_id: int = Field(ge=1, le=3)
    fixture_version: int = Field(ge=1)
    title: str
    clinical_review_status: Literal["pending"]
    provenance: Literal["authored_synthetic_script"]
    model_execution: Literal["none_scripted_playback"]
    patient: PatientMetadata
    educator: ScriptEducator
    facts: dict[str, ScriptFact]
    turns: list[ScriptTurn] = Field(min_length=1)
    chart: list[ScriptChart]
    debrief: ScriptDebrief

    @model_validator(mode="after")
    def validate_references(self):
        count = len(self.turns)
        if [t.step for t in self.turns] != list(range(1, count+1)):
            raise ValueError("Script steps must be contiguous and ordered")
        if len({c.id for c in self.chart}) != len(self.chart):
            raise ValueError("Chart IDs must be unique")
        for t in self.turns:
            if any(fid not in self.facts for fid in t.fact_ids):
                raise ValueError("Unknown dialogue fact reference")
            if not any(self.facts[fid].text == t.patient_text for fid in t.fact_ids):
                raise ValueError("A reply needs an exact authored dialogue source")
            if set(t.release_chart_ids) != {c.id for c in self.chart if c.release_step == t.step}:
                raise ValueError("Chart release references must agree")
        if any(c.release_step > count for c in self.chart):
            raise ValueError("Chart references a nonexistent turn")
        return self

class ScriptFixture(StrictModel):
    schema_version: Literal["scripted_clinical_demo_v1"]
    cases: list[ScriptCase] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_case_ids(self):
        if {c.scenario_id for c in self.cases} != {1, 2, 3}:
            raise ValueError("Provide exactly scenarios 1, 2, and 3")
        return self
