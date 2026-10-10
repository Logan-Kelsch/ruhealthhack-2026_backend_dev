# Notebook partition move

The additions from Notebooks 01–03 are now under `backend_kelsch/`. This includes the copied event fixtures, manifest, vocabulary, modules, scripts, tests, notebook dependencies, notebooks, prompts, and validation reports. Their relative layout is retained: `app/`, `scripts/`, `tests/`, `notebooks/`, and `docs/`. The existing `backend/` application, its case and Studio contracts, and `cases/` are shared inputs, so those original files stay in place.

Validation from the repository root:

- `LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.audit_datasets`: PASS, 0 errors, 8 sources.
- `LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.prepare_action_data`: NOT EVALUABLE supervised model gate, as before.
- `LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_patient_environment --output backend_kelsch/docs/validation/patient_environment.json`: PASS, 10/10 authored checks.
- `LLM_ENABLED=false PYTHONPATH=backend python -m pytest -q backend_kelsch/tests backend/tests --ignore=backend/tests/test_api.py`: 42/42 passed. The seven existing HTTP API tests require CI verification; they previously stalled at the first `TestClient` call in this sandbox.
- All three notebooks ran sequentially in a fresh Python process using an IPython `display` binding and Agg plotting backend: Notebook 01 (12 code cells), Notebook 02 (8), Notebook 03 (8). The three stages retain their source references and gates.

Relocation changes source paths in the regenerated JSON audit report, while the source content hashes are stable. No external Patient–Doctor dialogue content was imported. This move does not unblock the Notebook 02 training gate.
