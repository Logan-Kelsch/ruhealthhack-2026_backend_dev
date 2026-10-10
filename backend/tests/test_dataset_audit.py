"""Meaningful integrity checks for the supplied-data audit gate."""
from pathlib import Path

from scripts.audit_datasets import build_report, load_json_objects

ROOT = Path(__file__).resolve().parents[2]


def test_all_local_inputs_match_the_audited_schema_and_expected_counts():
    report = build_report(ROOT)
    assert report["gate"] == "PASS", report["errors"]
    assert report["checks"]["all_required_local_sources_present"]
    assert report["checks"]["expected_record_counts_match"]
    assert report["checks"]["patient_seed_csv_valid"]
    assert report["checks"]["vhs_profile_structure_valid"]
    assert report["checks"]["rubric_schema_valid"]

    sources = {source["id"]: source for source in report["sources"]}
    assert sources["faculty_patient_seed_csv"]["record_count"] == 8
    assert sources["vhs_virtual_patient_profiles"]["record_count"] == 8
    assert sources["vhs_virtual_patient_profiles"]["normalized_case_count"] == 8
    assert (
        sources["vhs_virtual_patient_profiles"]["normalized_facts_with_source"]
        == sources["vhs_virtual_patient_profiles"]["normalized_fact_count"]
    )
    assert sources["shp_encounter_rubric"]["record_count"] == 7
    assert sources["pediatric_aural_rehabilitation_rubric"]["record_count"] == 4
    assert sources["pediatric_aural_rehabilitation_rubric"]["total_points"] == 100
    assert sources["sample_clinician_personas"]["record_count"] == 5
    assert sources["golden_cases"]["record_count"] == 3
    assert report["cross_source_comparison"]["matching_name_count"] == 8


def test_rubric_and_outcome_limitations_remain_visible():
    report = build_report(ROOT)
    notes = " ".join(report["warnings"])
    assert "no subcriterion weights" in notes
    assert "No labeled student transcripts" in notes
    assert report["checks"]["clinical_review_completed"] is False
    assert report["checks"]["student_outcome_data_available"] is False
    assert report["advance_to"] == "Notebook 02 — action-data preparation"


def test_adjacent_json_objects_are_parsed_as_eight_profiles():
    path = ROOT / "backend/app/data/vhs/virtual-patient-profiles-sample.json"
    profiles = load_json_objects(path)
    assert len(profiles) == 8
    assert all("patient_overview" in profile for profile in profiles)


def test_vhs_importer_maps_every_profile_to_a_draft_case():
    from app.studio.vhs_import import import_all

    cases = import_all(ROOT / "backend/app/data/vhs/virtual-patient-profiles-sample.json")
    assert len(cases) == 8
    assert all(case.facts for case in cases)
    assert all(fact.status == "draft" and fact.source.ref for case in cases for fact in case.facts)
