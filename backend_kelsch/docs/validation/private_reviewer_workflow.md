# Private reviewer workflow validation

Date: 2026-10-10. [Machine summary](private_reviewer_workflow.json), [coordinator/reviewer instructions](../private_reviewer_workflow.md), [toy notebook](../../notebooks/08_private_reviewer_workflow.ipynb).

The Notebook 06 lock and 287-packet denominator match: 189 release, 15 semantic, 41 claim, 42 domain, zero prospective action packets. All Notebook 01–07 reports and shared contracts are unchanged. The 12 newer live candidates are excluded pending separate versioning.

Independent offline files include approved case facts, source hashes, authored trust-event definitions and exact evidence context. Release screens also show effective thresholds for the existing illustrative vectors. They omit engine release results, script levels/intent, verifier verdicts, confidence labels and provisional grades. Claim/domain transcript text is necessarily available as review evidence; a candidate disclosure claim is a question to review, not an engine answer. Independent slots contain no peer answers. Only the third-reviewer file contains both human answers and supplemental evidence/rationale after disagreement.

| Check | Observed result |
|---|---|
| Locked source/packet preflight | PASS, 287/287 prepared |
| Offline backend + notebook tests | 90 passed, 0 failed, 0 uncompleted, 21.97 s |
| HTTP API tests included above | 7 passed, 0 failed, 0 uncompleted |
| New workflow tests | 8 passed, 0 failed, 0 uncompleted |
| Toy transport | 4 packets; 8 independent answers; 2 agreements; 2 disagreements; 2 adjudications; 10 validated audit events |
| Genuine reviews | **0** |
| Supplement notebook | 2/2 code cells passed sequentially as Python source |
| Jupyter kernel | Failed before code execution: socket/network restriction |
| JavaScript | Node mock-DOM render, Unicode span, memory save and download smoke passed; browser acceptance not run |

The tests exercise full blinded projection across all packets, distinct identities, tampered spans, Unicode character offsets, N/A, disagreement routing, missing independent answers, toy rejection, stale context, repository/symlink destination rejection and modified export/audit/supplemental evidence detection. The existing importer and chain verifier validate every export. Extra evidence and rationale are bound by a private supplemental receipt because the locked importer normalizes them out of some answer types. Toy intermediates that resemble genuine importer rows are deleted. Technical toy resolutions do not count as reviews or clinical accuracy.

Engineering **PASS** requires unchanged locked sources, blinded views, private outputs, typed/evidence import round trips and invalid-input rejection. Any failure is **FAIL** and blocks use of the workflow. Model, clinical, semantic, rubric, difficulty and learner gates remain **NOT EVALUABLE** pending their independently supplied reviews, approval and samples. Faculty-role strings and hash chains cannot establish genuine professional identity or institutional authorization. Coordinator-controlled separate access, original records, retention and verification remain necessary. This feature is an offline review aid; it enables no learner recruitment or authenticated shared service.
