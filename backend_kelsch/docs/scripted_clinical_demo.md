# Three-case scripted clinical rehearsal (P-02, S-01, F-05)

This opt-in demo walks from an educator's natural-language description through structured metadata, a fixed student–patient conversation, progressive findings, and a separate post-encounter debrief with indirect reflection prompts. It uses real HTTP handlers and persisted sessions. It does not call an LLM, interpret arbitrary student questions, assign grades, or establish clinical approval.

The dialogue is authored synthetic content representing the intended LLM-assisted experience. It is not a recording of live Bedrock output. `actual_model_calls: 0` and `execution_mode: scripted_playback` are returned explicitly. `LLM_ENABLED=true` in a local `.env` does not change this mode.

## Cases

| Select | Fixed example | Teaching target | Path behavior |
|---|---|---|---|
| 1 | Daniel Mercer, 58; fever, cough, breathlessness, diarrhea; Philadelphia convention and hotel stay | Elicit illness course and exposure history; investigate pneumonia and consider Legionella-directed antibiotic coverage under supervision | Ten exchanges. Travel is a clue, not a confirmed source or diagnosis. Hypoxemia is visible in the chart; safety reasoning is reviewed after the encounter. Testing stays pending. No antibiotic dose or universal regimen is supplied. |
| 2 | Marcus Hale, 42; tobacco use and difficult past quit attempt | Explore readiness, sustain talk, priorities, and autonomy | Eight exchanges. A premature quit-date question produces resistance; the student repairs the interaction. The patient remains unwilling to quit. Success is not defined by cessation agreement. |
| 3 | Leah Carter, 45; nausea, sweating, fatigue, vague chest unease; panic/anxiety history | Avoid anchoring; recognize the released ST-elevation pattern and escalate urgently | Eight exchanges. ECG and vitals release at step 3. The ECG is a synthetic text report, not a waveform. Escalation is immediate; the script does not wait for troponin or a complete interview. |

All cases have `clinical_review_status: pending`. Exact symptoms, timelines, findings, and dialogue are invented. Sources support the clinical patterns, not approval of these individual cases.

## Notebook

Open `backend_kelsch/notebooks/11_scripted_clinical_demo.ipynb` in VS Code or Jupyter, select the backend environment, and run all cells. Install notebook dependencies if needed:

```bash
python -m pip install -r backend_kelsch/requirements-notebooks.txt
```

Set `CASE = 1`, `2`, or `3`. Leave `API_BASE_URL = None` for real routes against a temporary isolated SQLite database. The notebook does not change the database selected in `.env`. Pasted educator text is editable in a widget or `EDUCATOR_TEXT`. Student controls offer a presenter suggestion, a text input, send, start, **End encounter**, and a separate **View debrief** control. View debrief is disabled until the conversation has ended; its output never appears inside the conversation.

`REPLAY_ALL = True` displays all three completed rehearsals in separate sessions. `SHOW_NATURAL_DELAY = True` enables estimated patient-display waits; set it false for quick review. The preview in `docs/validation/scripted_demo/scripted_clinical_demo.html` is a static presentation; interactive widgets need the notebook kernel.

To regenerate a static preview on a local machine with a working kernel:

```bash
DEMO_NOTEBOOK_FAST=1 jupyter nbconvert --execute --to html --no-input \
  backend_kelsch/notebooks/11_scripted_clinical_demo.ipynb
```

## Run the API for a frontend

From `backend/`, apply migrations to the database configured in your local environment and run the server:

```bash
python -m alembic upgrade head
SCRIPTED_DEMO_ENABLED=true python -m uvicorn app.main:app --reload
```

Alternatively set `SCRIPTED_DEMO_ENABLED=true` in the existing `.env`. The routes return 404 while disabled. Use `http://localhost:8000/docs` to inspect the generated contracts. Educator routes include teaching material and should be exposed only to the presenter/educator in this rehearsal. The demo inherits the repository's deployment/authentication boundary; it adds no role authorization system. Keep it in a controlled demo environment.

| Action | Method and endpoint | Request / response |
|---|---|---|
| Select / inspect educator examples | `GET /api/demo/educator/scenarios` | All three goals, metadata, sample descriptions, references, suggested student sequences |
| Prepare | `POST /api/demo/educator/preparations` | `{scenario_id, description}` → preparation ID, canonical patient, extracted spans, mismatch warnings, fixture hash |
| Start | `POST /api/demo/sessions` | `{preparation_id, accept_fixed_script: true}` → current public session |
| Resume | `GET /api/demo/sessions/{sid}` | Transcript, released chart, next step; no future replies, goal, or full instructor metadata |
| Advance | `POST /api/demo/sessions/{sid}/turns` | `{expected_step, request_id, text}` → static patient turn, new chart items, assumed display delay; no teaching feedback |
| End | `POST /api/demo/sessions/{sid}/end` | Ended session; conversation stops, no debrief returned; early ending allowed |
| Debrief | `GET /api/demo/sessions/{sid}/debrief` | Separate post-encounter review citing completed exchanges; 409 until ended, no grade |

Example first request:

```json
{"scenario_id": 3, "description": "Leah Carter is a 45-year-old woman with panic attacks and anxiety. She has nausea, sweating, fatigue and chest unease."}
```

Example turn:

```json
{"expected_step": 1, "request_id": "turn_1_attempt", "text": "Tell me what feels different today."}
```

**Input semantics:** every nonblank committed student turn consumes the next reply, regardless of meaning. The recommended sequence is supplied to the presenter, not the student session. Off-script text can create an incoherent conversation; do not present this as semantic responsiveness. The debrief changes off-script anchors to general reflection questions and never claims an unobserved error.

## Typed frontend transport and timing

Use `scriptedDemo(createApi(baseUrl))` from `frontend/src/api/demo.ts`. Its types come from the regenerated OpenAPI contracts in `frontend/src/api/{openapi.json,schema.ts}`. No frontend screen is changed by this PR.

```typescript
import { createApi } from "./client";
import { scriptedDemo } from "./demo";

const demo = scriptedDemo(createApi("http://localhost:8000"));
const prep = await demo.prepare(3, educatorDescription);
let session = await demo.start(prep.preparation_id);
const request = {
  expected_step: session.next_step!,
  request_id: crypto.randomUUID(),
  text: committedStudentTranscript,
};
const result = await demo.turn(session.session_id, request);
// Show released chart findings. Turn responses contain no teaching feedback.
// Optionally show the patient reply after simulated_delay_ms; this is a presentation wait.
session = await demo.read(session.session_id);
// When the user finishes the conversation:
const ended = await demo.end(session.session_id);
// Only then, in a separate review area:
const feedback = await demo.debrief(ended.session_id);
```

Disable submission while pending. Retry the exact same body and `request_id` after a network failure; retries return the saved response and do not advance twice. Reusing a key for different text returns 409. `expected_step` and an atomic database revision protect against stale tabs and concurrent workers. On 409 reload the session; do not silently move the input to another step. Start and end are idempotent for the same preparation/session. Create a new preparation to restart.

Estimated delays use `min(2400, 850 + 32 * word_count)` milliseconds per reply, frozen in the fixture; educator presentation delay is 1600 ms. These are estimates, not sampled model/voice latency. The server does not sleep. This lets the UI show chart findings before a cosmetic wait. Chart entries retain source/provenance fields. Teaching guidance is reserved for the post-encounter debrief; the turn response keeps its existing `safety_notice` field as null for compatibility.

For the actual production encounter, spoken transcripts still go to `/api/encounters/{id}/utterances` and patient speech uses the existing voice integration. A presenter-only text rehearsal is authorized by this demo request; this PR adds no production student typing box.

## JSON replacement boundaries

For clinician review, use the three condensed files in
[`scripted_scenarios/`](scripted_scenarios/README.md). They contain each dialogue
only once and place chart findings at their release turn. After edits, run
`PYTHONPATH=backend python -m scripts.update_scripted_clinical_demo <file1.json> <file2.json> <file3.json>`
from the repository root. Add `--check` for a validation preview. The importer
generates internal citations, release references, timing, and changed case versions;
new preparations use the result. The folder README covers partial imports and exports. Current review files use `clinical_script_review_v2`, explicitly set `debrief_delivery: "after_encounter"`, and use `evidence_turn` to cite completed exchanges. Original v1 files with `after_turn` still import; new exports use the updated labels.

`backend/app/data/scripted_clinical_demo_v1.json` contains the three complete authored snapshots. `ScriptFixture` in `backend/app/schemas/demo.py` validates contiguous steps, exact authored dialogue sources, chart release references, and debrief anchors. `PatientMetadata` and `MetadataExtraction` are the interchangeable metadata contracts.

The deterministic structurer categorizes explicit text into exact source spans. It extracts a digit-based age and explicit sex term, and recognizes the selected fixture's name if present. It does not perform general name recognition, infer clinical facts, interpret negation into diagnoses, or reconcile the pasted description with the dialogue. Negated text remains verbatim. Unmatched text remains visible; demographics disagreements produce warnings. The canonical fixed fixture is returned alongside the extracted description, never silently replaced by it.

Change dialogue, findings, goals, example descriptions, references, and reflection questions together. The review-file importer increments `fixture_version` automatically; when editing the runtime fixture directly, increment it yourself. Create a new preparation. Each preparation saves a complete snapshot plus a SHA-256 hash. Older sessions use their pinned version even if the fixture changes on disk. These demo sessions live in their own table; none enters production grades, reviewer evidence, learner outcomes, or MCPT.

To use an actual model later, add a structuring adapter returning `MetadataExtraction` and preserve explicit provenance. To author a production case, use the existing `Case` schema and Studio review workflow; this demo format is not a direct `Case` import. A future retrieval-supported debrief needs approved hint material and reveal rules. Neither a live model nor RAG is required for this rehearsal.

## Debrief and rubric boundary

The debrief is a separate phase after the conversation has ended. During the encounter, responses contain patient dialogue and released chart findings only. Neither a chart release nor reaching the last scripted reply opens or returns debrief feedback.

Call `POST /api/demo/sessions/{sid}/end` to close the conversation, then call `GET /api/demo/sessions/{sid}/debrief` and render that response outside the conversation transcript. The debrief read never ends an active encounter; it returns 409 for both active and ready-to-end sessions. Explicit early ending is allowed and reviews only exchanges that occurred. Repeated debrief reads are stable and do not advance dialogue.

Questions are linked to official seven-domain rubric IDs and the exact submitted student text and delivered patient reply at their anchor turn. `anchor_step` (runtime) and `evidence_turn` (review JSON) identify transcript evidence, not during-conversation feedback triggers. The debrief invites reflection rather than printing the final diagnosis or expected antibiotic. It is **scripted guided reflection**, not a validated PEARLS implementation, a conversational tutor, or an automated assessment of mistakes. Safety reasoning is reviewed retrospectively in the ended-session debrief. The chart retains its authored urgency flags during the encounter. N/A/numeric scoring belongs to the existing production scorer; this rehearsal assigns no score.

## Reproduce the HTTP rehearsal

From repository root:

```bash
LLM_ENABLED=false PYTHONPATH=backend python -m scripts.run_scripted_clinical_demo \
  --output /tmp/rounds-scripted-demo.json
```

Add `--scenario 1`, `2`, or `3` for one example. All cases make 39 requests and deliver 26 fixed replies. The report distinguishes actual handler timings from invented display waits and states zero model calls. It creates and cleans up an isolated SQLite database.

Validation details and known baseline issues are recorded in `docs/validation/scripted_demo/validation.json`. The native Jupyter kernel transport is blocked in the development runtime; notebook cells were executed through IPython instead, including interactive suggestion/send/early-end callbacks. The post-encounter update verifies separate end/view controls, a blocked active debrief read, no coaching during turns, and reset of debrief access when preparing a new case. Post-encounter callback results are saved in `docs/validation/scripted_demo/post_encounter_debrief.json`. Rehearsal source code and a refreshed static HTML preview are supplied.

## Clinical sources

- CDC [Legionella clinical guidance](https://www.cdc.gov/legionella/hcp/clinical-guidance/index.html): travel history, paired testing, appropriate coverage, no treatment delay for specimen collection.
- CDC [clinical features](https://www.cdc.gov/legionella/hcp/clinical-signs/index.html): respiratory and gastrointestinal symptom context.
- NCDHHS [motivational interviewing](https://www.dph.ncdhhs.gov/programs/chronic-disease-and-injury/tobacco-prevention-and-control/quitlinenc/providers/treatment/motivational-interviewing): open questions, reflection, permission, and autonomy.
- [2025 ACC/AHA ACS guideline](https://www.jacc.org/doi/10.1016/j.jacc.2024.11.009): early ECG assessment and emergency management framework.
- AHA [heart attack symptoms in women](https://www.heart.org/en/health-topics/heart-attack/warning-signs-of-a-heart-attack/heart-attack-symptoms-in-women): varied symptoms; chest discomfort remains the most common symptom.
