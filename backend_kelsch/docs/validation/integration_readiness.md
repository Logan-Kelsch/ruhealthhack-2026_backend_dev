# Notebook 07 — reviewed pilot and integration readiness

Date: 2026-10-10. Run `LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_integration` from the repository root. The [JSON report](integration_readiness.json) records the Notebook 06 source lock, packet digest, missing review denominators and audit head. The [notebook](../../notebooks/07_integration_readiness.ipynb) visualizes the backlog. Sources: `AGENTS.md`, `context.md` §§14–15, `PRD.md` §15, Notebook 01–06 reports, three `cases/*.json`, and shared `backend/` contracts.

## Authorization finding

The Notebook 06 protocol says `proposed_pending_faculty_and_ethics_review`. The repository has **no approval evidence** for the protocol, synthetic case set, consent process, review roster, outcome definitions or institutional determination; no consenting learner cohort or genuine reviews were supplied. Notebook 07 runs **quality controls only**. It does not compute a prospective performance metric. An optional `--approval-bundle` checks six document digests, declared roles and the protocol lock but still returns **NOT VERIFIED**: metadata cannot establish authenticity or institutional authority. `--corpus` fails closed. Obtain independent approval verification outside this tool before a new protocol version permits learner intake. [U.S. Office for Human Research Protections guidance](https://www.hhs.gov/ohrp/coded-private-information-or-biospecimens-used-research.html) is a reference for institutional determination; this code makes no determination.

## Source and review preflight

Current case/rubric/vocabulary/protocol/code/report hashes match Notebook 06's manifest. All **287** blinded packets rebuild with identical kind counts and no actual releases, verifier verdicts, provisional grades or scripted levels in their reviewer contexts. They are authored work items, not learner samples.

| Unit | Total | Resolved | Missing |
|---|---:|---:|---:|
| Fact-release turns | 189 | 0 | 189 |
| Semantic candidate replies | 15 | 0 | 15 |
| Debrief claims | 41 | 0 | 41 |
| Rubric-domain ratings | 42 | 0 | 42 |

Observed unresolved disagreements: **0** from **0** review rows; observed N/A ratings: **0** from **0** ratings. These do not estimate agreement or N/A frequency. Reviewed class balance, precision/recall, macro-F1, Cohen kappa, confidence intervals, performance failure examples and learner outcomes are **null**. Notebook 06 has methods for these after genuine reviews and authorization. Prior Notebook 02/04/05 gates stay blocked.

With private `--reviews review.jsonl --audit-log audit.jsonl`, the Notebook 06 importer checks source-locked faculty roles, independent pairs, typed answers, exact evidence and adjudication. Notebook 07 reconstructs each audit event's sequence, packet ID, predecessor and final head; a supplied audit must equal the chain derived from the review rows. Raw text and reviewer IDs do not enter the public report. A correct chain verifies consistency with the supplied source, not institutional approval or reviewer identity. No private review material is committed.

## Progression

| Gate | PASS | FAIL | Current |
|---|---|---|---|
| Import and audit quality | Current lock, packet counts/blindness, approval metadata, review schema and audit integrity check; tests/notebooks run | Any mismatch, leak, bad digest, invalid span or chain | **PASS** |
| Actual faculty/institutional authorization | Trusted external verification of all six approvals before prospective intake | Explicit denial or verified revocation | **NOT EVALUABLE** |
| Trained action, prompted comparison, disclosure, semantics, claim support, grader agreement | Genuine independently reviewed complete labels, held-out data and each Notebook 06 criterion | Fully evaluated prespecified failure | **NOT EVALUABLE** |
| Difficulty and learner outcomes | Approved full presets and sufficient consenting randomized cohort with blinded outcomes | Fully evaluated prespecified failure | **NOT EVALUABLE** |

PASS here means the **engineering preflight works**, not that the study is authorized or beneficial to learners. The next notebook needs a trusted institutional authorization route. Toy inputs in unit tests never enter reports as learner truth.

Verification: **7/7** new Notebook 07 tests and **69/69** moved/shared non-HTTP tests passed. Notebook 01–07 code cells ran in isolated Python processes (12, 8, 8, 8, 6, 6, 5). The seven HTTP API tests collected but timed out after 25 seconds with zero completed in this sandbox; none is counted as passing. A normal Jupyter kernel needs sockets blocked here, so notebook code cells used fresh processes with Agg plotting and IPython display. Commands and counts are in [machine-readable execution results](integration_test_execution.json).
