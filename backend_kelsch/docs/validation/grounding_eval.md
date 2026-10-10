# Notebook 04 — scripted test students and grounding probes

Date: 2026-10-10. Source files: `cases/{walter_greene,alina_reyes,eli_brooks}.json`; `PRD.md` §§9.1, 9.3, 9.4, 15; Notebook 02–03 reports. The [machine-readable summary](grounding_eval.json) and [compressed turn/challenge ledger](grounding_traces.json.gz) preserve each case SHA-256/version, the actual student utterance, explicit intent tags, disclosures, trust evidence, verifier decision, template status, and fact source metadata. These are authored synthetic fixtures, not observed student actions or faculty-approved expected releases. Every turn records `intent_origin: authored_fixture`; the underlying `Intent.source: keywords` is a compatibility value from the shared schema, not a classifier evaluation.

From repository root:

```bash
LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_grounding
LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_grounding --export-review-queue /tmp/notebook04_pending.jsonl
LLM_ENABLED=false PYTHONPATH=backend python -m pytest -q backend_kelsch/tests backend/tests --ignore=backend/tests/test_api.py
```

`--reviews /path/to/reviewed.jsonl` imports independent faculty reviews. `--llm-judge` is opt-in only with configured Bedrock access. It logs each judge's model ID, prompt version and verdict; an unavailable judge fails closed for evaluation. Neither the script nor notebook invokes a model by default.

## Denominators and observations

| Measure | Observation | Interpretation |
|---|---:|---|
| Authored scripts | 27 (3 cases × 3 levels × 3 threshold vectors) | Profiles are authored behaviors, not learner samples. |
| Turns | 189 | Explicit intents, never trained predictions. |
| Engine replay | 27/27 | Fixed intent/state trace equality. |
| Fact/access invariant violations | 0/189 turns | Authored mechanics check; 23 guarded releases and 42 guarded withholds examined. |
| Delivered fact ID source coverage | 142/142 cited IDs | Source and permission bookkeeping, not sentence-level clinical grounding. |
| Deterministic mechanical blocks | 9/9 attempted | Three numeric inventions, three unauthorized citations and three premature guarded replies. The latter two use the same unauthorized-citation rule. |
| Deterministic allowed exact case replies | 3/3 | Exact approved `say` text. |
| Unsupported prose | 3/3 passes deterministic checks | Unverified candidate replies; **none was delivered**. Requires semantic review/judge. |
| Offline template use | 189/189 | Deliberate offline execution. Live pipeline fallback rate: NOT EVALUABLE. |
| Faculty-reviewed release turns | 0/189 | Fact-level precision/recall: null. |
| Faculty-reviewed semantic candidates | 0/15 | Semantic precision/recall: null. |

The full traces include case and fact sources, allowed IDs and withheld reasons. Challenge failures show why the deterministic verifier catches numeric/citation errors yet cannot certify unsupported prose. No failed challenge was delivered to a student. The case source fields often say `kind: faculty` without an external clinical citation; fact IDs and case hashes link to the authored file, not independent clinical validation.

## Review/import contract

Export an unreviewed JSONL queue. A reviewer must set `review_status: approved`, `reviewer_role: faculty`, a pseudonymous `reviewer_id` distinct from `author_id`, `reviewed_at`, and either `expected_fact_ids` for each release turn or `expected_supported` for each challenge. Keep `case_sha256` and `case_version` unchanged. `load_reviews` rejects duplicate IDs, unknown IDs, wrong hashes/versions, invalid fact IDs, machine/pending reviews and missing reviewer metadata. These fields establish a review *workflow*, not proof that review happened; confirm the reviewer and independence outside the script. Partial coverage does not produce aggregate clinical metrics. Reviewers should assess the case and question without copying actual disclosures as expected labels.

For disclosure accuracy, report TP, FP, FN and precision/recall on every reviewed turn only when all 189 are approved. For semantic grounding, require all 15 approved challenge labels and a logged judge verdict for every reply the deterministic checks permit. An LLM judge alone is not truth; compare its outputs with independent labels. No labels were fabricated for this report.

## Difficulty observations

The three Notebook 03 threshold-only vectors are tested with the same scripts. The paired straightforward-minus-difficult discovery counts for Walter are 0, 1 and 3 for novice, competent and expert; for Alina and Eli they are 0 in this authored set because explicit per-fact `min_trust` overrides preserve those releases. This is a diagnostic of current case configuration, not V-04 calibration. There is no random student sample, full faculty-reviewed preset, effect significance test, or learning claim.

## Progression gate

| Gate | PASS rule | FAIL rule | Current |
|---|---|---|---|
| Offline mechanics | No invariant violation on 189 turns, 27/27 replay and all 12 mechanically decidable challenges meet their fixture rules | Any miss | **PASS** |
| V-02 disclosure accuracy | All 189 expected releases independently reviewed; zero false or missed fact releases, with TP/FP/FN reported | Fully evaluated mismatch | **NOT EVALUABLE** |
| V-01 semantic grounding | All 15 candidates independently labeled, every permitted reply judged, zero unsupported permitted claims | Fully evaluated unsupported permitted claim | **NOT EVALUABLE** |
| V-04 difficulty | Faculty approves complete S-11 vectors; student sample and analysis demonstrate agreed discovery order without safety regression | Evaluated safety/order failure | **NOT EVALUABLE** |
| Notebook 02 trained extractor | Reviewed grouped split reaches macro-F1 and critical recall targets | Evaluated below target | **NOT EVALUABLE** |
| Student learning | Prospective outcome study under agreed metric | Evaluated failure | **NOT EVALUABLE** |

Notebook 05 may continue with the authored debrief/feedback evidence path, keeping model-based grading and learner outcomes blocked until faculty-reviewed transcript labels exist. The relocated plus shared non-HTTP suite passed **47/47** (`--ignore=backend/tests/test_api.py`). All four notebooks ran in a fresh process with IPython display and Agg plotting (12, 8, 8, 8 code cells). The seven existing HTTP API tests previously stalled at `TestClient` in this sandbox and require a normal CI run; they are not counted as passing.
