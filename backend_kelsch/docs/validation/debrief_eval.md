# Notebook 05 — evidence-linked debrief probes

Date: 2026-10-10. Run `LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_debrief` from the repository root. The [JSON summary](debrief_eval.json) and [compressed claim/transcript/branch ledger](debrief_traces.json.gz) contain source hashes and case versions for each run. Source contracts: `AGENTS.md`, `context.md` §14, `PRD.md` F-01–F-10 and L-03–L-04, `backend/app/feedback/`, `backend/app/encounter/visit.py`, `backend/app/data/rubric_shp_v1.json`, and the three `cases/*.json` files. Notebook 01–04 validation reports remain the preceding gates.

The six scenarios comprise Walter's authored, absent and low-confidence sequences; Alina's authored safety sequence; and Eli's authored and conflicting-antibiotic sequences. These are fixture intents, not classified or observed student acts. Every positive action and trust event has an exact student quote and character offsets. Disclosures and key-finding omissions cite an exact authored case fact ID, file SHA-256, version and source metadata. Unsupported-number documentation candidates cite the exact note span and are checked against the complete disclosed fact/chart ledger. A single transcript quote cannot prove absence across an encounter; these are pending heuristic candidates. Rubric suggestions include linked quotes and `faculty_score: null`; provisional grades computed inside the shared fallback are discarded. No submitted faculty score is present.

| Check | Observation | Scope |
|---|---:|---|
| Authored cases / scenarios | 3 / 6 | Fixed fixtures, no learner sample |
| Claims / audited evidence references | 41 / 45 | All 45 offsets or source IDs checked; 41 claims have at least one reference |
| Next-visit full state replay | 4/4 | Walter and Alina v2; Eli has no v2 |
| Scenarios with branch uncertainty | 2/6 | Walter low confidence; Eli conflicting actions |
| Domain 6/7 safety-review flags | 5 | Pending flags; not scores |
| Documentation discrepancy candidates | 11 | Numeric fallback and lexical missing-key heuristic |
| Faculty reviewed claims | 0/41 | Feedback accuracy null |
| Empty-signal domain 6 fixture | N/A | Isolated rule contract probe |

Walter's absent scenario has **zero positive action claims** and follows `b_nsaid_missed` by the authored closed-window predicate. Walter's low-confidence action yields `dp_nsaid=unclear` and the shared selector can still choose `b_partial`; the trace explicitly flags this as uncertain. Eli's conflicting antibiotic actions choose `b_abx`, and the adapter suppresses action-based rubric suggestions in that scenario. These branches are deterministic software states, not validated outcomes.

## Independent review workflow

Export a pending queue with `--export-review-queue /tmp/notebook05_pending.jsonl`. Faculty should review each claim and set `expected_supported` to true/false, `review_status` to `approved`, `reviewer_role` to `faculty`, a pseudonymous `reviewer_id` distinct from `author_id`, and `reviewed_at`; preserve `case_sha256`, `case_version`, and the entire claim. Import with `--reviews /path/to/reviewed.jsonl`. Duplicate, unknown, wrong-source, pending and machine-authored rows are rejected. Only complete independent claim review produces feedback support accuracy. The importer checks metadata, but organizational reviewer independence and clinical merit still require outside confirmation. This queue does **not** confer faculty-approved domain scores; scoring needs a separate reviewed process.

## Progression to Notebook 06

| Gate | PASS | FAIL | Current |
|---|---|---|---|
| Evidence and replay | Every exported claim has validated exact evidence, 4/4 applicable next-state replays, N/A contract holds | Any assertion fails | **PASS** |
| Faculty feedback accuracy | All 41 claims independently reviewed and supported (or explicit agreed threshold later set by faculty) | Fully reviewed claim set fails stated criterion | **NOT EVALUABLE** |
| Faculty rubric scores | Independent reviewed domain scores and agreement protocol | Fully evaluated agreed score criterion fails | **NOT EVALUABLE** |
| Notebook 02 trained extractor | Reviewed grouped train/test data meet macro-F1 and critical recall gates | Evaluated below target | **NOT EVALUABLE** |
| Notebook 04 clinical release, semantics and difficulty | Independent faculty releases/semantic labels and approved complete V-04 design pass their gates | Fully evaluated failure | **NOT EVALUABLE** |
| Learning outcome | Prospective learner study passes agreed target | Evaluated failure | **NOT EVALUABLE** |

The shared documentation fallback flags numbers absent from allowed evidence and finds omissions by token overlap; it does not adjudicate unsupported nonnumeric prose. Decision selection counts low-confidence hits as boolean while marking `unclear`; a clinically relied-on branch needs faculty review. Source IDs in these cases indicate authored provenance, not independent medical verification. No LLM or semantic judge was run. The seven existing HTTP API tests previously stalled at `TestClient` in this sandbox; they are excluded from the non-HTTP run and are not reported as passing.

Run status: the seven Notebook 05 tests passed **7/7**; the relocated plus shared non-HTTP suite passed **54/54** with `--ignore=backend/tests/test_api.py`. Notebook 01–05 code cells executed in fresh kernels (12, 8, 8, 8, 6 cells, respectively). See the terminal/CI status in the PR for the exact environment.
