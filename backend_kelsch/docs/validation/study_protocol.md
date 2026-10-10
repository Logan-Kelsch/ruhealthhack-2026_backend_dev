# Notebook 06 — prospective evaluation and faculty review

Date: 2026-10-10. Run from the repository root:

```bash
LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_study
LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_study --export-packets /tmp/notebook06_pending.jsonl
```

The [JSON report](study_protocol.json) contains source hashes, packet/review denominators and gates. The [protocol](../../app/data/study_protocol_v1.json) is **proposed**, pending faculty approval and an institutional ethics determination. The source lock covers the protocol, rubric, vocabulary, three case files, shared feedback/encounter contracts, Notebook 02 action preparation, Notebook 06 code, and Notebook 01–05 reports and traces. A change invalidates old packet IDs. An externally timestamped registration and institutional approval are separate actions.

## Blinded packets

| Packet | Pending | Faculty task | Hidden system field |
|---|---:|---|---|
| Fact release | 189 | Newly expected approved fact IDs at each turn | Actual releases, scripted level and intent tags |
| Semantic reply | 15 | Supported/unsupported candidate reply | Verifier and judge verdicts |
| Debrief claim | 41 | Support of cited claim | Aggregate verdict and faculty grade |
| Rubric domain | 42 (6 encounters × 7) | Score 1–4 with exact evidence, or N/A with reason | Provisional rule score |
| Prospective action spans | 0 | Exact student spans and rubric mapping | Classifier predictions and scripted intents |

Each packet has an opaque ID, case SHA/version and protocol lock. Reviewers should inspect the approved case and judge release sequences from the start; previous student utterances do not themselves establish previous releases. The packet intentionally omits engine answers. Study staff must provide approved case facts and rules in a controlled reviewer view. The source-key mapping remains in the analysis process.

Two distinct faculty reviewers submit approved JSONL rows with `packet_id`, `protocol_lock`, `case_sha256`, `case_version`, pseudonymous `reviewer_id`, `reviewer_role: faculty`, timestamp with time zone, `phase: independent`, and typed `answer`. Agreement resolves a packet; disagreement requires a third distinct reviewer with `phase: adjudication`. No answer is inferred from system output. Release answers have `expected_fact_ids` (possibly empty). Semantic/claim answers have `expected_supported`. Domain answers have `score` 1–4 and exact transcript `evidence` (`turn`, `speaker`, `start`, `end`, `quote`) or `N/A` with `na_reason`. Action answers have `annotations` containing exact `start`, `end`, `span`, `labels`, and `rubric_mapping`; a reviewed negative is explicit `other`. General dialogue acts remain a different namespace.

Use `--reviews private_reviews.jsonl --audit-log /tmp/notebook06_audit.jsonl` with private source files. The importer rejects unknown/stale packets, unapproved/duplicate raters, invalid spans, unapproved fact IDs, incomplete adjudication and wrong hashes. The audit chain records packet IDs, timestamp, answer/reviewer hashes and predecessor hash; public reports have no raw review text. Metadata cannot establish professional identity or actual independence. The study coordinator must verify those and retain source records privately. Partial reviews yield denominators, not performance estimates.

## Learner pilot, privacy and analysis

The optional private `--corpus` requires the current protocol lock, synthetic-case-only origin, documented consent/ethics references, deidentification, no real patient data, pseudonymous learner/assignment/consent IDs, locked case version/hash, and a canonical transcript digest. This is a validation of submitted metadata, not proof that consent occurred. Keep linkage and raw audio in institution-controlled storage and redact incidental identifiers before annotation. Obtain the institution's determination before recruitment. [U.S. Office for Human Research Protections guidance](https://www.hhs.gov/ohrp/coded-private-information-or-biospecimens-used-research.html) cautions that coded information alone does not settle oversight status.

The proposed future study randomly assigns learners to feedback or standard practice; blinded faculty score baseline and held-out follow-up cases. The learner is the analysis unit. Primary outcome: between-arm difference in each learner's mean baseline-to-follow-up change per common scored rubric domain; N/A is excluded, never set to zero. Missing visits/scores are counted by arm. A descriptive two-sided 95% normal interval is available only with at least two reviewed changes per arm; efficacy needs protocol approval and adequate randomized sampling. V-04 additionally needs faculty-approved full difficulty presets. Whole-patient, family and duplicate-text links must stay in one train/validation/test split. The three current case patients cannot provide a credible trained extractor split.

The PRD's 15–20 hand-scored transcripts are a *feasibility* scale. This proposal uses 20 distinct double-rated encounters per domain before reporting quadratic weighted Cohen kappa with encounter-cluster bootstrap intervals (N/A separately counted). A future efficacy planning calculation, assuming standardized difference 0.5, two-sided α=0.05, 80% power and 15% loss, yields about 63 learners per arm before loss or 74 after. This is an assumption for faculty/statistics review, not recruitment authorization. About 100 independent binary judgments gives a worst-case normal 95% half-width near 0.10; correlated facts/turns reduce precision. Wilson fact-level intervals are descriptive.

## Progression to Notebook 07

| Gate | PASS criterion | FAIL criterion | Current |
|---|---|---|---|
| Source lock, blindness, import | Correct source hashes and hidden fields; invalid reviews/spans/leaks rejected; moved tests/notebooks run | Any invariant fails | **PASS** |
| Trained action extraction | Complete independent span review, whole-patient test split, every training label has positives and negatives, ≥10 held-out positives per critical action, macro-F1 ≥0.85 and critical recall ≥0.95 | Sufficient reviewed study below target | **NOT EVALUABLE** |
| Prompted comparison | Logged model ID/prompt version predictions on exactly the reviewed held-out annotation IDs, alongside baseline | Invalid coverage or metadata | **NOT EVALUABLE** |
| Clinical disclosure | All 189 turns double-reviewed/adjudicated, zero false or missed releases, denominators and intervals reported | Fully evaluated mismatch | **NOT EVALUABLE** |
| Semantic grounding | All 15 candidates independently reviewed; every mechanically permitted reply judged; zero unsupported permitted | Fully evaluated unsupported permit | **NOT EVALUABLE** |
| Debrief support | All 41 claims reviewed/adjudicated and supported | Fully reviewed unsupported claim | **NOT EVALUABLE** |
| Grader agreement measurement | ≥20 distinct double-rated encounters per domain; N/A count, per-domain and overall kappa/interval | Invalid scoring evidence or insufficient complete study | **NOT EVALUABLE** |
| Difficulty and learning | Approved full presets and V-04 sample; separately approved and adequately sampled randomized learner protocol with blinded outcomes | Fully evaluated prespecified failure | **NOT EVALUABLE** |

PASS for agreement **measurement** says the statistic is available, not that agreement is good; no acceptable kappa threshold has been approved. No human reviews, learner transcripts, judge calls or sampled learners were imported. Authored fixture inputs and patient profiles are never student-performance truth. Source-linked failure examples will appear only after genuine reviews. The seven existing HTTP API tests collected successfully, but the run timed out after 25 seconds with zero completed tests in this sandbox; they are not counted as passing.

Validation: Notebook 06 tests **8/8** and moved/shared non-HTTP suite **62/62** passed. Notebook 01–06 code cells ran in fresh Python processes (12, 8, 8, 8, 6, 6). An ordinary Jupyter kernel could not start here because socket creation was denied.
