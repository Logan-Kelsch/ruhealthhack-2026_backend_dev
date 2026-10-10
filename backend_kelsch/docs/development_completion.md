# Replaceable development reference and completion checks

V-01–V-06, P-01, F-01, F-03, L-03–L-04. Development may continue with a provisional reference. AI responses retain AI provenance; they are not converted to faculty reviews. This workflow never changes Notebook 06–08 clinical, authorization, or learner gates.

## Where to put reviews

Keep the coordinator package and submissions in a private directory **outside every Git checkout**, for example `~/rounds-private/development/`. The single switch point is **`reference_v1.json`**, passed with `--config`. It pins each input's SHA-256 and retains reviewer provenance. The original answer files are never edited.

The coordinator directory supplies `review_manifest.json`, `blinded_tasks.json`, and, for live comparison, `PRIVATE_packet_mapping.json` plus `live_trace.json.gz`. The 90-task live batch has its own lock; do not pool it with Notebook 06's historical 287 tasks. Browser envelopes and JSONL rows are supported. Task IDs, frozen views, case digests, exact citations, timestamps, reviewer IDs, labels, and disagreement coverage are checked before analysis.

From the repository root:

```bash
LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_development configure \
  --workspace ~/rounds-private/development \
  --a ~/rounds-private/development/answers.jsonl \
  --b ~/rounds-private/development/answers_b.jsonl \
  --adjudicator ~/rounds-private/development/adjudication.jsonl \
  --a-description 'Qwen 3.8; user-reported AI model' \
  --b-description 'GPT 6 Luna; user-reported AI model' \
  --adjudicator-description 'ChatGPT AI adjudication' \
  --trace ~/rounds-private/development/live_trace.json.gz \
  --output ~/rounds-private/development/reference_v1.json

LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_development evaluate \
  --config ~/rounds-private/development/reference_v1.json \
  --output ~/rounds-private/development/development_report.json \
  --export-reference ~/rounds-private/development/resolved_reference.json
```

Both full submissions are required for resolution. Disagreements remain pending until a distinct third source resolves them. Adjudication may contain only disputed tasks. Canonical development exports are deliberately different from faculty-import rows: they contain no fabricated `faculty` role or `approved` status.

### Replace with human responses later

Keep version 1. Save fresh blinded human submissions separately, then run `configure` with a **new** output, such as `reference_human_v2.json`, and new `--a`, `--b`, and optional `--adjudicator` paths. Add `--a-kind human --b-kind human`, distinct pseudonymous `--a-id`/`--b-id`, and descriptions. If the new browser files contain reviewer IDs, config IDs must match them. Specify the adjudicator's actual type and ID as well.

Use the same `evaluate --config` command with version 2. No backend code change is needed. A declared human type is metadata, not proof of qualifications, independence, case approval, or institutional authority. Gate closure still requires the trusted review/authorization route. Never expose this AI reference to reviewers before their blinded submissions are locked.

If the source cases, prompts, task wording, or protocol change, prepare a **new batch**. Do not rehash altered files to pretend they are the old batch. Availability/disclosure constraints and semantic source support are separate dimensions; the six blocked, case-backed candidate replies are excluded from semantic-judge accuracy.

## What can run before more human input

| Step | Implemented development work | Still needs new evidence |
|---|---|---|
| Semantic grounding | Source-locked A/B intake, third-source resolution, replaceable canonical labels, delivered wording and candidate-judge comparisons | Independent qualified review; fresh live trace after the phraser change |
| Case approval | Case versions/digests and unchanged clinical content across probe presets are checked | Qualified case, disclosure, and safety decisions; no new clinical facts invented |
| Action extraction | Keyword versus saved classifier agreement on authored utterances; eight critical-action regression probes; exact-span action-prediction comparison adapter | Reviewed held-out action spans and sufficient critical positives; no trained-model accuracy from fixtures |
| Feedback/scoring | Existing claim-anchor audit, N/A preservation, per-domain paired agreement, generic claim/rubric prediction comparison | Reviewed claims and double-rated rubric scores with enough independent transcripts |
| Difficulty/progression | 27 scripted case/level/preset runs; content preservation, discovery ordering, deterministic replay, existing next-visit branch checks | Approved full presets, validated next-case routing, actual learner difficulty observations |
| Backend operation | Source hashes, model/prompt provenance, fallback/call/latency/cost-state report, offline and HTTP regression tests | Integrated voice first-audio latency; pricing and live post-change verification |
| Learner study | Synthetic roster/encounter schema, missingness and N/A handling, assigned-arm consistency, held-out case checks | Independently verified authorization, consent, genuine outcomes, approved frozen protocol |
| MCPT | Seeded learner-unit Monte Carlo permutation test, effect estimate, learner bootstrap interval, simulation uncertainty | Approved observed cohort; synthetic results are arithmetic demonstrations |

`--predictions /private/predictions.json` on `configure` enables the generic comparator for semantic, claim, release, domain, or action tasks in a frozen coordinator batch. Each prediction has `packet_id`, `answer`, `model_id`, and `prompt_version`; answers use the same schema as the review. Prediction IDs must exactly cover the resolved tasks. Task kinds are never inferred from semantic reviews: the current 90 rows cannot create action annotations or rubric ratings. Numeric domain scores require transcript spans; N/A remains N/A. Exact-span action comparisons report critical recall without treating persona speech as student performance.

For trained action extraction, retain the existing [grouped action-data workflow](action_data.md). Patient/family/duplicate links must stay within one split. These development probes are not a training set, and saved-file hashes do not prove blinded prediction generation. Do not present their F1 as held-out accuracy.

## Fixes motivated by the checks

The old template asserted “I already told you” based on the engine disclosure ledger. That ledger records availability, even when a phraser spoke only one of several available facts. The template now restates approved content without asserting dialogue history. Phraser version 3 explicitly distinguishes availability from spoken history and requires recent dialogue evidence for the assertion. This does not change clinical facts, releases, thresholds, or the verifier.

The keyword fallback now suppresses narrowly recognized explicit negation before three critical action phrases. It searches later matches too, preserving an affirmative clause after a refusal. Tags remain low-confidence. This is not a general negation parser or a change to the Bedrock classifier; uncertain, hypothetical, reported, and more complex language still require reviewed evaluation.

## MCPT mechanics and limits

The fixed `development_mcpt_v1` plan in `app/study/permutation.py` implements an unstratified parallel design with feedback and standard arms. Average repeated domain scores within each learner/phase, retain common numeric domains between baseline and follow-up, and calculate one mean change per learner. No N/A imputation. Follow-up cases cannot overlap that learner's baseline cases. Keep all assigned learners in roster counts; missing outcomes are reported by arm. The numerical comparison is available-case within assigned arms, not a claim of complete intention-to-treat inference.

Shuffle whole learner outcomes while retaining arm sizes. The statistic is feedback mean change minus standard mean change; the two-sided tail counts absolute differences at least as large, including ties. The randomized estimate uses `(extreme + 1)/(draws + 1)`; a learner bootstrap supplies a descriptive percentile effect interval. A Wilson interval describes Monte Carlo tail uncertainty, not the effect uncertainty. Seed, draws, input hash, plan hash, and implementation hash are recorded. There is one primary outcome; additional endpoints require a prespecified multiplicity policy. Stratified, blocked, crossover, or cluster randomization requires a different plan, not this shuffle.

Method reference: [SciPy permutation-test documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html). The implementation uses the Python standard library and adds no dependency. Its absolute-statistic two-sided convention is explicit; do not assume it equals every library's doubled-one-tail convention.

```bash
LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_development demo
LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_development mcpt \
  --input ~/rounds-private/development/synthetic_learners.json \
  --output ~/rounds-private/development/synthetic_mcpt.json
```

The input requires `source_kind: synthetic_fixture`, `design: unstratified_parallel`, a generation description, a unique assigned-arm roster, and encounters with IDs, learner IDs, baseline/followup phases, case IDs, and all seven scores (1–4 or N/A). See `demo_fixture()` for the executable example. Observed learner envelopes are rejected even when they declare approval. No environment flag bypasses the existing authorization gate.

## Current evidence

[Offline report](validation/development_completion.json) and [saved-live-run comparison](validation/development_live_reference.json) are generated separately. The latter evaluates the provided phraser-v2 trace against the AI-only reference: 90 resolved labels, 86 paired agreements, 62/63 delivered replies supported, and 18/18 mechanically permitted candidate-judge decisions agreeing. Nine mechanically blocked candidates are excluded from judge comparison. The delivered failure is kept as FAIL rather than erased after the fix.

The live run used 235 successful model calls, 10/63 template fallbacks, median text-pipeline latency 1,563 ms and nearest-rank p90 2,565 ms. Cost remains unknown and voice latency unevaluable. These are saved authored-probe observations, not new Bedrock calls, learner outcomes, or clinically validated accuracy. The classifier fixture comparison has no critical-action positives in that live script; the separate eight-probe set tests critical-action mechanics without meeting the proposed held-out support floor.

Run a fresh `eval_live_grounding --live` after merging to test phraser version 3, then freeze a new review batch if reviewing new replies. Notebook 09 reproduces offline mechanics; private review and learner files must stay out of Git.

Validation: [check record](validation/development_checks.json) records 153 passing backend/notebook tests, including all seven HTTP API tests. Notebook 09's three code cells passed sequential plain-Python execution. Native Jupyter kernel execution was blocked by this runtime's TCP and IPC socket restrictions. No new Bedrock call or integrated voice timing was performed.
