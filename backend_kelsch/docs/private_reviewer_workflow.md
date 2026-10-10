# Private reviewer workflow, version 1

This workflow wraps the **287 Notebook 06 locked packets**: 189 release judgments, 15 semantic candidates, 41 debrief claims and 42 rubric domains. It reuses the existing importer and Notebook 07 audit verification without editing their locked sources. The 12 newer live adversarial candidates are excluded: they need a separately versioned packet protocol before review.

## Coordinator setup

Use a new directory outside **every Git checkout**, on institution-controlled storage. On Unix the workflow creates its directory with mode 0700 and files with mode 0600. File permissions are not encryption or identity verification. The coordinator verifies faculty credentials, actual independence, permissions to review the synthetic material, and any institutional requirements. Keep identity linkage separately; use private reviewer pseudonyms in submissions. No learner intake is enabled by this workflow.

From the repository root, with the backend Python dependencies installed:

```bash
LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.review_workflow prepare --workspace /private/rounds-review-v1
```

Choose a real writable private location instead of `/private/rounds-review-v1`. `prepare` refuses an existing directory, repository destinations, paths inside another checkout, and symlinks into a checkout. It verifies the historical Notebook 06 lock before generating a private manifest and two HTML files.

Give `reviewer_a.html` only to reviewer A and `reviewer_b.html` only to reviewer B. Open each directly in a browser; there is no server, login service, external dependency, network request, browser storage or shared answer store. Do not give either reviewer access to the coordinator's workspace or the other submission. Independent files contain no answers or identities. The Content Security Policy blocks network access. Source text is rendered with `textContent`, never HTML.

## Reviewer task

The screen shows fact IDs, approved fact text/values, source references, authored disclosure constraints and trust thresholds. “Approved” means the case schema's status; it does not prove independent faculty approval. Personal source attribution is omitted. The screen does not embed the engine mapping, actual release lists, script identifiers/levels/intents, classifier predictions, verifier verdicts, confidence labels or provisional rubric scores.

- Release: the exact prior/current **student** utterances, illustrative threshold vector, approved facts and authored rules. Patient outputs are withheld because they would reveal the engine answer. Judge the whole sequence yourself; supply newly expected fact IDs, including an explicit empty list when none should be newly released. The locked packets do not contain an independently authored full patient transcript for this task.
- Semantic: candidate reply, student utterance, and the locked challenge's availability/history constraints. These are the candidate scenario, not an engine release result. Judge supported/unsupported claims against those constraints and approved facts. No verifier verdict is supplied.
- Claim: candidate claim and its evidence references, alongside the exact transcript. Candidate claims about disclosure are review questions, not authoritative engine release answers. Author labels are not observed learner labels. Confidence and provisional review status are omitted.
- Domain: official rubric domain descriptors and exact transcript, without a provisional score. Supply 1–4 with transcript evidence, or N/A with a specific reason and no evidence. N/A is never converted to zero. Clinical/safety domains 6/7 require faculty judgment.

Independent reviewers enter typed JSON answers using on-screen templates. The exact-context boxes provide selectable text; **Cite selected span** creates Python-compatible Unicode character offsets and an exact quote. **Cite fact** binds the approved fact ID to the case hash. Add a private rationale, especially where a claim has no supporting evidence. Domain evidence is copied into the answer for the existing importer. Save each answer in memory, then **Download submitted answers** before closing. The saved subset is explicit; unfinished packets remain missing. Restore only your own slot's download to resume. N/A is available for rubric domains; other packet types have no N/A label in the locked contract—leave them pending and tell the coordinator if you cannot judge them.

Download destinations are controlled by the browser. Move each submission to private storage immediately; never select a checkout as the download destination. File transfer, access authorization, consent checks, encryption, retention and backup are coordinator responsibilities. A directory on shared storage is not automatically access-controlled. This is a local review aid, not a multi-user authenticated service.

## Adjudication and export

Collect the separate downloads as `submission_a.json` and `submission_b.json` in the private workspace. Validate typed answers, sources, N/A reasons, exact spans, distinct pseudonyms, timestamps, duplicates and review coverage:

```bash
LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.review_workflow validate --workspace /private/rounds-review-v1 --submissions /private/rounds-review-v1/submission_a.json /private/rounds-review-v1/submission_b.json
LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.review_workflow adjudicate --workspace /private/rounds-review-v1 --submissions /private/rounds-review-v1/submission_a.json /private/rounds-review-v1/submission_b.json
```

Only disagreements with **two independent completed answers** appear in `adjudicator.html`. The third reviewer can see the pair's normalized answers and original source context. Their answers must use the same typed contract and evidence checks. They must use a distinct pseudonym. Agreement packets must not be adjudicated. If evidence spans differ on domain/action answers, the existing importer treats that difference as disagreement too.

```bash
LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.review_workflow validate --workspace /private/rounds-review-v1 --submissions /private/rounds-review-v1/submission_a.json /private/rounds-review-v1/submission_b.json /private/rounds-review-v1/submission_adjudicator.json
LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.review_workflow verify-export --workspace /private/rounds-review-v1 --submissions /private/rounds-review-v1/submission_a.json /private/rounds-review-v1/submission_b.json /private/rounds-review-v1/submission_adjudicator.json
```

All outputs stay private: importer-compatible `validated_reviews.jsonl`, `audit.json`, `evidence_receipt.json` and `quality.json`. Existing `load_reviews` validates the export; `verify_audit_log` checks every chain link. The existing audit normalizes answers and does not bind supplemental rationale/evidence for semantic/release tasks, so a separate receipt hashes the complete private submissions and links their manifest to the importer audit head. `verify-export` recomputes both from source submissions, rejects altered exports/audits/evidence, and must run before downstream analysis. This detects accidental or unilateral alteration when trusted originals/head are retained; it is not a signature, identity authentication or an externally timestamped registration. Store receipts and original files under independently controlled retention.

The Notebook 06 importer continues to interpret metadata, not authenticate reviewers. A toy flag cannot defend against someone deliberately relabeling fabricated answers as faculty reviews; coordinator verification of originals remains necessary. No raw identities, answers, transcript text or private audit events belong in a PR. Only aggregate validation counts are committed.

## Toy demonstration and gates

```bash
LLM_ENABLED=false PYTHONPATH=backend python -m backend_kelsch.scripts.review_workflow demo --workspace /tmp/rounds-review-toy-demo
```

The demo selects four authored packets (one per current task), creates clearly marked toy answers, demonstrates two agreements and two disagreements, then third-party adjudication and N/A reasons. Every UI/submission/manifest/report marks toy mode. Production commands refuse toy submissions. Toy importer-compatible intermediates are deleted, and **genuine review count stays zero**. This is a transport/import demonstration, not a clinical or learner study.

Engineering PASS requires unchanged source lock/denominators, blinded allowlisted views, valid evidence/import/audit round trips and rejection of invalid inputs; any violated invariant is FAIL. Clinical disclosure, semantics, trained action extraction, rubric agreement, difficulty and learner outcomes remain NOT EVALUABLE until their existing review/sample/approval conditions are met. Building this workflow grants no study approval. Use the existing Notebook 06/07 analysis only after verifying genuine submissions and authority. Private action/learner intake remains blocked by Notebook 07 pending independent authorization.
