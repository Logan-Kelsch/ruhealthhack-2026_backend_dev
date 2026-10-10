# [Product name]: simulation demonstration through MCPT

**SIMULATION ONLY — authored references and assumed learner effects. No clinical approval or learning-effect evidence.**

Demo readiness: **PASS**. Human evidence readiness: **NOT EVALUABLE**.

## Executed backend and evaluation

| Component | Execution/result |
|---|---|
| Studio → new patient → debrief → follow-up | OFFLINE HTTP EXECUTED; PASS |
| HTTP requests | 29 |
| Difficulty/replay | 27 runs, 27 matching replays |
| Provisional progression | PASS; five score/N/A/safety controls; simulation adapter only |
| Synthetic action corpus | 30 synthetic patient groups; {'train': 540, 'validation': 180, 'test': 180} spans by split |
| Trained whole-sentence action macro-F1 | 1.0000; synthetic template labels |
| Keyword action macro-F1 | 1.0000; synthetic template labels |

These action scores measure template generalization, not real learner performance or arbitrary span extraction. Predictions were frozen before comparison; training used training labels only. Validation groups remain unused.

## Simulated review transport

| Kind | Tasks | A/B agreements | Disagreements | Baseline differences |
|---|---:|---:|---:|---:|
| action | 23 | 23 | 0 | 0 |
| claim | 41 | 36 | 5 | 3 |
| domain | 42 | 38 | 4 | 6 |
| release | 189 | 180 | 9 | 3 |
| semantic | 9 | 9 | 0 | 4 |

References are seeded correlated simulations. Disclosure labels echo engine output. Action/claim/domain references perturb baseline outputs; their agreement is partly constructed. Constructor-known semantic probes are not a live Bedrock evaluation.

## Monte Carlo permutation testing (MCPT)

| Synthetic scenario | Scored feedback / standard | Effect | 95% learner-bootstrap interval | p-value |
|---|---:|---:|---|---:|
| no_effect | 12 / 12 | 0.0000 | -0.6667 to 0.6667 | 1.0000 |
| beneficial_effect | 12 / 12 | 1.0000 | 0.3333 to 1.6667 | 0.0208 |
| adverse_effect | 12 / 12 | -0.6667 | -1.2500 to -0.1667 | 0.0552 |
| missingness | 10 / 9 | 0.9889 | 0.2444 to 1.7444 | 0.0414 |
| repeated_encounters | 12 / 12 | 1.0000 | 0.3333 to 1.6667 | 0.0208 |

| Scenario | Assigned feedback / standard | Encounters | Excluded learners by arm | Seed | Permutations / bootstraps | Monte Carlo tail 95% interval |
|---|---:|---:|---|---:|---:|---|
| no_effect | 12 / 12 | 48 | {'feedback': 0, 'standard': 0} | 2026 | 4999 / 1999 | 0.9992 to 1.0000 |
| beneficial_effect | 12 / 12 | 48 | {'feedback': 0, 'standard': 0} | 2026 | 4999 / 1999 | 0.0170 to 0.0249 |
| adverse_effect | 12 / 12 | 48 | {'feedback': 0, 'standard': 0} | 2026 | 4999 / 1999 | 0.0490 to 0.0617 |
| missingness | 12 / 12 | 44 | {'feedback': 2, 'standard': 3} | 2026 | 4999 / 1999 | 0.0360 to 0.0471 |
| repeated_encounters | 12 / 12 | 80 | {'feedback': 0, 'standard': 0} | 2026 | 4999 / 1999 | 0.0170 to 0.0249 |

One outcome per learner; repeats are averaged within each phase/domain. N/A is not imputed. Assigned-arm missingness remains in roster counts. These p-values describe invented mathematical outcomes. The exact null is a test control, not an estimated false-positive rate. Each JSON result includes seeds, draw counts, input/plan hashes, bootstrap and Monte Carlo tail uncertainty.

## Human replacement map

| Component | Replace this simulation | Human route |
|---|---|---|
| action spans | `inputs/action_corpus.json` | backend_kelsch.scripts.prepare_action_data --corpus --annotations; reviewed grouped corpus |
| semantic/disclosure/feedback/rubric reviews | `inputs/review_policy.json; review_stage/<kind>/synthetic_*.json` | eval_development configure/evaluate with actual submissions; eval_next_review report for action/claim/domain |
| clinical cases, full presets and progression | `inputs/case_preset_decisions.json` | Qualified decisions, versioned case corrections and a fresh frozen review batch |
| protocol, authorization and consent | `frozen_plan.json (proposed synthetic analysis only)` | Existing backend_kelsch.app.integration.quality trusted authorization workflow |
| learner outcomes | `inputs/learner_scenarios.json` | Authorized roster and genuine blinded baseline/follow-up scores under a frozen supported analysis plan |

## Operational limits

- Live Bedrock access and current-model evaluation were not executed in this offline command.
- Microphone, speech recognition, playback, echo/barge-in and voice first-audio latency need the integrated frontend rehearsal.
- Postgres/cloud deployment and full service costs are unevaluated; no guessed latency or cost numbers are presented.
- Case content, safety/disclosure, full presets and next-case routing still need qualified decisions.
- Independent labels and authorized genuine learner outcomes must replace simulations before a learning-effect claim.

Source/input receipts: `source_manifest.json`, `inputs/manifest.json`, `frozen_plan.json`, `frozen_action_predictions.json`, per-batch `PRIVATE_predictions.json` and `reference_simulated_v1.json`. Raw API interactions and the disposable SQLite database are local artifacts; no real patient or learner data.
