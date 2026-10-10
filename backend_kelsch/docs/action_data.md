# Notebook 02: action-data preparation (P-01, F-01, F-03)

Run from the repository root: `LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.prepare_action_data`.
Install `requirements-notebooks.txt` to execute the notebook and optional baseline.
The production intent classifier, case schema, API and vocabularies are unchanged.
Research labels live in `action_annotation_vocab.json`; student action IDs mirror the
existing actions vocabulary. They describe behavior, not rubric ratings.

## Import and annotation contract

Use `--corpus corpus.json --annotations reviewed.jsonl` to evaluate reviewed data.
The corpus envelope requires `license_verified`, `synthetic_provenance_verified`,
`provenance_ref`, and `conversations`. These flags record a human import review;
they do not replace checking original source evidence. Do not import real records.
Each conversation needs a unique ID, source path, SHA-256, patient ID when known,
script family ID, and turns with unique IDs, speaker and verbatim text.
`parse_dialogue` supports explicit Doctor/Patient/Student/Clinician prefixes and
multiline turns. Preambles are quarantined. It has not been validated on upstream
Postzeun files: those contents were not downloaded because permission is unresolved.
Never use viewer rows or blank lines as independent conversations.

Each JSONL annotation has `annotation_id`, `conversation_id`, `turn_id`, `speaker`,
`start`, `end`, `span`, `namespace`, `labels`, `rubric_mapping`, `review_status`,
`reviewer_type`, `reviewer_id` (pseudonymous), and `reviewed_at`.
Offsets are zero-based, end-exclusive within turn text. A reviewed negative uses
`other`; an empty label set is not a reviewed negative. General `dialogue_act`
annotations have no rubric mapping. `student_skill` requires student speech and
may reference SHP domain IDs 1–7; these references do not create scores.
Pending, rejected and machine-only approvals cannot train the baseline.

Patient, script-family and duplicate-text links form connected groups; the seeded
split assigns groups to train/validation/test. Missing patient identifiers limit
patient-level guarantees; reviewers must supply them. Fit TF-IDF and multi-label
logistic regression only on training spans. A tiny or single-class split returns
NOT EVALUABLE. The validation split is reserved, without hyperparameter tuning here.
Confusion matrices are per label in order `[[TN, FP], [FN, TP]]`.

`evaluate(..., predictions=...)` can compare logged prompted-LLM predictions on the
same held-out IDs. Each entry requires labels, model ID and prompt version. Produce
predictions without access to reviewed labels, using temperature 0 and structured
output. No API calls or paid inference run automatically in this stage.

## Progression gates

Preparation: tests pass, provenance retained, offsets validate, namespace and review
rules enforced, patient/family/duplicate groups do not cross splits.
Model: proposed macro-F1 >= 0.85 and recall >= 0.95 for reviewer-designated critical
actions, with sufficient held-out positive examples; report class support and
uncertainty before accepting either threshold. These are engineering targets.
No critical-label set or reviewed labels exists yet, so these gates are NOT EVALUABLE.
LLM comparison also remains NOT EVALUABLE without logged predictions.

Notebook 03 may build deterministic controlled simulation with the existing intent
classifier. It must preserve the blocked trained-extraction gate. Authored visit
branches remain deterministic per AGENTS.md; no probabilistic visit outcomes added.
Learning efficiency and MCPT belong to later randomized learner evaluation.
