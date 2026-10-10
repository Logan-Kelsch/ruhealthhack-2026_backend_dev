# Kelsch notebook work

Open [Notebook 10: clinical presenter demonstration](notebooks/10_clinical_presenter_demo.ipynb) for a narrated, visual walkthrough from Patient Studio through MCPT. It executes the offline backend and offers an explicit local-`.env` live Bedrock section with successful/failed attempt accounting. See the [presenter guide](docs/presenter_notebook.md) and its offline HTML preview; genuine-evidence gates remain separate.

The [simulation demonstration through MCPT](docs/simulation_demo.md) supplies documented, versioned synthetic replacements for unavailable inputs, exercises the actual offline HTTP backend in disposable SQLite, freezes predictions, and runs five learner-level statistical controls. Run `LLM_ENABLED=false PYTHONPATH=backend python -m scripts.run_simulation_demo --mode simulation --output ~/rounds-private/simulation-v1`. It creates shareable HTML/Markdown/JSON reports and an exact human replacement map. Simulation readiness stays separate from clinical approval, human evidence, live services and learner-study authorization.

The [next review stage](docs/next_review_stage.md) freezes current action, feedback-claim and seven-domain rubric work items with private baseline predictions, separate offline A/B pages, disagreement adjudication, and a clinical/difficulty decision worksheet. Run `LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_next_review prepare --workspace ~/rounds-private/next-review-v1`. It advances development to independent human review without treating authored encounters as learner evidence.

The [development completion workflow](docs/development_completion.md) and Notebook 09 accept a replaceable private review reference, compare saved live outputs, check action/difficulty/feedback mechanics, and exercise learner-unit MCPT with synthetic fixtures. `reference_v1.json` is the input switch point; create a new config version when replacing AI responses with human submissions. Human, clinical, and learner gates stay separate from development checks. Run `LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_development demo` for offline checks.

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

The [V-01 pipeline probe](docs/validation/live_grounding_v1.md) runs with `LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_live_grounding`. Its versioned ledger includes model/usage/cost fields, verifier decisions, actual replies and source-linked fallback across authored turns. `--live` requires configured credentials; no live model call is included in the committed offline report. Notebook 01–07 source-locked reports are preserved. See [Bedrock JSON formatting](docs/bedrock_json_formatting.md) for strict response validation, one formatting retry, and accounting for both attempts.

The [private reviewer workflow](docs/private_reviewer_workflow.md) wraps Notebook 06's 287 locked packets in independent offline reviewer files, source facts, exact-span evidence tools and third-party adjudication. All generated files and submissions must live outside Git. Run `python -m backend_kelsch.scripts.review_workflow prepare --workspace /your/private/new-directory` with `LLM_ENABLED=false PYTHONPATH=backend`; `demo` demonstrates toy transport only. New live candidates are excluded until separately versioned. See [workflow validation](docs/validation/private_reviewer_workflow.md).

The [clinical review kit](docs/clinical_review_kit.md) adds a 12-packet instruction rehearsal and separately locked 12-candidate semantic supplement. Run `LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.clinical_review_kit report`. The [AI-authored clinical critique and steps 3–6 plan](docs/clinical_reasoning_review.md) are for human review; no clinical approval, learner evidence or new patient facts are supplied.


## Three-case scripted presenter rehearsal

Notebook `notebooks/11_scripted_clinical_demo.ipynb` runs educator text structuring, fixed conversations for pneumonia/tobacco/cardiac examples, progressive findings, and indirect debrief questions. It includes interactive presenter controls and a complete replay. See [setup, endpoints, and replacement guide](docs/scripted_clinical_demo.md). The opt-in `/api/demo` routes are separate from graded encounters and never call Bedrock or assign scores.
