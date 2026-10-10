"""Translate review documents into validated, source-linked demo fixtures."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app import catalogs
from app.schemas.demo import PatientMetadata, ScriptCase, ScriptFixture
from app.settings import BACKEND_DIR

Text = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]
StudentText = Annotated[Text, StringConstraints(max_length=2000)]
Description = Annotated[Text, StringConstraints(max_length=12000)]
FIXTURE = BACKEND_DIR / "app/data/scripted_clinical_demo_v1.json"
REVIEW_DIR = BACKEND_DIR.parent / "backend_kelsch/docs/scripted_scenarios"
FILENAMES = {1: "01_legionella_final_debrief.json", 2: "02_smoking_cessation_final_debrief.json", 3: "03_cardiac_final_debrief.json"}


class ReviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ReviewFinding(ReviewModel):
    id: Text
    label: Text
    text: Text
    source: Text
    urgent: bool


class ReviewTurn(ReviewModel):
    student: StudentText
    patient: Text
    chart: list[ReviewFinding] = Field(default_factory=list)


class ReviewReflection(ReviewModel):
    rubric_domain: Text
    question: Text


class ReviewDebrief(ReviewModel):
    delivery: Literal["after_dialogue"]
    questions: list[ReviewReflection]


class ReviewSource(ReviewModel):
    title: Text
    url: Text


class ReviewScript(ReviewModel):
    format: Literal["clinical_script_review_v3"]
    scenario_id: int = Field(ge=1, le=3)
    title: Text
    patient: PatientMetadata
    learning_goal: Text
    educator_description: Description
    learner_role: Text
    teaching_notes: list[Text]
    sources: list[ReviewSource]
    dialogue: list[ReviewTurn] = Field(min_length=1, max_length=100)
    debrief: ReviewDebrief

    @model_validator(mode="after")
    def check_domains(self):
        domains = {d["name"] for d in catalogs.rubric()["domains"]}
        for question in self.debrief.questions:
            if question.rubric_domain not in domains:
                raise ValueError(f"Unknown rubric_domain: {question.rubric_domain}; use {sorted(domains)}")
        return self


def to_review(case: ScriptCase) -> ReviewScript:
    domains = {d["id"]: d["name"] for d in catalogs.rubric()["domains"]}
    return ReviewScript.model_validate({
        "format": "clinical_script_review_v3", "scenario_id": case.scenario_id,
        "title": case.title, "patient": case.patient.model_dump(),
        "learning_goal": case.educator.goal,
        "educator_description": case.educator.example_description,
        "learner_role": case.educator.learner_role,
        "teaching_notes": case.educator.teaching_notes, "sources": case.educator.sources,
        "dialogue": [{"student": t.suggested_student_text, "patient": t.patient_text,
                      "chart": [c.model_dump(exclude={"release_step", "provenance"})
                                for c in case.chart if c.release_step == t.step]}
                     for t in case.turns],
        "debrief": {"delivery": "after_dialogue", "questions": [
            {"rubric_domain": domains[q.domain_id], "question": q.question}
            for q in case.debrief.questions]},
    })


def to_case(review: ReviewScript, version: int) -> ScriptCase:
    domains = {d["name"]: d["id"] for d in catalogs.rubric()["domains"]}
    facts, turns, chart = {}, [], []
    for step, turn in enumerate(review.dialogue, 1):
        fact_id = f"{review.scenario_id}.reply.{step}"
        facts[fact_id] = {"text": turn.patient, "provenance": "authored_synthetic_dialogue"}
        turns.append({"step": step, "suggested_student_text": turn.student,
                      "patient_text": turn.patient, "fact_ids": [fact_id],
                      "release_chart_ids": [c.id for c in turn.chart],
                      "simulated_delay_ms": min(2400, 850 + 32 * len(turn.patient.split()))})
        chart.extend({**c.model_dump(), "release_step": step,
                      "provenance": "authored_synthetic_finding"} for c in turn.chart)
    return ScriptCase.model_validate({
        "schema_version": "scripted_clinical_demo_v1", "scenario_id": review.scenario_id,
        "fixture_version": version, "title": review.title, "patient": review.patient.model_dump(),
        "clinical_review_status": "pending", "provenance": "authored_synthetic_script",
        "model_execution": "none_scripted_playback",
        "educator": {"goal": review.learning_goal, "example_description": review.educator_description,
                     "learner_role": review.learner_role, "teaching_notes": review.teaching_notes,
                     "sources": [s.model_dump() for s in review.sources]},
        "facts": facts, "turns": turns, "chart": chart,
        "debrief": {"delivery": "after_dialogue", "questions": [
            {"id": f"{review.scenario_id}.reflection.{n}",
             "domain_id": domains[q.rubric_domain], "question": q.question}
            for n, q in enumerate(review.debrief.questions, 1)]},
    })


def _json(value: BaseModel) -> str:
    return json.dumps(value.model_dump(), indent=2, ensure_ascii=False) + "\n"


def export_scripts(directory: Path = REVIEW_DIR, fixture_path: Path = FIXTURE) -> list[Path]:
    fixture = ScriptFixture.model_validate_json(fixture_path.read_text(encoding="utf-8"))
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for case in fixture.cases:
        path = directory / FILENAMES[case.scenario_id]
        path.write_text(_json(to_review(case)), encoding="utf-8")
        paths.append(path)
    return paths


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def import_scripts(paths: list[Path], fixture_path: Path = FIXTURE, *, check: bool = False) -> dict:
    """Validate the entire batch first, then atomically replace the runtime fixture."""
    if not paths:
        raise ValueError("Provide at least one scenario JSON file")
    original = fixture_path.read_bytes()
    fixture = ScriptFixture.model_validate_json(original)
    replacements = {}
    for path in paths:
        try:
            review = ReviewScript.model_validate(json.loads(
                path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys))
            if review.scenario_id in replacements:
                raise ValueError(f"Scenario {review.scenario_id} supplied more than once")
            replacements[review.scenario_id] = review
        except ValueError as exc:
            raise ValueError(f"{path}: {exc}") from exc
    changed = []
    cases = []
    for current in fixture.cases:
        review = replacements.get(current.scenario_id)
        if review is None:
            cases.append(current)
            continue
        replacement = to_case(review, current.fixture_version)
        if replacement != current:
            replacement = replacement.model_copy(update={"fixture_version": current.fixture_version + 1})
            changed.append(current.scenario_id)
        cases.append(replacement)
    updated = ScriptFixture.model_validate({"schema_version": fixture.schema_version, "cases": cases})
    if changed and not check:
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=fixture_path.parent,
                                             prefix=f".{fixture_path.name}.", delete=False) as output:
                temporary = Path(output.name)
                output.write(_json(updated))
                output.flush()
                os.fsync(output.fileno())
            os.chmod(temporary, fixture_path.stat().st_mode & 0o777)
            if fixture_path.read_bytes() != original:
                raise ValueError("Runtime fixture changed during import; review the latest file and retry")
            os.replace(temporary, fixture_path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return {"mode": "check" if check else "update", "changed_scenarios": changed,
            "fixture": str(fixture_path), "written": bool(changed and not check),
            "versions": {c.scenario_id: c.fixture_version for c in updated.cases}}
