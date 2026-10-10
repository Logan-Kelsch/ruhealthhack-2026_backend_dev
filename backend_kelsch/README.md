# Kelsch notebook work

Notebooks 01–07, their Python modules, scripts, tests, source fixtures, and reports live here. This folder is separate from the shared `backend/` application. It imports the existing case schema, disclosure engine, Studio importer, verifier, feedback, and visit contracts; those shared contracts and the three cases remain in their original locations.

From the repository root in the backend's Python environment:

```bash
LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.audit_datasets
LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.prepare_action_data
LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_patient_environment --output backend_kelsch/docs/validation/patient_environment.json
LLM_ENABLED=false PYTHONPATH=backend python -m pytest -q backend_kelsch/tests
```

Notebook dependencies are in `requirements-notebooks.txt`. Open the notebooks from the repository root. The audits use the original `backend/app/data/vhs/` and rubric files as inputs; copied event fixtures are in `app/data/source_fixtures/`. All generated reports and source provenance live under `docs/validation/`. Notebook 02's supervised model gate remains **NOT EVALUABLE**; the external dialogue corpus is still excluded pending provenance and license review.

Notebook 04 runs with `LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_grounding` from the repository root. Its summary and compressed full trace are under `docs/validation/`; export a pending faculty review queue with `--export-review-queue`. Clinical precision/recall stays NOT EVALUABLE until independently reviewed labels are imported.

Notebook 05 runs with `LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_debrief`. Read `notebooks/05_evidence_debrief.ipynb` and `docs/validation/debrief_eval.md`. Its compressed trace preserves anchored claims, provisional review flags and deterministic next-visit branches. Export pending claim checks using `--export-review-queue`; no fixture intent or provisional rubric output is a faculty-approved grade. The Notebook 02 and 04 model/clinical gates remain NOT EVALUABLE.

Notebook 06 runs with `LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_study`. The [proposed protocol](app/data/study_protocol_v1.json), `notebooks/06_prospective_evaluation.ipynb` and `docs/validation/study_protocol.md` describe blinded independent review and an optional consenting learner corpus. Export pending packets with `--export-packets` to a controlled location; review data and learner transcripts must not be committed. The report stores aggregates and source hashes only. No review or learner data is bundled, so clinical, model and learning gates remain NOT EVALUABLE.

Notebook 07 runs with `LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_integration`. The [integration readiness report](docs/validation/integration_readiness.md) and `notebooks/07_integration_readiness.ipynb` check the Notebook 06 source lock, approval metadata, blinded packet quality, review imports, and audit integrity. No independent institutional approval is documented, so prospective learner intake is blocked and all study performance gates remain NOT EVALUABLE. The next step is in `docs/notebook_08_prompt.txt`.

The [V-01 pipeline probe](docs/validation/live_grounding_v1.md) runs with `LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_live_grounding`. Its versioned ledger includes model/usage/cost fields, verifier decisions, actual replies and source-linked fallback across authored turns. `--live` requires configured credentials; no live model call is included in the committed offline report. Notebook 01–07 source-locked reports are preserved.

The [private reviewer workflow](docs/private_reviewer_workflow.md) wraps Notebook 06's 287 locked packets in independent offline reviewer files, source facts, exact-span evidence tools and third-party adjudication. All generated files and submissions must live outside Git. Run `python -m backend_kelsch.scripts.review_workflow prepare --workspace /your/private/new-directory` with `LLM_ENABLED=false PYTHONPATH=backend`; `demo` demonstrates toy transport only. New live candidates are excluded until separately versioned. See [workflow validation](docs/validation/private_reviewer_workflow.md).
