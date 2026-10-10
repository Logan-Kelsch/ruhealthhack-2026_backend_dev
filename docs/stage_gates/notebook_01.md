# Notebook 01 gate: dataset audit and provenance

## Purpose

Record which supplied sources are present, how they are structured, how they relate to the current cases and rubric, and what each source can support. This gate checks data integrity. It does not certify clinical content, assessment validity, or learning improvement.

## PASS criteria

- The local source groups have the expected counts: 8 faculty CSV rows, 8 VHS profiles, 7 SHP rubric domains, 4 pediatric rubric categories totaling 100 points, 5 clinician profiles, and 3 project cases.
- Required CSV columns are present; patient names and IDs are unique; ages parse; cells are populated.
- All 8 adjacent JSON profile objects parse, have the required sections, and have unique names.
- The current deterministic VHS importer produces 8 draft case objects and retains source references on every imported fact.
- The rubric retains 1–4/N/A, seven domains, max 28, and review triggers for domains 6 and 7.
- The local case JSON files parse and their count matches the manifest.
- The generated JSON audit report is reproducible and contains source hashes.

## Review notes that do not fail this gate

- External Patient–Doctor dialogue and pathology links are listed but not cached. Verify access terms and provenance before downloading.
- Patient versions may differ. Keep them separate until faculty review.
- Faculty review is still required before publication.
- No reviewed student transcript labels or measured learning outcomes are available in these sources. They cannot be reported as model or learning ground truth.

## Commands

From `backend/`:

```bash
python -m scripts.audit_datasets
python -m pytest tests/test_dataset_audit.py -q
```

For the explanatory notebook, install `backend/requirements-notebooks.txt`, then open and run `notebooks/01_dataset_audit.ipynb` from the repository root.

## Advancement

PASS allows work on Notebook 02's action-data preparation. Supervised model training remains blocked until its action labels are human-reviewed or a suitable licensed, annotated source is obtained. A PASS is not clinical review.
