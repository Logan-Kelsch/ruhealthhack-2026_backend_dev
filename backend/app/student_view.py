"""Projects saved cases and encounters into the fields a student is allowed to see.

The case document and the encounter state hold hidden facts, trust, and branch
outcomes. These functions copy only the released briefing, chart, and transcript.
"""

from typing import Literal

from app import catalogs
from app.encounter.visit import resolve_visit
from app.models.tables import EncounterRow, TurnRow
from app.schemas.case import Case
from app.schemas.student import (
    DocumentationField,
    DocumentationTemplate,
    PublicBriefing,
    PublicCase,
    PublicChartEntry,
    PublicDoorwayVital,
    PublicEncounter,
    PublicNotice,
    PublicPatient,
    PublicSource,
    PublicVisitSummary,
    TranscriptEntry,
    TurnResult,
    WordTimestamp,
)


def public_case(case: Case, visit_id: str | None = None) -> PublicCase:
    """Briefing for one visit. Later-visit changes apply; unreleased branches do not."""
    # No visit id means the first visit, which is what the case list shows.
    selected = visit_id or (case.visits[0].id if case.visits else None)
    resolved = resolve_visit(case, selected, None) if selected else case
    briefing = resolved.briefing
    doorway: list[PublicDoorwayVital] = []
    if briefing.show_doorway_vitals:
        for vital in resolved.vitals:
            doorway.append(
                PublicDoorwayVital(
                    key=vital.key,
                    label=vital.label,
                    value=vital.value,
                    unit=vital.unit,
                    source=PublicSource(kind=vital.source.kind, ref=vital.source.ref),
                )
            )
    profile = case.profile
    return PublicCase(
        case_id=case.case_id,
        version=case.version,
        title=case.title,
        golden=case.golden,
        patient=PublicPatient(
            name=profile.name,
            age=profile.age,
            sex=profile.sex,
            pronouns=profile.pronouns,
            portrait=profile.portrait,
            speaker=profile.speaker,
        ),
        briefing=PublicBriefing(
            setting=briefing.setting,
            reason_for_visit=briefing.reason_for_visit,
            goal=briefing.goal,
            student_role=briefing.student_role,
            show_doorway_vitals=briefing.show_doorway_vitals,
        ),
        # Visit labels come from the authored list. Branch contents stay off the card.
        visits=[PublicVisitSummary(id=visit.id, label=visit.label, day=visit.day) for visit in case.visits],
        doorway_vitals=doorway,
    )


def _source_of(case: Case, entry: PublicChartEntry) -> PublicSource | None:
    """Cite the authored item behind a released row. A missing match stays uncited."""
    item = None
    if entry.kind == "vital":
        item = next((vital for vital in case.vitals if vital.key == entry.ref), None)
    elif entry.kind == "exam":
        item = next((exam for exam in case.exam if exam.maneuver == entry.ref), None)
    elif entry.kind == "lab":
        item = next((lab for lab in case.labs if lab.key == entry.ref), None)
    elif entry.kind == "artifact":
        item = next((artifact for artifact in case.artifacts if artifact.id == entry.ref), None)
    elif entry.kind == "medication":
        item = next((med for med in case.medications if med.name == entry.ref), None)
    elif entry.kind == "diagnosis":
        item = next((diagnosis for diagnosis in case.diagnoses if diagnosis.name == entry.ref), None)
    elif entry.kind == "allergy":
        item = next((allergy for allergy in case.allergies if allergy.substance == entry.ref), None)
    elif entry.source_fact or entry.kind == "fact":
        item = case.fact(entry.source_fact or entry.ref)
    if item is None:
        return None
    return PublicSource(kind=item.source.kind, ref=item.source.ref)


def _body_of(case: Case, entry: PublicChartEntry) -> str | None:
    """Copy a document body only when that document is already in the released chart."""
    if entry.kind != "artifact":
        return None
    artifact = next((item for item in case.artifacts if item.id == entry.ref), None)
    return artifact.body if artifact else None


def chart_entries(case: Case, raw_items: list[dict]) -> list[PublicChartEntry]:
    """Turn saved chart rows into the public chart, keeping each row's fact citation."""
    entries: list[PublicChartEntry] = []
    for raw in raw_items:
        entry = PublicChartEntry.model_validate(raw)
        entry.source = _source_of(case, entry)
        entry.body = _body_of(case, entry)
        entries.append(entry)
    return entries


def transcript_entries(turns: list[TurnRow]) -> list[TranscriptEntry]:
    """Keep the saved order. The newest turn is marked so a refresh knows which line is last."""
    if not turns:
        return []
    last = turns[-1].idx
    return [
        TranscriptEntry(
            turn=turn.idx,
            student_text=turn.student_text,
            reply_text=turn.reply_text,
            student_start_ms=turn.student_start_ms,
            student_end_ms=turn.student_end_ms,
            words=[WordTimestamp.model_validate(word) for word in (turn.student_words or [])],
            mode=_reply_mode(str((turn.verifier or {}).get("mode") or "template")),
            is_last=turn.idx == last,
        )
        for turn in turns
    ]


def _patient(case: Case) -> PublicPatient:
    """The name and portrait on the encounter. Personality and voice ids stay off this object."""
    profile = case.profile
    return PublicPatient(
        name=profile.name,
        age=profile.age,
        sex=profile.sex,
        pronouns=profile.pronouns,
        portrait=profile.portrait,
        speaker=profile.speaker,
    )


def _briefing(case: Case) -> PublicBriefing:
    """The goal and role for this saved visit. Hidden visit rules are not copied."""
    briefing = case.briefing
    return PublicBriefing(
        setting=briefing.setting,
        reason_for_visit=briefing.reason_for_visit,
        goal=briefing.goal,
        student_role=briefing.student_role,
        show_doorway_vitals=briefing.show_doorway_vitals,
    )


def documentation_template_for(case: Case) -> DocumentationTemplate:
    """Copy the case's saved template so the student can dictate without opening Studio."""
    raw = catalogs.documentation_templates()[case.documentation_template]
    return DocumentationTemplate(
        id=case.documentation_template,
        label=str(raw["label"]),
        fields=[
            DocumentationField(id=str(field["id"]), label=str(field["label"]), hint=str(field["hint"]))
            for field in raw["fields"]
        ],
    )


def _saved_note(raw: dict | None) -> dict[str, str] | None:
    """The submitted note, as text. No note yet stays null rather than an empty form."""
    if not raw:
        return None
    return {str(key): str(value) for key, value in raw.items()}


def public_encounter(enc: EncounterRow, turns: list[TurnRow]) -> PublicEncounter:
    """Build the recovery view from the saved encounter. This does not create another one."""
    case = Case.model_validate(enc.visit_doc)
    visit = case.visit(enc.visit_id)
    lines = transcript_entries(turns)
    return PublicEncounter(
        encounter_id=enc.id,
        case_id=enc.case_id,
        case_version=enc.case_version,
        visit_id=enc.visit_id,
        visit_label=visit.label if visit else enc.visit_id,
        has_next_visit=bool(case.visits and case.visits[-1].id != enc.visit_id),
        previous_encounter_id=enc.previous_encounter_id,
        patient=_patient(case),
        briefing=_briefing(case),
        chart=chart_entries(case, list(enc.state.get("chart") or [])),
        transcript=lines,
        started_at=enc.started_at,
        ended_at=enc.ended_at,
        last_turn=lines[-1].turn if lines else None,
        status=_encounter_status(enc.status),
        documentation_template=documentation_template_for(case),
        saved_documentation=_saved_note(enc.documentation),
    )


def public_turn(
    case: Case,
    *,
    turn: int,
    reply_text: str,
    audio_tags: list[str],
    chart_releases: list[dict],
    exam_results: list[dict],
    notices: list[dict],
    mode: str,
    latency_ms: dict,
) -> TurnResult:
    """The reply the student hears, plus the rows that turn released. Engine internals stay out."""
    reply_mode = _reply_mode(mode)
    visible = [PublicNotice.model_validate(notice) for notice in notices]
    # Offline and failed checks use the template. The student sees that notice instead of a silent change.
    if reply_mode == "template" and not any(notice.kind == "fallback" for notice in visible):
        visible.append(PublicNotice(kind="fallback", text="Simplified responses"))
    return TurnResult(
        turn=turn,
        reply_text=reply_text,
        speaker=case.profile.speaker or case.profile.name,
        audio_tags=list(audio_tags),
        chart_releases=chart_entries(case, chart_releases),
        exam_results=chart_entries(case, exam_results),
        notices=visible,
        mode=reply_mode,
        # The stored step name "engine" is the disclosure pass. Students see the duration, not that name.
        latency_ms={("disclosure" if key == "engine" else key): int(value) for key, value in latency_ms.items()},
    )


def _encounter_status(value: str) -> Literal["active", "ended", "complete"]:
    """Map the stored status onto the public contract. An unknown value is a storage error."""
    if value == "active":
        return "active"
    if value == "ended":
        return "ended"
    if value == "complete":
        return "complete"
    raise ValueError(f"unknown encounter status {value}")


def _reply_mode(value: str) -> Literal["template", "llm"]:
    """The student can see whether the reply was phrased from the template or the model."""
    if value == "llm":
        return "llm"
    return "template"
