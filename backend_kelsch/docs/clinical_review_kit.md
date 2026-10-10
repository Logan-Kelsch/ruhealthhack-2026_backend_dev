# Clinical review kit

Read [the clinical critique and steps 3–6 plan](clinical_reasoning_review.md). All clinical proposals await review. This kit adds no patient facts, completed labels, study approval or learner intake. Notebook 06 remains 287 packets. The new 12-candidate supplement has its own lock and never enters that historical denominator.

Run from the repository root with existing dependencies. Choose new directories outside every Git checkout on controlled private storage. Sample preparation reuses the existing workflow; see [review instructions](private_reviewer_workflow.md) for independent ratings, evidence, adjudication and export verification.

```bash
LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.clinical_review_kit report
LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.clinical_review_kit sample --workspace /private/rounds-sample
LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.clinical_review_kit supplement --workspace /private/rounds-supplement
```

The sample chooses the first hash-ordered packet per case/task. Its 12 items test instructions, not performance. Use the original `review_workflow` commands to validate sample submissions. Do not pool overlapping sample ratings as additional observations.

For the supplement, give separate `reviewer_a.html` and `reviewer_b.html` files to independent reviewers and collect private downloads. Each reviewer labels supported/unsupported with a source fact or exact span. Available/disclosed fact lists are scenario constraints, not verifier results. No answer key is embedded. Follow existing coordinator controls for identity, authority, independence, access and retention. Leave unjudgeable semantic items pending.

```bash
LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.clinical_review_kit validate --workspace /private/rounds-supplement --submissions /private/rounds-supplement/submission_a.json /private/rounds-supplement/submission_b.json
LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.clinical_review_kit adjudicate --workspace /private/rounds-supplement --submissions /private/rounds-supplement/submission_a.json /private/rounds-supplement/submission_b.json
```

Only disagreements after two completed independent answers appear for the third reviewer. Add that submission to `validate`, then run `verify-export` with the identical submissions in the same order. Unfinished pairs stay unresolved. Sources, answers, quotes, audit events and supplemental rationales are bound to a receipt; verification recomputes from originals.

Private outputs: `supplement_reviews.jsonl`, `supplement_audit.json`, `supplement_receipt.json` and `supplement_quality.json`. Keep them outside Git. The importer validates transport; it does not calculate accuracy or verify professional identity. Future analysis must match these packet IDs to a locked prediction run and verified authority. Full review coverage alone does not advance clinical gates.

Unit tests generate synthetic submissions in temporary directories. Preparation commands generate empty queues only. No historical case, rubric, notebook report or production API contract changes.
