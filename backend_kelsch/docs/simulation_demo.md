# Backend demonstration through Monte Carlo permutation testing

V-01–V-06, S-01–S-06, E-01, F-01–F-05, L-03–L-04, P-01. This is an explicit **simulation-only development mode**. It completes an offline backend rehearsal and statistical analysis without waiting for unavailable people. Clinical approval, independent human evidence, learner authorization, and learning-effect gates remain **NOT EVALUABLE**. The real-evidence importers are unchanged.

## Run once

From the repository root, activate the backend Python 3.12+ environment with its normal dependencies and `pytest`. Install `scikit-learn>=1.5` if it is not already installed; this is an existing notebook dependency, used here for the trained action baseline. No new production dependency is added. Then run:

```bash
LLM_ENABLED=false PYTHONPATH=backend python -m scripts.run_simulation_demo \
  --mode simulation --output ~/rounds-private/simulation-v1
```

The directory must be new and outside every Git checkout. The command creates synthetic inputs, freezes plans and predictions, executes the actual offline engine and HTTP API, compares provisional references, and runs all five MCPT scenarios. It exits nonzero on incomplete integration or failed mechanical checks. Missing evidence is never counted as an evidence pass. No AWS, external dataset, institutional decision, real learner, or patient input is required. The command disables Bedrock, remote lookup, and paid TTS during the HTTP rehearsal and restores process configuration afterward. Run it as a standalone process, rather than inside a running API worker.

The seed is `2026`, with `4,999` permutation draws and `1,999` learner bootstrap draws per scenario. Override these with `--seed`, `--draws`, and `--bootstrap-draws`. Different draw counts change numerical precision. The test suite uses fewer draws for speed.

## Outputs

All these paths are relative to the chosen output directory:

| File | Purpose |
|---|---|
| `simulation_report.html` | Shareable pitch report with explicit simulation labels |
| `simulation_report.md` | The same aggregate report as Markdown |
| `simulation_report.json` | Full metrics, denominators, intervals, seeds, provenance, limitations, and replacement map |
| `source_manifest.json` | SHA-256 of backend/evaluation code, cases, prompts, vocabulary and supporting data; relevant package versions |
| `inputs/manifest.json` | Versioned SHA-256 receipts for all four synthetic input files |
| `frozen_plan.json` | Per-scenario outcome, learner aggregation, tail, draw counts and seeds, written before comparison |
| `frozen_action_predictions.json` | Held-out keyword and trained predictions written before metric calculation |
| `action_split_assignments.json` | Linked synthetic patient/family/duplicate group assignments |
| `review_stage/<kind>/PRIVATE_predictions.json` | Frozen baseline outputs for each review batch |
| `review_stage/<kind>/synthetic_a.json`, `synthetic_b.json`, `synthetic_adjudicator.json` | Provisional correlated reference sources, explicitly synthetic |
| `review_stage/<kind>/reference_simulated_v1.json` | Replaceable reference configuration, retaining provenance and input hashes |
| `review_stage/<kind>/review_report.json` | Transport, disagreement, scoring, and N/A comparison details |
| `review_stage/clinical_and_difficulty_decisions.md` | Current-source clinical/preset decision worksheet; no approval asserted |
| `api_interactions.json`, `simulation_api.sqlite` | Actual request statuses and disposable database; local engineering artifacts |

Only the aggregate report snapshots and check record are committed under `backend_kelsch/docs/validation/simulation_demo.*` and `simulation_checks.json`. Raw reviewer/learner files, API interactions and databases stay outside Git. Stable aggregate reports omit random database IDs and wall-clock times. A repeat with the same inputs, code, seed and package versions produces the same aggregate digest; receipts detect file drift but cannot prove human blinding or authority.

## How the substitutions are generated

| Component | Construction and source | What the resulting numbers establish |
|---|---|---|
| Case and preset decisions | Assume the current three authored case files for the rehearsal, pin their digests, and apply estimated disclosure threshold offsets `-2/0/+2`. All clinical content stays unchanged. | Engine ordering and replay on authored scripts; no clinical accuracy or complete preset validation |
| Exact-span actions | Code-authored phrases from the closed research action vocabulary, with explicit negation controls and neutral unique context. Thirty synthetic patient/family groups, two encounters each, fifteen whole-sentence spans per encounter: 900 spans. | A reproducible annotation/training/comparison path on easy templates; no actual learner generalization |
| Semantic and disclosure references | Nine constructor-known injected semantic examples; disclosure expectations echo 189 engine turns. Existing mechanical checks make the semantic predictions. | Known injected examples expose the mechanical check's limitations; disclosure echo agreement is not independent accuracy |
| Feedback and rubric references | Regenerate 41 feedback claims and 42 domain items from six authored transcripts; start from frozen baseline answers and perturb selected rows. Two synthetic source IDs and a tie breaker choosing A exercise transport and disagreement. Every eleventh domain item becomes N/A. | Validation of import/comparison mechanics; agreement is partly constructed, with no independent rating or faculty reliability claim |
| Next-case/progression decisions | Versioned simulation-only score thresholds with exact learner-role matching, N/A abstention and a review flag for domain 6/7 score 1. Five fixed score controls exercise routing. | Provisional policy mechanics, not validated difficulty or clinical progression. Current cases have distinct roles, so no new compatible case is available; the policy reports repeat-current-case fallback. |
| Baseline/follow-up learner outcomes | Twenty-four invented learners, balanced randomized arm labels, baseline scores 2, background changes `-1/0/+1` matched by arm, assumed feedback shifts, clipping to 1–4. Disjoint arithmetic fixture IDs represent phases. | MCPT arithmetic and missingness/repeat handling under invented effects. Outcomes are not grades from the backend encounters, and the fixture IDs are not validated transfer cases. |
| Study protocol and authorization | Freeze a proposed synthetic analysis plan, while the existing trusted authorization route remains closed to observed intake. | A reproducible analysis sequence, with no simulated consent, approval or institutional signature |

No data was downloaded. No new clinical facts, clinical decision rule or person identity was fabricated. Existing source-backed auto-fill is exercised by the API. In the disposable database only, the script sets the schema's authoring statuses to demonstrate publication; the report calls this code-driven simulation, never clinical approval. It rewrites the intake's default faculty-source attribution as a simulation rule before publishing the test case.

The TF-IDF/logistic baseline trains on the training split only. Patient, family and exact duplicate links cannot cross splits; validation groups remain unused. Test groups are held out by synthetic identities, but train/test deliberately share the phrase bank. Both classifiers can score perfectly on this easy corpus; this is not evidence for a pitch claim about clinical action extraction. The trained model classifies supplied whole-sentence spans, rather than discovering arbitrary boundaries. The keyword path additionally reports exact-span TP/FP/FN and critical-action support/recall. No prompted LLM comparison is claimed.

The difficulty probe executes 27 case × script-level × preset traces and deterministic replays, then checks four authored follow-up branches. Threshold offsets are estimated probe parameters, not complete approved difficulty presets. The simulated progression adapter does not modify production dashboard recommendations, persist learner decisions, or switch between health-professions roles.

## MCPT design and controls

The reused learner-level pipeline averages repeated numeric domain ratings within phase, retains domains numeric in both phases, and computes one mean follow-up-minus-baseline change per learner. The effect is feedback-arm mean change minus standard-arm mean change. Whole learner outcomes are shuffled while retaining arm sizes, so encounter counts never increase the analysis sample size. N/A is not zero and is never imputed. Assigned-arm roster counts, scored counts, missing-phase/no-common-domain counts and encounter denominators remain visible.

The two-sided tail includes ties at absolute differences at least as large as observed. The estimate is `(extreme + 1)/(draws + 1)`. A within-arm learner bootstrap provides a descriptive percentile 95% effect interval; a Wilson interval describes permutation-tail Monte Carlo uncertainty. These are different uncertainties. Plans, seed, draw counts and input hashes are frozen before comparison. The scenarios are mathematical controls, not five clinical endpoints or a power/false-positive study. Available-case comparison under missingness does not establish complete intention-to-treat inference.

| Scenario | Assumption/control |
|---|---|
| `no_effect` | Shift zero; matched arm background makes effect exactly zero and p-value one. This is an exact test control. |
| `beneficial_effect` | Assume +1 feedback shift; observed arithmetic effect follows that assumption. |
| `adverse_effect` | Assume −1 feedback shift; score clipping makes the resulting difference asymmetric. A non-small p-value does not remove the assumed harm. |
| `missingness` | Omit selected follow-up phases; one learner has all domains N/A. Denominators shrink visibly without imputation. |
| `repeated_encounters` | Add unequal numbers of identical-score encounters. The result matches the beneficial scenario because each learner keeps weight one. |

This plan supports unstratified parallel assignment only. A real study with stratification, clusters, crossover or different endpoints requires a new approved analysis plan. The current public MCPT command rejects observed envelopes even if they contain an `approved` or consent flag.

## Exactly where to replace simulations

| Component | Simulation switch point | Genuine replacement route |
|---|---|---|
| Action corpus | `<output>/inputs/action_corpus.json` | Keep independently labeled conversations/annotations private; run `backend_kelsch.scripts.prepare_action_data --corpus ... --annotations ...` under [the grouped action-data contract](action_data.md). Human approval fields stay required there. |
| A/B reviews and disagreements | `<output>/review_stage/{action,claim,domain,semantic,release}/reference_simulated_v1.json` | Save fresh independent submissions separately. Use `eval_development configure` to create a **new** `reference_human_v2.json` with actual provenance/IDs and pinned predictions, then `eval_development evaluate --config ... --output ...`. The source-locked `eval_next_review report --workspace <output>/review_stage --kind <kind> --config ...` also supports action/claim/domain. For those browser pages and import commands, see [next review stage](next_review_stage.md). The semantic/release additions provide JSON task files for separately prepared independent submissions. Prepare a fresh batch if sources change. Never expose private predictions or synthetic answers to independent reviewers. |
| Case/preset decisions | `<output>/inputs/case_preset_decisions.json` and `<output>/review_stage/clinical_and_difficulty_decisions.md` | Obtain qualified decisions in a separately versioned worksheet, then version accepted case corrections in `cases/*.json` and generate a new locked batch. Replace the simulation progression adapter after a real policy is agreed. Human judgments do not go into the simulation-only envelope. |
| Rubric/scoring and feedback claims | Domain/claim reference configs above | Independently rate original transcripts and claim evidence; preserve N/A and exact spans, resolve disagreements with a distinct source. Metadata alone cannot certify qualifications. |
| Authorization/protocol | `<output>/frozen_plan.json` | Use the existing `backend_kelsch.app.integration.quality` trusted authorization workflow and [integration readiness](validation/integration_readiness.md). Synthetic analysis does not unlock observed intake. |
| Genuine learner outcomes | `<output>/inputs/learner_scenarios.json` contains replaceable roster/encounter schema examples | Keep a genuine authorized roster and blinded scores in the controlled study workflow. Reuse learner aggregation/statistics only through its approved adapter/plan; this demo rejects observed inputs. Obtain held-out clinical follow-up cases, genuine encounters and consent first. |

For a new **synthetic** input version, copy the four inputs into a new private directory, change the documented generation assumptions, and regenerate `manifest.json` (keep the original receipts). Its format is `{"version":"simulation_demo_v1","files":{"action_corpus.json":"<sha256>", ...}}`; all four exact filenames must be covered. Then run into another new directory:

```bash
LLM_ENABLED=false PYTHONPATH=backend python -m scripts.run_simulation_demo \
  --mode simulation --inputs-dir ~/rounds-private/simulation-v1/inputs \
  --output ~/rounds-private/simulation-repeat-v1
```

Reusing the original input directory as above needs no manifest editing. Changed cases require new case digest assumptions and a fresh review lock. The explicit synthetic-only adapter prevents replacement from silently relabeling simulations as humans; the established genuine routes remain available separately.

## What still blocks a live product demonstration

- Live Bedrock access/model permissions and a fresh current-model run remain unevaluated. Run `backend_kelsch.scripts.eval_live_grounding --live` separately with configured credentials and freeze its outputs before comparing. This simulation never turns a failed model call into a live pass.
- Microphone, streaming recognition, playback, echo/barge-in and voice first-audio latency require the integrated frontend rehearsal. Text HTTP calls are the authorized test interface; no student text UI is added. TTS fallback is explicitly unavailable/mocked.
- PostgreSQL/cloud deployment and service cost/latency measurements remain unevaluated. The API checks use isolated SQLite; no estimated prices or voice timings are invented.
- Qualified case/safety/disclosure and full preset decisions, independent action/rubric/claim references, and authorized genuine learner data are still needed for evidence claims. All are listed by the generated replacement map; none blocks running this engineering demonstration.

Read the [aggregate Markdown](validation/simulation_demo.md), [JSON](validation/simulation_demo.json), [HTML](validation/simulation_demo.html), and [check record](validation/simulation_checks.json). The old notebook and live-run reports retain their original scope and results.
