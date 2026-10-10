# Advance action extraction and feedback to the next human review

V-03, P-01, F-01, F-03, F-05, L-03–L-04. This stage regenerates development encounters with current code rather than reusing the old phraser-v2 trace. It freezes independent work items and predictions before reviewers receive them. It leaves the historical 287-task and live 90-task batches unchanged.

## What this PR advances

- **Action extraction:** deduplicate authored student utterances per case, add the existing eight critical-action probes, run the keyword baseline, and preserve exact action spans. No authored expected labels appear in reviewer views. Unsupported research labels and ambiguous spans are recorded as omissions, never assigned invented offsets.
- **Feedback:** regenerate six authored debrief scenarios, show the entire candidate claim and its anchors, and ask whether the evidence supports it. Include documentation as separate exact-context units. Freeze the emitted-claim support assumption privately; human unsupported labels become visible diagnostic failures.
- **Scoring:** collect independent scores for all seven official domains on each of the six transcripts. Freeze the current rule-based scores privately. Report paired agreement, model disagreement, N/A mismatches and numeric agreement after import. These are six authored encounters, not the proposed 15–20 independent transcripts.
- **Clinical/difficulty/progression:** generate a source-versioned decision worksheet containing roles, threshold probes, decision points, authored outcomes and flagged uncertain branches. It needs actual decisions before changing case content or approving full presets.

No production API, vocabulary, case, prompt or learner authorization contract changes. Preparation makes no Bedrock call. It does not exercise the integrated voice interface. No dataset was downloaded and no new clinical ground truth was synthesized.

## Prepare the next review

From repository root in the backend environment:

```bash
LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_next_review prepare \
  --workspace ~/rounds-private/next-review-v1
```

The workspace must be new and outside every Git checkout. It contains:

| Path | Who uses it |
|---|---|
| `action/reviewer_a.html`, `action/reviewer_b.html` | Independent exact-span action reviewers |
| `claim/reviewer_a.html`, `claim/reviewer_b.html` | Independent feedback claim reviewers |
| `domain/reviewer_a.html`, `domain/reviewer_b.html` | Qualified independent rubric reviewers |
| `clinical_and_difficulty_decisions.md` | Qualified clinical reviewer and preset/progression owner |
| Each batch's `PRIVATE_predictions.json` | Coordinator only; never give to independent reviewers |
| `stage.json`, batch manifests and task files | Coordinator source/version receipts |
| `README.md` | Instructions included in the handoff |

The review pages work offline in a browser. Reviewers enter JSON using the provided examples and use the citation buttons; no Python or AWS credentials are needed. Downloads include their pseudonym, exact answers, evidence, rationale and timestamp. They must download before closing. Keep raw human reviews outside Git; publish aggregate checks only.

For documentation citations, select text from the `note:<field>` exact-context box. Its turn 0 is a note anchor, not spoken student evidence. A claim's original note-span anchor remains visible as well. Domain ratings use only transcript spans or a specific N/A reason. Numeric scores and classifier predictions are withheld from the independent view.

## Import and resolve, one batch at a time

Example for action (substitute `claim` or `domain` for those batches):

```bash
LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_development configure \
  --workspace ~/rounds-private/next-review-v1/action \
  --a ~/rounds-private/next-review-v1/action/submission_a.json \
  --b ~/rounds-private/next-review-v1/action/submission_b.json \
  --a-kind human --a-id reviewer-a --a-description 'Independent human action reviewer; qualifications recorded privately' \
  --b-kind human --b-id reviewer-b --b-description 'Independent human action reviewer; qualifications recorded privately' \
  --predictions ~/rounds-private/next-review-v1/action/PRIVATE_predictions.json \
  --output ~/rounds-private/next-review-v1/action/reference_human_v1.json

LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_next_review adjudicate \
  --workspace ~/rounds-private/next-review-v1 --kind action \
  --config ~/rounds-private/next-review-v1/action/reference_human_v1.json
```

Config pseudonyms must match browser exports. Adjudication requires both full independent submissions. It generates only disputed tasks, shows the original human labels, evidence and rationales, and keeps model predictions hidden. Send `adjudicator.html` to a distinct third reviewer if there are disagreements. Reconfigure into a **new** version with `--adjudicator`, its actual `--adjudicator-kind human`, pseudonym and description. Do not edit/relabel the old source files.

```bash
LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.eval_next_review report \
  --workspace ~/rounds-private/next-review-v1 --kind action \
  --config ~/rounds-private/next-review-v1/action/reference_human_v2.json \
  --output ~/rounds-private/next-review-v1/action/report_v2.json
```

If no adjudication was needed, use v1. Partial submissions produce a pending report; they do not produce a complete comparison. The source config must match the frozen stage manifest and original prediction digest. Replacing predictions after the review is rejected. These hashes help preserve a declared sequence but cannot prove reviewer blinding or authority outside this workflow.

The report retains pending IDs, original provenance, answer differences with source mappings, paired domain agreement, and critical positive span counts. It rejects changed current source code, cases or vocabulary; evaluate from the frozen checkout or prepare a new batch. Use failures to target the next code changes. An action negative is `other`; the research vocabulary is narrower than all production case actions. Exact span boundaries matter, and different annotations of the same utterance may need adjudication. Critical recall with little positive support must not be called validated performance.

## The next human stop and path through MCPT

1. Complete the new action/claim/domain reviews and adjudicate disagreements. Existing semantic reviews remain a separate batch; they cannot supply action labels or rubric scores.
2. Resolve the clinical worksheet with qualified reviewers. It records proposed decisions, not approval. Version accepted case changes, rerun relevant checks and freeze a new batch for changed outputs.
3. Supply independent action conversations with whole patient/family/duplicate groups held out and sufficient critical positives. Use the existing grouped action-data training workflow; this small authored batch is a development regression set.
4. Approve full difficulty presets and next-case routing. Threshold offsets alone are not complete presets; actual learners must establish difficulty.
5. Run the fresh live Bedrock evaluation and full Studio → voice → chart → debrief → follow-up rehearsal. Measure voice first-audio latency and actual costs.
6. Freeze the authorized learner protocol and outcome definitions, collect genuine baseline and held-out follow-up results with blinded scoring, then analyze under the appropriate learner-level permutation design. The existing synthetic Monte Carlo permutation test demonstrates mechanics only; this PR does not enable observed learner intake or bypass authorization.

The human replacement files reported by the user were not present in the fetched `main` snapshot (`035baf4`). No new human results are claimed in this PR. To evaluate them, provide their branch/path or private reference config; do not turn the old AI files into human records by changing metadata alone.
