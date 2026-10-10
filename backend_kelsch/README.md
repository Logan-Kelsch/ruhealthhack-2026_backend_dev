# Kelsch notebook work

Notebooks 01–03, their Python modules, scripts, tests, source fixtures, and reports live here. This folder is separate from the shared `backend/` application. It imports the existing case schema, disclosure engine, Studio importer, and verifier; those shared contracts and the three cases remain in their original locations.

From the repository root in the backend's Python environment:

```bash
LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.audit_datasets
LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.prepare_action_data
LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_patient_environment --output backend_kelsch/docs/validation/patient_environment.json
LLM_ENABLED=false PYTHONPATH=backend python -m pytest -q backend_kelsch/tests
```

Notebook dependencies are in `requirements-notebooks.txt`. Open the notebooks from the repository root. The audits use the original `backend/app/data/vhs/` and rubric files as inputs; copied event fixtures are in `app/data/source_fixtures/`. All generated reports and source provenance live under `docs/validation/`. Notebook 02's supervised model gate remains **NOT EVALUABLE**; the external dialogue corpus is still excluded pending provenance and license review.

Notebook 04 runs with `LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_grounding` from the repository root. Its summary and compressed full trace are under `docs/validation/`; export a pending faculty review queue with `--export-review-queue`. Clinical precision/recall stays NOT EVALUABLE until independently reviewed labels are imported.
