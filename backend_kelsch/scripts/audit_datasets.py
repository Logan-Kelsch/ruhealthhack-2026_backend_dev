"""Audit supplied TwinVerse case, rubric, dialogue, and persona sources.

Run from ``backend/`` with ``python -m backend_kelsch.scripts.audit_datasets``. This is a
provenance and structural audit; it does not validate clinical correctness or
student learning outcomes.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = Path("backend_kelsch/app/data/dataset_manifest.json")


def load_json_objects(path: Path) -> list[dict[str, Any]]:
    """Load either one JSON value or adjacent pretty-printed JSON objects."""
    raw = path.read_text(encoding="utf-8")
    decoder = json.JSONDecoder()
    index = 0
    values: list[dict[str, Any]] = []
    while index < len(raw):
        while index < len(raw) and raw[index].isspace():
            index += 1
        if index == len(raw):
            break
        value, index = decoder.raw_decode(raw, index)
        if not isinstance(value, dict):
            raise ValueError(f"Expected a JSON object in {path} at character {index}")
        values.append(value)
    return values


def _norm(value: str) -> str:
    return " ".join(value.casefold().split())


def _source_entry(root: Path, spec: dict[str, Any]) -> dict[str, Any]:
    entry = {key: value for key, value in spec.items() if key != "path"}
    if not spec.get("path"):
        entry.update({"local_status": "external_not_cached", "record_count": None})
        return entry

    path = root / spec["path"]
    entry["path"] = spec["path"]
    if not path.exists():
        entry.update({"local_status": "missing", "record_count": 0})
        return entry
    if path.is_dir():
        digest = hashlib.sha256()
        for file in sorted(path.glob(spec.get("glob", "*"))):
            if file.is_file():
                digest.update(file.name.encode("utf-8"))
                digest.update(file.read_bytes())
        entry["sha256"] = digest.hexdigest()
    else:
        entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    entry["local_status"] = "present"

    if spec["format"] == "csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            entry["columns"] = reader.fieldnames or []
        entry["record_count"] = len(rows)
        entry["missing_cells"] = sum(
            not str(value or "").strip() for row in rows for value in row.values()
        )
        names = [str(row.get("patient-name", "")).strip() for row in rows]
        ids = [str(row.get("patient-uuid", "")).strip() for row in rows]
        entry["unique_names"] = len({_norm(name) for name in names if name})
        entry["unique_ids"] = len({value for value in ids if value})
        entry["age_parse_failures"] = sum(
            not str(row.get("age", "")).strip().isdigit() for row in rows
        )
        entry["patient_names"] = names
        entry["patient_ages"] = {
            _norm(name): str(row.get("age", "")).strip()
            for name, row in zip(names, rows)
        }
    elif spec["format"] == "concatenated_json_objects":
        records = load_json_objects(path)
        entry["record_count"] = len(records)
        entry["serialization"] = "adjacent JSON objects; not a JSON array or JSONL"
        entry["patient_names"] = [
            str(record.get("patient_overview", {}).get("name", "")).strip()
            for record in records
        ]
        entry["patient_ages"] = {
            _norm(str(record.get("patient_overview", {}).get("name", ""))): str(
                record.get("patient_overview", {}).get("age", "")
            )
            for record in records
        }
        required = {
            "patient_overview", "demographics", "clinical_profile",
            "medication_profile", "nutrition_profile", "psychosocial_profile",
            "information_disclosure", "learning_opportunities", "metadata",
        }
        entry["schema_key_sets"] = Counter(
            "complete" if required.issubset(record) else "incomplete"
            for record in records
        )
        entry["learning_opportunity_count"] = sum(
            len(record.get("learning_opportunities", {}).get("opportunities", []))
            for record in records
        )
        entry["disclosure_fact_count_by_tier"] = dict(
            sum(
                (
                    Counter({tier: len(record.get("information_disclosure", {}).get(key, []))})
                    for record in records
                    for key, tier in (
                        ("initial_information", "initial"),
                        ("discoverable_information", "discoverable"),
                        ("reluctant_information", "reluctant"),
                        ("hidden_information", "hidden"),
                    )
                ),
                Counter(),
            )
        )
    elif spec["format"] == "json":
        value = json.loads(path.read_text(encoding="utf-8"))
        entry["record_count"] = len(value.get("domains", []))
        entry["domain_keys"] = [domain.get("key") for domain in value.get("domains", [])]
        entry["allowed_scores"] = value.get("allowed_scores", [])
        entry["review_trigger_domain_ids"] = value.get("scoring", {}).get(
            "review_trigger_domain_ids", []
        )
        entry["max_total"] = value.get("scoring", {}).get("max_total")
    elif spec["format"] == "json_profile":
        records = [json.loads(file.read_text(encoding="utf-8")) for file in sorted(path.glob(spec["glob"]))]
        entry["record_count"] = len(records)
        entry["files"] = sorted(file.name for file in path.glob(spec["glob"]))
        entry["required_sections_present"] = sum(
            all(key in record for key in (
                "clinician_overview", "demographics", "professional_profile",
                "personality_and_communication", "simulation_behavior",
                "interprofessional_profile", "learning_opportunities", "metadata",
            ))
            for record in records
        )
        entry["learning_opportunity_count"] = sum(
            len(
                record.get("learning_opportunities", [])
                if isinstance(record.get("learning_opportunities"), list)
                else record.get("learning_opportunities", {}).get("opportunities", [])
            ) for record in records
        )
        entry["clinician_names"] = [
            str(record.get("clinician_overview", {}).get("name", "")).strip()
            for record in records
        ]
    elif spec["format"] == "case_directory":
        files = sorted(path.glob("*.json"))
        records = [json.loads(file.read_text(encoding="utf-8")) for file in files]
        entry["record_count"] = len(records)
        entry["files"] = [file.name for file in files]
        entry["case_ids"] = [record.get("case_id") for record in records]
        entry["case_statuses"] = dict(Counter(record.get("status") for record in records))
        entry["fact_count"] = sum(len(record.get("facts", [])) for record in records)
    elif spec["format"] == "docx_rubric":
        with zipfile.ZipFile(path) as archive:
            document = ET.fromstring(archive.read("word/document.xml"))
        text = " ".join(
            node.text or "" for node in document.iter()
            if node.tag.endswith("}t")
        )
        point_values = [int(value) for value in re.findall(r"\((\d+)\s+points?\)", text, re.IGNORECASE)]
        entry["record_count"] = len(point_values)
        entry["point_values"] = point_values
        entry["total_points"] = sum(point_values)
    else:
        entry.update({"local_status": "unsupported_format", "record_count": None})
    return entry


def build_report(root: Path = ROOT) -> dict[str, Any]:
    manifest_path = root / MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources = [_source_entry(root, spec) for spec in manifest["sources"]]
    errors: list[str] = []
    warnings: list[str] = []

    for source in sources:
        if source["local_status"] == "missing":
            errors.append(f"Required local source missing: {source['id']}")
        expected = source.get("expected_records")
        if expected is not None and source["local_status"] == "present":
            if source.get("record_count") != expected:
                errors.append(
                    f"{source['id']} record count is {source.get('record_count')}; expected {expected}"
                )

    by_id = {source["id"]: source for source in sources}
    csv_source = by_id.get("faculty_patient_seed_csv", {})
    vhs_source = by_id.get("vhs_virtual_patient_profiles", {})
    required_csv_columns = {
        "patient-uuid", "patient-name", "age", "background", "gender", "notes",
        "patient-img", "personality", "race/ethinicity", "summary",
    }
    if csv_source.get("local_status") == "present":
        missing_columns = sorted(required_csv_columns - set(csv_source.get("columns", [])))
        if missing_columns:
            errors.append(f"Faculty patient CSV missing columns: {', '.join(missing_columns)}")
        for key, label in (("missing_cells", "blank cells"), ("age_parse_failures", "invalid ages")):
            if csv_source.get(key, 0):
                errors.append(f"Faculty patient CSV has {csv_source[key]} {label}")
        if csv_source.get("unique_names") != csv_source.get("record_count"):
            errors.append("Faculty patient CSV contains duplicate or empty names")
        if csv_source.get("unique_ids") != csv_source.get("record_count"):
            errors.append("Faculty patient CSV contains duplicate or empty IDs")

    if vhs_source.get("local_status") == "present":
        names = vhs_source.get("patient_names", [])
        if any(not name for name in names) or len({_norm(name) for name in names}) != len(names):
            errors.append("VHS profiles contain a missing or duplicate patient name")
        if vhs_source.get("schema_key_sets", {}).get("incomplete", 0):
            errors.append("One or more VHS profiles are missing required sections")
        try:
            from app.studio.vhs_import import import_all

            imported = import_all(root / vhs_source["path"])
            vhs_source["normalized_case_count"] = len(imported)
            vhs_source["normalized_fact_count"] = sum(len(case.facts) for case in imported)
            vhs_source["normalized_lab_count"] = sum(len(case.labs) for case in imported)
            vhs_source["normalized_objective_count"] = sum(len(case.objectives) for case in imported)
            vhs_source["normalized_facts_with_source"] = sum(
                bool(fact.source.ref) for case in imported for fact in case.facts
            )
            if len(imported) != vhs_source.get("record_count"):
                errors.append("VHS profile count differs from deterministic normalized draft-case count")
            if vhs_source["normalized_facts_with_source"] != vhs_source["normalized_fact_count"]:
                errors.append("One or more normalized VHS facts lost their source reference")
        except Exception as exc:  # report the gate failure without leaking profile text
            vhs_source["normalization_error"] = type(exc).__name__
            errors.append(f"VHS profiles could not be normalized by the project importer ({type(exc).__name__})")

    if csv_source.get("local_status") == "present" and vhs_source.get("local_status") == "present":
        csv_names = {_norm(name) for name in csv_source.get("patient_names", [])}
        vhs_names = {_norm(name) for name in vhs_source.get("patient_names", [])}
        unmatched_csv = sorted(csv_names - vhs_names)
        unmatched_vhs = sorted(vhs_names - csv_names)
        age_conflicts = sorted(
            name for name in csv_names & vhs_names
            if csv_source.get("patient_ages", {}).get(name)
            != vhs_source.get("patient_ages", {}).get(name)
        )
        if unmatched_csv or unmatched_vhs or age_conflicts:
            warnings.append("The faculty CSV and VHS profiles contain version differences; review before merging them.")
        cross_source = {
            "matching_name_count": len(csv_names & vhs_names),
            "csv_only_count": len(unmatched_csv),
            "vhs_only_count": len(unmatched_vhs),
            "age_conflict_count": len(age_conflicts),
            "age_conflict_names": age_conflicts,
        }
    else:
        cross_source = {"status": "not_comparable"}

    rubric = by_id.get("shp_encounter_rubric", {})
    if rubric.get("local_status") == "present":
        if rubric.get("record_count") != 7 or rubric.get("max_total") != 28:
            errors.append("SHP rubric does not match the expected seven-domain, 28-point schema")
        if rubric.get("allowed_scores") != [4, 3, 2, 1, "N/A"]:
            errors.append("SHP rubric rating scale differs from the expected 1–4 and N/A scale")
        if rubric.get("review_trigger_domain_ids") != [6, 7]:
            errors.append("SHP rubric review triggers differ from domains 6 and 7")
        warnings.append("The holistic rubric has no subcriterion weights; do not infer a leaf-level score decomposition.")

    specialty_rubric = by_id.get("pediatric_aural_rehabilitation_rubric", {})
    if specialty_rubric.get("local_status") == "present" and specialty_rubric.get("total_points") != 100:
        errors.append("Pediatric specialty rubric point categories do not total 100")
    if specialty_rubric.get("local_status") == "present":
        warnings.append(specialty_rubric.get("review_note", "Specialty rubric needs case mapping."))

    for source in sources:
        if source["local_status"] == "external_not_cached":
            warnings.append(f"External source not cached or structurally audited: {source['id']}")
    warnings.append("No labeled student transcripts or measured learning outcomes are present in these sources.")
    warnings.append("Clinical content and version conflicts require faculty review before cases are published.")

    checks = {
        "all_required_local_sources_present": not any("Required local source missing" in item for item in errors),
        "expected_record_counts_match": not any("record count is" in item for item in errors),
        "patient_seed_csv_valid": not any("CSV" in item for item in errors),
        "vhs_profile_structure_valid": not any("VHS" in item for item in errors),
        "vhs_profiles_normalize_to_case_schema": not any("normalized" in item.lower() or "normalized by" in item for item in errors),
        "rubric_schema_valid": not any("rubric" in item for item in errors),
        "clinical_review_completed": False,
        "student_outcome_data_available": False,
    }
    gate = "PASS" if not errors else "FAIL"
    return {
        "audit_version": 1,
        "stage": "Notebook 01 — dataset audit and provenance",
        "scope": "Structural and provenance audit; not a clinical validation or learning-outcome study.",
        "gate": gate,
        "advance_to": "Notebook 02 — action-data preparation" if gate == "PASS" else None,
        "checks": checks,
        "source_count": len(sources),
        "sources": sources,
        "cross_source_comparison": cross_source,
        "errors": errors,
        "warnings": list(dict.fromkeys(warnings)),
        "next_stage_constraints": [
            "External dialogue contents and redistribution terms are not present in the repository; acquire or replace them before supervised dialogue-model training.",
            "Use source profiles and rubric descriptors as schema and scenario material, not as student labels.",
            "Keep faculty review as the publication gate for clinical facts and conflicting profile versions.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=Path("backend_kelsch/docs/validation/dataset_audit.json"))
    args = parser.parse_args()
    root = args.repo_root.resolve()
    report = build_report(root)
    output = args.output if args.output.is_absolute() else root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Dataset audit: {report['gate']} ({len(report['errors'])} errors, {len(report['warnings'])} review notes)")
    print(f"Report: {output}")
    for source in report["sources"]:
        print(f"- {source['id']}: {source['local_status']}; records={source.get('record_count')}")
    for error in report["errors"]:
        print(f"ERROR: {error}")
    for warning in report["warnings"]:
        print(f"REVIEW: {warning}")
    return 0 if report["gate"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
