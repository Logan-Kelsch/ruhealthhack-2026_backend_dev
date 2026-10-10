# Notebook 03 validation — controlled patient environment

Date: 2026-10-10. Feature: E-07 progressive disclosure, E-12 trust, PRD V-01/V-02/V-04 probes.

## Sources and method

The offline script `backend/scripts/eval_patient_environment.py` loads only authored synthetic `cases/walter_greene.json` and `cases/alina_reyes.json`. The machine-readable [report](patient_environment.json) records their SHA-256 hashes. Each disclosed or repeated fact in the trace carries its case fact ID and `source` fields. The comparison uses exact authored `Intent` tags and fallback patient text from the existing `engine`, `trust`, `phraser`, and `verifier` contracts. It does not infer student actions with a model, use external dialogue, or score students.

Run from the repository root:

```bash
LLM_ENABLED=false PYTHONPATH=backend python -m scripts.eval_patient_environment --output docs/validation/patient_environment.json
LLM_ENABLED=false PYTHONPATH=backend python -m pytest -q backend/tests
```

The notebook `notebooks/03_patient_environment.ipynb` executes eight code cells and renders two figures (trust/disclosure and comparative discovery). A fresh Python process with a shared notebook namespace and the Agg plot backend completed all code cells.

## Measured results

The script passed **10/10 authored checks**: guarded facts withheld at trust 0; reluctant fact unlocked at trust 3 while hidden stayed withheld; memory without duplicate disclosure; evidence spans on trust events; ordered illustrative preset discovery counts (straightforward 5, typical 4, difficult 3); exact deterministic replay across three presets; hidden student fact lookup denied; stray numeric claim and unauthorized citation rejected; Alina prerequisite and nonpenalized suicide screening; source metadata on all cited facts. Counts refer to one authored script, not populations or students.

The five new tests independently check the case copy, versioned replay mismatch, unknown role and draft fact denial, Alina transitions, and invalid preset input. The new tests plus encounter tests passed **18/18**. The backend suite excluding HTTP API tests passed **42/42**. The full 49-test suite could not complete here: it stalled at `test_api.py::test_student_case_list_hides_facts` and was stopped after 20 seconds; this appears to be the local HTTP test client under this sandbox, and is not counted as a pass. The Notebook 02 report previously recorded 44/44 before this run. The seven HTTP API tests still need a normal CI run.

## Progression criteria

| Gate | PASS | FAIL | Current |
|---|---|---|---|
| Controlled E-07/E-12 probe | All 10 expected checks pass; zero premature guarded release or unauthorized lookup; replay digest matches | Any check fails | **PASS** (10/10) |
| Trained action extractor from Notebook 02 | Reviewed student encounter labels; whole-conversation split; macro-F1 ≥ 0.85 and critical recall ≥ 0.95 | Evaluated metrics below target | **NOT EVALUABLE**: no reviewed labels; external source lacks verified license/provenance |
| Semantic grounding | Independently reviewed challenge claims and zero delivered unsupported clinical claims | Measured unsupported delivery | **NOT EVALUABLE**: deterministic checks cannot assess arbitrary prose; no LLM judge run |
| Difficulty calibration (V-04) | Novice, competent and expert students across three faculty-reviewed presets; report discovery effect and test when sample permits | Evaluated vectors fail target or safety rule | **NOT EVALUABLE**: one authored script and threshold-only probe vectors |
| Learning effect | Designed and measured student study | Measured negative outcome under agreed rule | **NOT EVALUABLE** |

**Advancement:** Notebook 04 may investigate deterministic test students and grounding. Model-based action extraction, clinical semantic accuracy, calibrated difficulty, and learning claims stay blocked until their data and review gates pass.

## Limits

The source fields on the authored facts are `kind: faculty` with no cited external clinical references; source identity comes from the case hash and fact ID. Case facts and their approval status are existing project contracts, not human-reviewed evaluation annotations. The probe threshold offsets (−2, 0, +2) change only tier thresholds; per-fact `min_trust` still overrides. They do not implement full S-11 presets. `student_view` tests a local wrapper, not production endpoint authorization. Replay covers engine state and deterministic template replies with fixed intents; it does not promise stable speech model output. The current repeat answer can choose an earlier disclosed fact when multiple facts share a topic; a specific memory response quality evaluation is pending.

## Next notebook prompt

Implement Notebook 04: scripted novice, competent and expert test students across the three authored cases. Define independently faculty-reviewed expected fact releases and a semantic verifier challenge set. Measure fact-level disclosure precision/recall, zero premature guarded releases, delivered grounding and fallback use. Report denominators and failure examples. Compare difficulty only after full preset vectors are faculty approved and sample size supports inference. Preserve Notebook 02's NOT EVALUABLE trained-extraction gate until licensed, reviewed conversation-level split labels exist.
