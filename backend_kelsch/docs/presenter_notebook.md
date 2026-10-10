# Clinical presenter notebook

V-01–V-06, S-01–S-06, E-01, F-01–F-05, L-03–L-04, P-01. Open **`backend_kelsch/notebooks/10_clinical_presenter_demo.ipynb`** in VS Code or Jupyter. Select the backend Python 3.12+ environment as the kernel. The notebook walks a medical professional through the actual offline backend, generated annotations/references, provisional feedback and progression, and learner-unit Monte Carlo permutation testing. Every section includes a clinical explanation, presenter translation, and interpretation limits.

## Set up and run

Install the normal backend dependencies plus the existing notebook dependencies into the selected environment:

```bash
python -m pip install -r backend_kelsch/requirements-notebooks.txt
python -m pip install nbconvert ipykernel
```

Use **Restart Kernel → Run All**. The default `RUN_LIVE_BEDROCK = False` runs the complete offline demonstration with native figures and no model requests. It uses seed 2026, 4,999 permutations and 1,999 learner bootstraps per scenario. It chooses a fresh private directory under `~/rounds-private/presenter-demo-<id>/`; restarting chooses another run. Running the simulation cell twice in the same session correctly rejects overwriting the frozen run.

The notebook does not modify production cases or a shared database. Its Studio authoring statuses are code-driven values inside disposable SQLite, not clinical approval. Its text input is the authorized backend test interface, not a new student-facing text box.

## Use your local `.env` for live Bedrock

Keep `.env` at the repository root or `backend/.env`. The backend file overrides matching root-file values; environment variables override file values. Use the existing `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` or configured AWS profile/SDK chain, and `BEDROCK_MODEL_FAST` / `BEDROCK_MODEL_STRONG` settings. The notebook shows only region, model IDs and a credential-route description. It never prints settings dumps, keys, `.env` contents or raw process logs.

Set **`RUN_LIVE_BEDROCK = True`** in the setup cell, then restart and run all. This enables billable requests in a fresh child process and calls the current nine-script classifier/phraser/verifier evaluation. It explicitly sets `LLM_ENABLED=true` for that process without changing the notebook's other offline stages. The credential preflight now reuses the application's `.env`-aware `aws_session()`, so a key pair declared in `.env` is recognized without shell-exporting it. Credential detection does not verify IAM/model permissions; actual failures remain visible.

Fresh files go under `<workspace>/bedrock/`:

- `live_report.json`: model configuration, source/prompt hashes, usage, fallback and mechanical checks.
- `live_trace.json.gz`: each delivered reply, citation, timing, verifier result and model attempt.
- `live_process.log`: private CLI diagnostics. Inspect locally if the process fails; do not commit it.

The notebook reports model successes and failures directly from the trace, alongside fallback counts. `EVALUATED` in the underlying CLI only describes attempted execution; it does not imply model success or clinical validation. An all-failed run is labeled FAILED, a mixture PARTIAL, and a zero-call/offline run NOT EVALUABLE. The plot distinguishes failed retries from successful attempts. Text-turn latency is never relabeled voice first-audio latency.

Alternatively, set **both** `LIVE_REPORT_PATH` and `LIVE_TRACE_PATH` to files from the same saved run, outside Git. The notebook verifies matching version/mode and model-call denominators, and labels them SAVED RUN. It cannot certify the origin of arbitrary user-supplied files. `PRICING_PATH` optionally supplies the existing sourced, dated pricing JSON contract; missing pricing leaves dollar cost unknown. Saved files do not trigger new requests.

Live outputs are operational observations alongside the simulation. They do not manufacture clinical labels or replace the synthetic learner scores. Clinical accuracy still needs qualified reviews, and learning-effect inference still needs authorized genuine outcomes.

## Presentation route

| Stop | Visual / example | Clinical point | Presenter translation |
|---|---|---|---|
| Backend operation | Studio-to-follow-up diagram and actual request checks | Source control and rejected transitions precede clinical review | “The model phrases permitted facts; code controls disclosure.” |
| Encounter | Actual authored Walter transcript and case objective | A scripted test is not a genuine learner encounter | “This is a source-linked rehearsal.” |
| Live models | Optional attempt/failure and latency charts | A template can remain safe when a model fails | “Service execution and clinical correctness are separate questions.” |
| Actions | Exact highlighted spans, grouped split and baseline plot | Intention, negation and hypothetical actions need careful annotation | “A learned word-pattern baseline tests the machinery, not clinical understanding.” |
| Feedback/rubric | Seven-domain table, claim anchors and N/A control | A located citation is not an approved interpretation | “A clinician decides what can be scored.” |
| Difficulty/progression | Discovery curves and N/A/safety routing controls | Estimated threshold offsets are not complete calibrated presets | “More guarded does not automatically mean educationally appropriate.” |
| Learner analysis | One-dot-per-learner plot and phase score example | Invented outcomes are independent of backend-generated grades | “We wrote benefit into this fixture.” |
| MCPT | Frozen-plan null histogram, effect intervals and denominators | Shuffle learners, keep repeats together, do not impute N/A | “How surprising is this difference under an appropriate shuffled-assignment null?” |
| Review handoff | Exact file paths, replacement map and evidence gates | Human authority and consent cannot be synthesized | “These are the judgments we need next.” |

Use the full notebook for a 12–15 minute review. For a short pitch, use the backend diagram, one encounter/action example, the MCPT controls figure, and the replacement map. Pre-run live inference before presenting to avoid waiting on variable service latency. Live access, voice, PostgreSQL/cloud deployment, cost measurement and genuine evidence are all separately scoped.

## Export and share

The committed notebook has **no execution outputs**. Keep any locally executed notebook with live content private. For a reproducible offline HTML walkthrough and executed notebook, run from the repository root:

```bash
LLM_ENABLED=false PYTHONPATH=backend python -m scripts.export_presenter_notebook \
  --output ~/rounds-private/presenter-export-v1
```

This requires a new output directory and the pristine offline notebook configuration. By default it executes a native Jupyter kernel, exports `presenter_demo.html`, writes `executed_presenter.ipynb` and `execution_receipt.json`, and preserves the simulation outputs/figures under `runs/`. HTML hides code inputs and presents the clinical narration, tables and charts; it can be opened without Python. The export path never performs live inference. If a restricted host blocks Jupyter kernel transport, add `--in-process` to execute all cells through IPython in the current process and capture their rich displays. The receipt records which execution method actually ran.

The committed [offline HTML preview](validation/presenter_demo/presenter_demo.html) and [validation receipt](validation/presenter_demo/checks.json) were generated from the notebook, not reconstructed as mock screenshots. This work environment blocked native Jupyter ZMQ transport, so the verified snapshot uses the explicit in-process IPython method; native-kernel completion is not claimed. Paths/timing may differ on your computer. The simulation report and review/source receipts live inside your new private workspace. See [simulation methods and exact human replacement contracts](simulation_demo.md).
