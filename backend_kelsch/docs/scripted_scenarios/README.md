# Review the three demo scripts

Each JSON file is one complete scenario. Open it in a text editor, review it with a
clinician, and edit the wording inside quotation marks. No Python edits are needed.

| File | Scenario |
|---|---|
| `01_legionella_final_debrief.json` | Pneumonia after a Philadelphia convention; assessment and antibiotic discussion |
| `02_smoking_cessation_final_debrief.json` | Smoking cessation; the patient remains unwilling to change |
| `03_cardiac_final_debrief.json` | A 45-year-old woman with anxiety history and ST elevation on an electrocardiogram |

These are authored synthetic teaching scripts awaiting clinical review. Each file ends with a single debrief for the entire completed dialogue.

## What to edit

- `patient`: name, age, sex, presenting concern, and history.
- `learning_goal`: what the student should practice. Educator-only.
- `educator_description`: the example background pasted into educator mode.
- `learner_role`, `teaching_notes`, and `sources`: teaching context and references.
- `dialogue`: the conversation in order. Each entry has a suggested `student`
  utterance and the exact `patient` response. Add, remove, or move whole entries.
- `chart`: findings shown after that dialogue entry. Move a finding to another
  entry to change when it appears. Keep its `id` unique. For a new finding, use a
  unique short ID, label, text, source, and `urgent: true` or `false`.
- `debrief`: one block after the entire `dialogue` array. Its `delivery` is
  `after_dialogue`, and `questions` contains the reflection questions for the
  completed encounter. Questions have a rubric domain and text only. They have
  no turn numbers, evidence references, or triggers.

Keep `format`, `scenario_id`, and the debrief `delivery: "after_dialogue"` unchanged. Background, dialogue, findings, and goals
should agree. Debrief questions should guide reflection without giving away the
answer. Mark urgent chart findings directly; chart data still appears during the
encounter. Teaching guidance about those findings belongs in the later debrief.
The importer checks structure and references, not medical correctness.

The dialogue remains a fixed sequence: any student input receives the next patient
line. Changing the suggested student text does not add a branching rule.

JSON requires straight double quotes, commas between entries, and no trailing
commas or comments. Inside a line, write `\"` for a literal double quote. Keep
numbers and `true`/`false` outside quotation marks. Unknown fields and duplicate
JSON keys are rejected, so typos cannot silently discard edits.

## Apply returned files

Run these commands from the repository root using the backend Python environment.
You can pass one, two, or all three files, including files returned in another folder.
An omitted scenario stays unchanged. Filenames may change; `scenario_id` identifies
the case. First check the edited files:

```bash
PYTHONPATH=backend python -m scripts.update_scripted_clinical_demo --check \
  backend_kelsch/docs/scripted_scenarios/01_legionella_final_debrief.json \
  backend_kelsch/docs/scripted_scenarios/02_smoking_cessation_final_debrief.json \
  backend_kelsch/docs/scripted_scenarios/03_cardiac_final_debrief.json
```

Remove `--check` to apply them:

```bash
PYTHONPATH=backend python -m scripts.update_scripted_clinical_demo \
  backend_kelsch/docs/scripted_scenarios/01_legionella_final_debrief.json \
  backend_kelsch/docs/scripted_scenarios/02_smoking_cessation_final_debrief.json \
  backend_kelsch/docs/scripted_scenarios/03_cardiac_final_debrief.json
```

The script validates the whole batch before writing anything. It updates
`backend/app/data/scripted_clinical_demo_v1.json` in one atomic replacement,
generates exact dialogue fact citations and chart release references, recalculates
estimated display delays, and increments only changed case versions. Importing the
same content again makes no change. No database, model call, or server is needed.
Clinical review remains pending. Use the current `clinical_script_review_v3` files. The importer rejects per-turn debrief fields and any delivery other than `after_dialogue`.

The notebook and `/api/demo` endpoints read this runtime file for **new preparations**.
Prepare/start a fresh session to see edits; existing sessions keep their saved script. Complete every dialogue exchange and end the encounter before opening its debrief. An early ending does not release a partial debrief.
For a remote server, deploy the changed runtime file there too. The saved HTML
preview and notebook outputs are snapshots; rerun the notebook to refresh them.

Python callers can use the same function:

```python
from pathlib import Path
from app.demo.authoring import import_scripts

result = import_scripts([Path("returned/01_legionella_final_debrief.json")])
```

## Export the current scripts again

After applying returned files, refresh these review copies before the next review.
Export overwrites the three JSON files in the chosen directory, so import your edits first.

```bash
PYTHONPATH=backend python -m scripts.update_scripted_clinical_demo \
  --export backend_kelsch/docs/scripted_scenarios
```

## Official rubric domain names

- Opening and purpose
- Rapport, respect, and empathy
- Information gathering
- Listening and response to cues
- Explanation and shared decisions
- Clinical reasoning and synthesis
- Professionalism, safety, and closure

These labels link reflection to the official rubric; this rehearsal assigns no grades.
