# PRD — [Product name] (DRAFT)

**Status:** draft v0.1, 2026-10-10. Written before any code exists, so expect changes. Change this file in the same pull request as the code that changes the plan.

**Working name:** Rounds (may change; docs write [Product name]).

**Event:** Rutgers Health Hack 2026, TwinVerse track, Challenge 1 (Virtual Patient Encounter System), plus selected Challenge 2 ideas.

**Companion docs:**
- `context.md`: the full background, every decision, and the Shared Dictionary of terms. Read its section 14 before naming anything.
- `AGENTS.md`: how to work in this repo.

Priority labels:
- **P0:** must be in iteration 1, or the core demo fails.
- **P1:** should be in the final video.
- **P2:** stretch.

---

## 1. Summary

[Product name] lets health-professions faculty build a virtual patient in minutes by describing them in plain language. The system fills in statistically grounded details, asks guided questions about gaps, checks the case for contradictions, and publishes it.

Students then hold a **hands-free voice conversation** with that patient. The patient only says faculty-approved facts and opens up as trust is earned. The student examines the patient by narrating the exam, and the chart fills in as information is discovered.

The debrief scores the student on the school's own 7-domain rubric. Every score is linked to the exact moment in the conversation that justifies it. Patients can return for follow-up visits, and their condition depends on what the student did last time.

## 2. Problem

- **Standardized-patient practice is scarce and expensive.** Trained actors cost money and scheduling time, so students get few practice encounters before graded OSCEs (Objective Structured Clinical Examinations) and clinical rotations.
- **Existing chatbots have three faults.**
  - They invent clinical facts.
  - They give away information without making the student earn it.
  - Their feedback can't be traced to anything the student actually said.
- **Faculty can't easily author new cases.** They also can't see what a whole class keeps missing.
- **The hosts already run a profile-based system (VHS).** Its sample profiles contain internal contradictions (see `context.md` §7), which shows that case quality control is a real need.

## 3. Users

| User | Needs |
|---|---|
| **Faculty / case author** (dietetics, speech-language pathology, lab science, medicine, nursing…) | Build a case quickly; trust that the patient stays on-script; reuse and share cases; see class-wide gaps; adjust grades. |
| **Student** (role set per case: profession or specialty plus training level, such as medical student, resident, attending, dietetics student) | Realistic practice; hands-free voice; feedback that cites what they actually did; a next step. |
| **Program lead** (secondary) | Anonymized export; alignment with their rubric; evidence the system is reliable. |

## 4. Goals and non-goals

### Goals
1. A **faculty member can create a new patient and run an encounter with it, with no code changes.** This is the brief's Key Demonstration.
2. **Zero unsupported clinical facts reach the student,** and the system can prove it with a grounding log.
3. **Explainable feedback:** every rubric score and trust change cites transcript evidence.
4. **Longitudinal patient state** (the "twin"): the next visit depends on the previous one.
5. **Measured reliability** shown in the video: grounding rate, disclosure accuracy, grader agreement and difficulty calibration.

### Non-goals (for this event)
- Claims about learning outcomes ("students improve X%"). We measure the system, not learning.
- Real patient data or any PHI (protected health information). Synthetic only.
- Probabilistic outcome prediction ("dies 12% of the time").
- Multi-agent clinicians talking to each other (C2 top tier).
- Production authentication, LMS (Canvas) integration, mobile apps. Canvas can be a mocked endpoint (P2).
- HIPAA compliance claims.

## 5. Judging map

| Criterion | What answers it |
|---|---|
| Innovation and creativity | Guided intake that grounds values in population data; trust-gated disclosure with a quoted-evidence ledger; ghost-path decision tree; narrated exam. |
| Technical implementation | Deterministic disclosure engine + phraser + verifier; schema-validated case documents; generated API types; tests; clean modules. |
| Impact and relevance | The judges' own SHP data and rubric; class-wide gap view for faculty; safety catches (Walter's ibuprofen). |
| Presentation and documentation | 4-minute video; this PRD; setup and deploy steps in the README. |
| Feasibility and scalability | Imports the hosts' VHS format; config-driven AWS deploy; cost per encounter reported. |
| C1: architecture and reusability | Any published case runs with no patient-specific code; live creation in the video. |
| C1: profile quality and validity | Consistency checker; coded values (ICD-10-CM, LOINC, RxNorm); source label on every value. |
| C1: encounter quality | Always-on voice; in-character persona; progressive chart; narrated exam. |
| C1: feedback effectiveness and explainability | Rubric with evidence spans; elicited/missed list; audio playback at the cited moment. |

## 6. Iterations

### Iteration 1 (build first; no video avatar)
- **Studio:**
  - plain-language description → draft case;
  - guided intake;
  - auto-fill with sources;
  - fact editor;
  - labs, exam findings and disclosure rules;
  - consistency check;
  - publish;
  - VHS import.
- **Encounter:**
  - briefing card;
  - center patient with a **circular profile photo**;
  - **always-on live transcription** (no typing, no push-to-talk);
  - patient voice through ElevenLabs TTS;
  - transcript below; left and right panels;
  - narrated exam;
  - progressive chart;
  - disclosure log.
- **Feedback:**
  - 7-domain rubric with evidence;
  - elicited and missed;
  - trust timeline;
  - documentation with a fabrication check.
- **Platform:**
  - Postgres;
  - Bedrock;
  - template fallback;
  - test students;
  - grounding statistics;
  - cloud deploy.

### Iteration 2
- Tavus video avatar in the center, with our backend as the custom LLM.
- Longitudinal visits and the decision-tree editor and debrief.
- Faculty class dashboard.
- Audio playback with highlights.
- Grader-agreement study with Ahmad's labels.
- Visual polish; the video.

### Stretch (P2)
- 3D body figure.
- PrimeKG suggestions.
- Syllabus → objectives extraction.
- Rubric import beyond the default.
- Canvas mock endpoint.
- Raven perception cues.
- Synthea import.

---

## 7. Features and acceptance criteria

Feature IDs are stable. Reference them in branch names, pull requests and commits (for example `feat/S-04-auto-fill`).

### 7.1 Patient Studio (faculty)

#### S-01 Plain-language case creation (P0)
Faculty type or speak a description (for example "a mother insists her 6-year-old needs antibiotics for a cold; negative strep swab"). The system produces a draft case: profile, facts, disclosure tiers, baseline vitals, ROS (review of systems), social history, labs, exam findings and objectives.

**Acceptance:**
- The draft validates against the case schema.
- Every generated item is marked `status: "draft"` with a `source`.
- No item reaches students until it is approved.

#### S-02 Guided intake (P0)
After the draft, the Studio asks follow-up questions **only** about missing required fields and risky gaps (for example "Any allergies?" or "Should she disclose suicidal thoughts, and when?"). A visual shows the case graph filling in, plus a completeness ring.

**Acceptance:**
- Questions are generated from a deterministic gap list (required fields, plus rules like "medication present without an indication").
- The LLM only phrases the question.
- Faculty answers go back through the same extraction step and update the draft.

#### S-03 Required baseline (P0)
Every case has vitals, ROS for all systems, social history, allergies, medications and a normal default for every exam maneuver. This ensures any reasonable question has an approved answer.

**Acceptance:** publishing is blocked while the baseline is incomplete, and the missing items are listed.

#### S-04 Statistically grounded auto-fill (P0)
Values the faculty didn't set are filled from data, never guessed by the LLM.
- **Normal values:** NHANES age- and sex-matched distributions where available; otherwise a published reference interval with its source named.
- **Guideline shifts:** a diagnosis moves values into the matching range (diabetes: A1C ≥6.5% per ADA; CKD stage 3: eGFR 30–59 per KDIGO; stage 2 hypertension: ≥140/90 per ACC/AHA).
- **Linked values are computed:**
  - eGFR from creatinine, age and sex (CKD-EPI 2021, race-free);
  - anion gap = Na − (Cl + HCO₃);
  - eAG = 28.7 × A1C − 46.7.
- **A seed per case** makes values reproducible.

**Acceptance:**
- Each value carries `source` ∈ {`nhanes:<table>`, `reference:<citation>`, `rule:<guideline>`, `computed:<formula>`, `faculty`}.
- Regenerating with the same seed yields identical values.
- Unit tests cover the formulas.

#### S-05 Fact editor (P0)
A list and editor for facts: text, value/unit, category, disclosure tier, unlock condition, belief (unreliable narrator), and links to objectives.

**Acceptance:**
- Facts have stable IDs (`f_` + short slug or ULID).
- Editing a fact never changes its ID.
- Deleting a fact referenced elsewhere shows the references first.

#### S-06 Labs (P0)
- Sliders and inputs grouped by panel: CBC, BMP/CMP, magnesium, phosphorus, A1C, glucose, troponin, lipid panel.
- Lookup for other labs from a cached LOINC subset (about 100 codes).
- Each lab: LOINC code, value, unit, reference range and its source, collection date, release rule.
- Optional range plus seed for repeat measures.

**Acceptance:** out-of-range values show high/low flags; the consistency check runs on change.

#### S-07 Exam findings (P0)
- A catalog of about 40 maneuvers by body system, each with a normal default.
- Faculty set abnormal findings in plain text or structured form.
- Must include: inspection, palpation, percussion, auscultation (heart, lungs, abdomen), pedal edema, anterior and posterior drawer, Lachman, McMurray, empty can, Tinel, valgus and varus stress.

**Acceptance:** every maneuver has an approved finding (default or set) at publish time.

#### S-08 Diagnoses, medications, allergies with codes (P1)
- Diagnoses: ICD-10-CM (SNOMED CT only if a UMLS license is obtained).
- Medications: RxNorm.
- Search via NLM Clinical Tables, cached locally so demos work offline.
- Unknown drug names are flagged (this catches "Epirocil").

**Acceptance:** each coded item stores code, system, display name and lookup source.

#### S-09 Artifacts and imaging (P1)
- Attach images and documents (X-ray, CT, ECG, prior notes) with a release rule.
- A curated library of about 10–20 openly licensed images, matched by description, each with license and attribution stored.
- ECGs rendered from PTB-XL signals (CC BY 4.0).

**Acceptance:** an artifact can't be published without a license and attribution field.

#### S-10 Personality and presentation (P0)
- Structured traits: openness, irritability, verbosity, health literacy, mood, humor, plus example lines.
- A **difficulty preset** (see S-11).

**Acceptance:** the phraser prompt is built only from these fields plus the allowed facts.

#### S-11 Difficulty presets (P1)
A preset is a parameter vector:
- number of hidden facts;
- trust thresholds per tier;
- tangentiality (chance of off-topic remarks, which come from approved "small talk" facts);
- red-herring count;
- health literacy;
- emotional state.

There are three named presets (Straightforward, Typical, Difficult historian) plus custom.

**Acceptance:** calibration run (V-04): "Difficult" yields significantly fewer discoveries than "Straightforward" for the same test student.

#### S-12 Consistency check (P0)
Rule-based checks, with optional LLM suggestions that must be confirmed:
- labs versus text (for example "high sodium" with Na 136);
- unknown drug names;
- linked-value mismatches;
- conflicting history (widowed versus "my kids");
- weight-change contradictions;
- medication without an indication;
- allergy conflicts with medications.

**Acceptance:**
- Running it on the imported Walter Greene profile flags at least the 4 issues in `context.md` §7.
- Results are worded as "worth review", not "error".

#### S-13 Learning objectives and rubric (P0)
- Objectives are attached to a case; each has expected discoveries (fact IDs) and expected actions.
- The default rubric is the official 7-domain SHP rubric (from `encounter_evaluation_rubric.json`).
- Rubric import for others (P2), for example the SLP checklist.

**Acceptance:** each objective links to at least one fact or action.

#### S-14 Preview with test students (P1)
Run 1–3 scripted AI test students (novice, competent, expert) against a draft case before publishing. Show what they found, what was blocked, and score ranges.

**Acceptance:** runs use the same pipeline as real students, through the text entry point (I-07).

#### S-15 Publish and versioning (P0)
- Publishing freezes a version.
- Encounters reference `case_id` plus `version`.
- Edits create a new draft version.

**Acceptance:** an old encounter always replays against the version it used.

#### S-16 VHS import (P0)
Import the hosts' profile JSON (all 8 sample patients). Maps:
- `information_disclosure` tiers to facts;
- `learning_opportunities` to objectives;
- `possible_patient_reactions` to example lines.

The consistency check runs on import.

**Acceptance:** all 8 profiles import without code changes; the parser handles concatenated JSON (`raw_decode` loop).

#### S-17 Knowledge sources (P1)
Attach papers, guidelines and protocols (PDF or URL) to a case. They are used only to *suggest* facts or objectives, which faculty must approve.

**Acceptance:** suggestions cite the source and page or section.

#### S-18 Syllabus → objectives (P2)
Extract candidate objectives from an attached syllabus (for example MLSC 4329). Faculty approve.

### 7.2 Encounter (student)

#### E-01 Assignment and briefing card (P0)
- The instructor assigns a case, role and visit to a student or cohort, or a set of cases at once.
- Role = profession or specialty plus training level. Assign roles a learner at that level actually holds (a medical student is not assigned "cardiologist").
- Before starting, the student sees the briefing card: patient name, age, setting, **their role**, goal and **doorway vitals**.
- Not gamified.

**Acceptance:** the card is understandable to a first-time viewer (checked in a hallway test).

#### E-02 Layout (P0)
- **Center:** the patient (a circular portrait in iteration 1; Tavus video in iteration 2) with a speaking indicator.
- **Below:** the live transcript.
- **Left:** goal, referral or prior note, exam actions log.
- **Right:** the chart (vitals, labs, meds, problems, artifacts), filling in as facts are released. Each entry is clickable to show its source.

**Acceptance:** works at 1280×720 (recording size) and 1920×1080.

#### E-03 Always-on voice input (P0)
- The microphone opens when the encounter starts and stays live. **No push-to-talk; no text box.**
- Streaming STT (ElevenLabs Scribe v2 Realtime) shows partial text live; VAD commits an utterance after a silence threshold (start at about 1.0–1.5 s; tune it).
- Browser echo cancellation is on. Headphones are recommended in the UI.

**Acceptance:**
- Committed utterances arrive at the backend with word timestamps when available.
- A mute toggle exists (privacy), but muting is not a way to type.

#### E-04 Patient voice output (P0)
- Replies are spoken through ElevenLabs (Eleven v4 Turbo for live replies; the model ID comes from config).
- Audio tags (for example `[sighs]`) are chosen by code from patient state, not by the LLM.
- The persona has a fixed voice ID per case.

**Acceptance:** median time from utterance commit to first audio is ≤2.0 s on the demo network (measured and reported).

#### E-05 Barge-in (P1)
If the student starts speaking while the patient is talking, playback stops. The event is logged with timestamps, since it may count as an interruption in feedback.

**Acceptance:** the interruption event appears in the trust ledger only if the student's speech began more than 300 ms before the patient finished a sentence (tunable).

#### E-06 Grounded replies (P0)
The turn pipeline (§9) runs on every utterance. The patient never states a clinical fact that isn't in the allowed set.

**Acceptance:**
- In test-student runs, 100% of delivered clinical statements map to fact IDs.
- Blocked attempts are counted and logged.

#### E-07 Progressive disclosure and chart release (P0)
Facts unlock according to tier and unlock conditions (topic asked, trust ≥ threshold, extra conditions). Chart items and artifacts release by their rules (on order, on topic, at visit start).

**Acceptance:** the disclosure log records `fact_id`, turn, condition met and trust at the time.

#### E-08 Narrated physical exam (P0)
- The student says what they examine ("I'm going to listen to your lungs").
- The intent classifier maps it to a catalog maneuver; the approved finding appears in the left panel and the chart.
- Ambiguous requests get a clarifying prompt rather than a guess.

**Acceptance:** maneuvers outside the catalog get "that exam isn't available in this case", never an invented finding.

#### E-09 Lab and test orders by voice (P1)
"Can we check her A1C?" releases the result if the case allows it, or "not available" otherwise.

**Acceptance:** orders are logged as actions for feedback.

#### E-10 Repeat detection (P1)
If the student asks for a fact already disclosed, the patient reacts in character ("I already told you that"). Logged.

#### E-11 Personal cues (P0)
Cases can include rapport cues (Walter's dinner club, the depression patient's dog). Following up on one is a trust event; ignoring a cue the patient raised is logged as a missed cue.

#### E-12 Hidden trust (P0)
Trust is never shown during the encounter. It is revealed in the debrief (F-04).

#### E-13 End encounter and documentation (P0)
- The student ends the encounter by voice ("I think we're done") with a confirmation, or with an End button.
- They then complete documentation in the case's template (PES, ADIME, SBAR or SOAP).
- Because the no-typing rule applies to the conversation, documentation is **dictated** by voice into template fields and the student can review the transcription. (Open question: see §15.)

**Acceptance:** the fabrication check (F-06) runs on submit.

#### E-14 Template fallback mode (P0)
If Bedrock fails or times out, replies use template phrasings of the allowed facts. The encounter continues, and the UI shows a small "simplified responses" notice.

#### E-15 Tavus avatar (iteration 2, P1)
- The center panel shows a Tavus replica.
- Tavus calls our OpenAI-compatible `/v1/chat/completions` endpoint (streaming).
- Our pipeline produces the reply; Tavus speaks it with ElevenLabs (`tts_engine: "elevenlabs"`, `tts_model_name` from config, `external_voice_id` per case).

**Acceptance:**
- The same grounding and disclosure logs exist for Tavus encounters.
- If v4 model IDs aren't accepted, config falls back to the newest accepted ElevenLabs model, with no code change.

#### E-16 3D body figure (P2)
A neutral, low-detail figure that highlights the region being examined. 2D fallback.

### 7.3 Longitudinal visits and decision tree (the twin)

#### L-01 Multi-visit cases (P1)
A case has ordered visits with a time gap. Each visit has its own facts, overrides and chart state.

#### L-02 Prior notes (P1)
A visit can include a prior note written "by" an earlier clinician (for example a referral from a hospitalist). The note may contain a deliberate, faculty-authored mistake for the student to catch. The student isn't told.

**Acceptance:** catching the mistake is an objective with expected actions.

#### L-03 Decision points (P1)
- Each visit has 2–4 yes/no decision points, defined as predicates over tagged encounter events (for example `asked_topic("mania_history") OR asked_topic("bipolar_family_history")`).
- Evaluated deterministically at the end of the visit.

**Acceptance:** results are stored with the evidence spans that satisfied or failed them.

#### L-04 Branch outcomes (P1)
- Each combination of outcomes maps to faculty-written state changes for the next visit (symptoms, values, mood, new facts).
- The AI may draft outcomes from objectives, but every outcome needs faculty approval.
- No probabilities; optional "common/rare" tags.
- This is how follow-ups differ per student without faculty editing each one: rules pick the authored outcome; the LLM never extrapolates the next state.

#### L-05 Tree editor (P1)
A node editor (React Flow) for decision points and outcomes, with validation (every leaf has an outcome).

#### L-06 Debrief tree with ghost paths (P1)
After a visit, show the taken path (solid) and the alternatives (dashed), each with "what would have happened" in one or two sentences.

#### L-07 Consequence timeline (P2)
An animated timeline between visits showing the authored changes.

#### L-08 Care timeline (P2)
- Faculty order a patient's care as nodes (role + visit). Each node is a student encounter or a simulated one; follow-ups may loop back to an earlier clinician.
- Every node before the graded encounter is fixed by faculty.
- A simulated node outputs the same artifacts as a student node (note, chart state), using only faculty-approved content.
- No multi-student chains (that drifts into C2).

### 7.4 Feedback (student)

#### F-01 Rubric scoring with evidence (P0)
- Score each of the 7 domains 1–4 or N/A using the official descriptors.
- Each score includes `strength_demonstrated`, `important_gap_or_missed_opportunity` and `safety_or_accuracy_concern`, each citing transcript spans.
- The total is out of 28. A **review flag** is set if domain 6 or 7 scores 1.
- Wording: "the total is a discussion aid, not a pass/fail grade."

**Acceptance:**
- Scores without at least one cited span for a non-N/A domain are rejected and regenerated.
- The span must exist verbatim in the transcript.

#### F-02 Elicited versus missed (P0)
For each objective: expected discoveries found (with the turn) and missed (with a suggested question).

#### F-03 Communication metrics (P1)
Countable metrics from intent tags:
- open versus closed question ratio;
- reflections;
- reflection-to-question ratio (MITI-style);
- jargon without explanation;
- interruptions (voice timing only);
- talk-time share.

#### F-04 Trust timeline (P0)
A chart of trust over turns. Each step links to its trust event and quoted span.

#### F-05 Strengths, improvements, next attempt (P0)
3 strengths, 3 improvements, and 1–3 specific suggestions for the next attempt, each linked to evidence.

#### F-06 Documentation check (P0)
- Compare documentation against the disclosure log.
- Flag claims never elicited (fabrication), key findings missing, and wrong values.
- For PES: check the problem, etiology and signs structure.

#### F-07 Safety catches (P0)
Case-specific safety items, such as Walter's NSAID use with heart failure and CKD. Missing one appears prominently and can feed domain 7 or domain 6.

#### F-08 Faculty override (P1)
Faculty can change any score or comment. The original and the change are both kept.

#### F-09 Audio playback with highlights (P1)
Play the encounter audio; feedback items jump to their timestamps.

#### F-10 Suicide-screening rule (P0, for the depression case)
- Asking about suicidal ideation is **never** penalized.
- An abrupt opener is a communication note only.
- Not asking is a domain-7 safety gap.

### 7.5 Faculty dashboard

#### D-01 Cohort assignment (P1)
Assign a case and role to a cohort.

#### D-02 Class gaps (P1)
Percentage of students missing each expected discovery; common wrong turns (decision-point outcomes); rubric distribution.

#### D-03 Student view (P1)
Per-student strengths and weaknesses over encounters; "recommended next case" chosen by a rule (the case whose objectives target the weakest domain), optionally stepping difficulty up or down by score. Framing: "precision medical education" (an existing term: Triola and Burk-Rafel, *Academic Medicine*, 2023).

#### D-04 Anonymized export (P1)
CSV or JSON export with student identifiers replaced by random IDs.

### 7.6 Platform

#### P-01 Encounter log (P0)
Every encounter stores:
- the transcript with timestamps;
- intent tags;
- disclosure log;
- trust ledger;
- verifier results;
- model IDs and prompt versions;
- latencies;
- the feedback output.

#### P-02 Text entry point for automation (P0)
A backend endpoint accepts a text utterance and runs the same pipeline. It's used by test students, evaluation scripts and the Tavus custom LLM. **It is not exposed as a typing box in the student UI.**

#### P-03 Config (P0)
- All model IDs, voices, region, resource names and thresholds live in config (`.env` plus one settings module).
- No secrets in the repo.

#### P-04 Deploy (P0)
- A cloud deploy on AWS (required by the rules).
- The README documents local setup and deploy steps.

#### P-05 Accessibility (P1)
- Captions are always on (the transcript).
- Color is never the only signal.
- Keyboard navigation for the Studio.

---

## 8. Data model

### 8.1 Case document (JSON, stored in Postgres JSONB, validated by Pydantic)
Sketch only; the Pydantic models in `backend/app/schemas/case.py` are the source of truth once written.

```json
{
  "case_id": "case_walter_greene",
  "version": 3,
  "status": "published",
  "title": "Walter Greene — nutrition counseling, HFrEF + T2DM + CKD3",
  "student_role": "dietitian",
  "setting": "outpatient nutrition clinic",
  "seed": 42817,
  "profile": {
    "name": "Walter Greene", "age": 72, "sex": "male", "pronouns": "he/him",
    "portrait_asset_id": "asset_walter_face",
    "voice_id": "<elevenlabs voice id from config>",
    "personality": {
      "traits": {"irritability": 0.7, "verbosity": 0.4, "humor": 0.6, "health_literacy": "low"},
      "example_lines": ["You look like a kid. They sending students now?"]
    },
    "difficulty_preset": "typical"
  },
  "facts": [
    {
      "id": "f_ibuprofen_use",
      "category": "medication",
      "text": "Takes ibuprofen 400 mg 2-3 times a week for back pain",
      "value": null,
      "codes": [{"system": "RxNorm", "code": "<rxcui>", "display": "ibuprofen 400 MG Oral Tablet"}],
      "tier": "discoverable",
      "unlock": {"topics_any": ["otc_medications", "pain", "medication_list"], "min_trust": 0},
      "belief": {"text": "Advil isn't really a medicine, it's just for my back"},
      "source": {"kind": "vhs_import", "ref": "medication_profile.over_the_counter_medications"},
      "status": "approved",
      "objective_ids": ["obj_med_integration"],
      "safety": true
    }
  ],
  "vitals": [{"name": "BP", "value": "158/92", "fact_id": "f_bp", "source": {"kind": "faculty"}}],
  "labs": [
    {"id": "lab_a1c", "loinc": "4548-4", "name": "Hemoglobin A1c", "value": 8.7, "unit": "%",
     "ref_range": {"low": 4.0, "high": 5.6, "source": "reference:<citation>"},
     "release": {"on": "order"}, "fact_id": "f_a1c", "source": {"kind": "faculty"}}
  ],
  "exam": [
    {"maneuver": "lung_auscultation", "finding": "Bilateral crackles at the bases",
     "fact_id": "f_crackles", "default": false}
  ],
  "artifacts": [
    {"id": "art_referral", "kind": "prior_note", "title": "Referral from PCP",
     "release": {"on": "visit_start"}, "license": null, "attribution": null}
  ],
  "objectives": [
    {"id": "obj_med_integration", "text": "Integrate medication management into nutrition care",
     "expected_discoveries": ["f_ibuprofen_use", "f_metformin_skipping"],
     "expected_actions": ["counsel_nsaid_risk"]}
  ],
  "rubric_id": "shp_patient_encounter_v1",
  "documentation_template": "PES",
  "trust": {"start": 0, "thresholds": {"reluctant": 3, "hidden": 6}},
  "visits": [
    {"id": "v1", "label": "Initial visit", "day": 0, "fact_overrides": [], "decision_points": []},
    {"id": "v2", "label": "3-month follow-up", "day": 90, "branches": []}
  ],
  "consistency_findings": [],
  "credits": []
}
```

### 8.2 Tables (SQLAlchemy)
- **`cases`**: `id`, `case_id`, `version`, `status`, `doc` (JSONB), `created_by`, `created_at`, `published_at`. Unique on (`case_id`, `version`).
- **`users`**: `id`, `name`, `role` (faculty/student), `cohort_id`. Sign-in through Cognito (`faculty` and `student` groups); production identity (school SSO) is out of scope.
- **`cohorts`**, **`assignments`**: `case_id`, `version`, `role`, `cohort_id`, `due`.
- **`encounters`**: `id`, `student_id`, `case_id`, `version`, `visit_id`, `status`, `started_at`, `ended_at`, `audio_asset_id`, `fallback_used`.
- **`turns`**: `id`, `encounter_id`, `idx`, `student_text`, `student_start_ms`, `student_end_ms`, `words` (JSONB), `intent` (JSONB), `allowed_fact_ids`, `reply_text`, `cited_fact_ids`, `verifier` (JSONB), `audio_tags`, `latency_ms` (JSONB).
- **`disclosures`**: `encounter_id`, `turn_id`, `fact_id`, `condition`, `trust_at`.
- **`trust_events`**: `encounter_id`, `turn_id`, `event_type`, `delta`, `span` (JSONB), `rule_id`.
- **`exam_actions`**, **`orders`**: `encounter_id`, `turn_id`, `maneuver` or `loinc`, `result_fact_id`.
- **`documentation`**: `encounter_id`, `template`, `fields` (JSONB), `check` (JSONB).
- **`feedback`**: `encounter_id`, `rubric_scores` (JSONB), `metrics` (JSONB), `elicited` (JSONB), `decision_results` (JSONB), `overrides` (JSONB), `model_versions`.
- **`assets`**: `id`, `kind`, `s3_key` or local path, `license`, `attribution`, `mime`.

### 8.3 Fixed vocabularies (in code, versioned)
- `topics.yaml`: the closed topic labels the intent classifier may output (`chief_complaint`, `onset`, `medication_list`, `otc_medications`, `diet_breakfast`, `alcohol`, `mania_history`, `suicidal_ideation`…).
- `maneuvers.yaml`: the exam catalog.
- `trust_events.yaml`: the event types, deltas and detection rules (see §9.3).
- `lay_lexicon.yaml`: jargon → lay terms for the patient-language check.
- `rubric_shp_v1.json`: copied from the sponsor file, with attribution.

---

## 9. Turn pipeline and determinism

### 9.1 Steps (per committed student utterance)
1. **STT commit.** Final text plus word timestamps (Scribe v2 Realtime, VAD commit).
2. **Intent classifier.** LLM at temperature 0 with structured output (JSON schema). Labels come only from the fixed vocabularies. Output:
   - `topics[]`;
   - `question_type` (open/closed/none);
   - `maneuver?`;
   - `order?`;
   - `empathy` (reflection, validation, none);
   - `jargon[]`;
   - `closing?`;
   - an `evidence` span for each label.

   Labels without a valid span are dropped.
3. **Disclosure engine (pure code).** Inputs: case version, visit state, trust, intent, history. Outputs:
   - `allowed_fact_ids`;
   - chart releases;
   - exam or order results;
   - trust events (rule-based, §9.3);
   - repeat flags;
   - the `audio_tags` choice.

   Deterministic: same inputs, same outputs. Unit-tested.
4. **Phraser.** LLM with persona plus `allowed_fact_ids` (and their texts and beliefs) plus recent turns. Returns JSON: `reply_text`, `cited_fact_ids`. Instructions:
   - lay language at the case's health literacy;
   - stay in character;
   - say "I don't know" or deflect for anything not allowed;
   - no lists or markdown.
5. **Verifier.**
   - (a) Every number in `reply_text` must equal a value in the cited facts (normalized).
   - (b) A clinical-claim check: an LLM judge with a structured yes/no per sentence, "supported by the cited facts?".
   - (c) Cited IDs ⊆ allowed IDs.
   - (d) Lay-language lint.

   On failure, regenerate once with the failure reason; then fall back to a template. All results are logged.
6. **TTS.** ElevenLabs (v4 Turbo for live), with audio tags from step 3.
7. **Client update.** Transcript line, chart releases, exam findings; everything logged (P-01).

Latency target: commit → first audio ≤2.0 s median. Measure each step. If too slow:
- run the classifier with a small fast model (Haiku-class);
- stream the phraser while verifying sentence by sentence;
- skip the LLM judge for replies with no clinical claims (small talk tagged by the engine).

### 9.2 Model use (config, verify IDs before use)
- **Classifier and verifier judge:** a fast Claude model on Bedrock (a Claude Haiku 4.5 inference profile was tested and works in us-east-1).
- **Phraser:** a fast model; upgrade only if quality demands it.
- **Studio drafting, consistency suggestions, feedback writing:** a stronger Claude model (Sonnet- or Opus-class on Bedrock). Check availability with `aws bedrock list-inference-profiles --region us-east-1`.
- Record model ID and prompt version on every logged call.

### 9.3 Trust events (initial list; Ahmad and Logan to refine)

| Event | Delta | Detection |
|---|---|---|
| Introduces self and role | +1 | intent `introduction` with span, within the first 3 turns |
| Follows up on a personal cue | +1 | the patient raised cue fact X in turn n; the student's topic matches X within 2 turns |
| Empathic reflection or validation | +1 | intent `empathy ∈ {reflection, validation}` with span |
| Explains a term in plain language | +1 | jargon used then explained (span) |
| Blunt sensitive question before any rapport | −1 | sensitive topic with trust < 1 and no preface span. **Never applied to suicide screening.** |
| Unexplained jargon | −1 | `jargon[]` not followed by an explanation within the turn |
| Interrupts | −1 | voice timing only (E-05) |
| Lectures or judges (MI-inconsistent) | −1 | intent `confront` or `warn_without_permission` with span |
| Ignores a raised cue | −1 | cue raised; not acknowledged within 2 turns |

Every event stores its span and rule ID. No span, no event.

### 9.4 Determinism and reproducibility
- Case seed for auto-fill and ranged values.
- Temperature 0 for the classifier and verifier.
- Prompts are versioned files in `backend/app/prompts/`, with the version recorded per call.
- Replaying a logged encounter's intents through the engine must reproduce the same disclosures and trust ledger (a test).

---

## 10. Architecture and stack

```
Browser (React + TS, Vite)
  ├─ Studio UI, Encounter UI, Debrief, Dashboard
  ├─ Mic → ElevenLabs Scribe v2 Realtime (WebSocket, single-use token from our backend)
  └─ REST/WebSocket ↔ FastAPI backend
FastAPI (Python)
  ├─ studio/ (drafting, intake, auto-fill, consistency, publish, VHS import)
  ├─ encounter/ (turn pipeline: classifier → engine → phraser → verifier → TTS)
  ├─ feedback/ (rubric scoring, metrics, documentation check, decision tree eval)
  ├─ dashboard/ (cohort aggregates, export)
  ├─ integrations/ (bedrock, elevenlabs, tavus, nlm_tables, s3)
  └─ openai_compat/ (/v1/chat/completions for Tavus)
Postgres (Docker locally → AWS RDS)   S3 (audio, images)   AWS Bedrock (Claude)
```

- **Backend:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, boto3, httpx, pytest.
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, React Flow (`@xyflow/react`), Recharts. React Three Fiber only for E-16.
- **Types:** frontend types are generated from FastAPI's OpenAPI schema (`openapi-typescript`). Don't hand-write API types.
- **Local dev:** `docker compose up` for Postgres; backend via `uvicorn`; frontend via `vite`.
- **Deploy:** five CloudFormation stacks in `infra/cloudformation/` (network, data, edge, auth, app), deployed in that order by `infra/scripts/deploy-stacks.sh` (see `infra/README.md`).
  - API: a t3.small EC2 instance in a public subnet, reachable only through CloudFront (`/api/*`). No ALB and no NAT gateway, to stay inside the $50/month budget.
  - Database: RDS Postgres (db.t4g.micro, the largest class AWS free plan accounts allow). One database shared by the deployed app and team laptops; reachable only from the backend and single team IPs.
  - Frontend: S3 + CloudFront, on the default `*.cloudfront.net` domain until the team has one (Route 53 and ACM come later).
  - Sign-in: Cognito user pool with email + password, optional Google, and optional email one-time codes (needs a verified SES identity). Added so faculty and students have real accounts at the demo instead of a role switcher.
  - Region and names in config.
- **Not now:** Redis, vector databases, Kubernetes, microservices.

## 11. API contracts (initial; FastAPI OpenAPI is the source of truth once built)

**Studio**
- `POST /api/studio/drafts`: `{description, student_role?}` → `{case_id, version, doc, gaps[]}`
- `POST /api/studio/drafts/{case_id}/intake`: `{answer, gap_id}` → `{doc, gaps[]}`
- `PATCH /api/studio/cases/{case_id}`: partial doc update → `{doc, consistency_findings[]}`
- `POST /api/studio/cases/{case_id}/autofill`: `{fields[]?}` → `{doc}`
- `POST /api/studio/cases/{case_id}/consistency` → `{findings[]}`
- `POST /api/studio/cases/{case_id}/preview`: `{skill_levels[]}` → `{runs[]}`
- `POST /api/studio/cases/{case_id}/publish` → `{version}`
- `POST /api/studio/import/vhs`: file → `{case_ids[]}`
- `GET /api/studio/lookup/{system}?q=`: ICD-10-CM, LOINC, RxNorm search (cached)

**Encounter**
- `POST /api/encounters`: `{assignment_id | case_id+version, visit_id}` → `{encounter_id, briefing, initial_chart}`
- `POST /api/stt/token` → a single-use Scribe realtime token (keeps the API key server-side)
- `WS /api/encounters/{id}/stream`: client sends `{type:"utterance", text, words[], start_ms, end_ms}` and `{type:"barge_in", at_ms}`. The server sends `{type:"reply", text, audio_url|audio_chunk, chart_releases[], exam_results[]}` and `{type:"notice", ...}`.
- `POST /api/encounters/{id}/utterance` (P-02 text entry point, same pipeline; for test students and scripts)
- `POST /api/encounters/{id}/end` → `{documentation_template}`
- `POST /api/encounters/{id}/documentation`: `{fields}` → `{check}`

**Feedback and dashboard**
- `GET /api/encounters/{id}/feedback`
- `PATCH /api/encounters/{id}/feedback` (faculty override)
- `GET /api/cohorts/{id}/summary`
- `GET /api/export?cohort_id=` (anonymized)

**Tavus**
- `POST /v1/chat/completions` (OpenAI-compatible, `stream: true`, SSE). Maps the conversation to `encounter_id` via a conversation property or header; runs steps 2–5; streams `reply_text`.

## 12. Voice and avatar details

- **STT:** ElevenLabs Scribe v2 Realtime over WebSocket from the browser, using a single-use token from our backend.
  - Settings: `commit_strategy=vad`; silence threshold about 1.0–1.5 s; VAD threshold about 0.4; word timestamps on.
  - Fallback: Amazon Transcribe streaming.
  - Partial text shows live in the transcript; only committed text goes to the pipeline.
- **TTS:** Eleven v4 Turbo for live replies; Eleven v4 for pre-rendered audio (for example narration).
  - Model IDs come from config; check the ElevenLabs developer docs for the exact strings.
  - Voice settings (stability, similarity, style, speed) are set per case.
- **Echo and barge-in:** browser `echoCancellation`, `noiseSuppression` and `autoGainControl` on; pause STT commits while the patient's audio plays only if echo causes false commits (test first); barge-in per E-05.
- **Tavus (iteration 2):**
  - A persona or PAL configured with the custom LLM (our `/v1/chat/completions`), TTS engine `elevenlabs`, `tts_model_name` from config, and `external_voice_id` per case.
  - Replica per demo case (Image-to-Replica if fast enough, otherwise a stock replica matched by age and sex).
  - Turn-taking and STT come from Tavus in this mode; our logs still capture the text Tavus sends.
  - **Verify first:** v4 model ID acceptance; audio-tag passthrough; latency; Persona API versus PAL API.
- **Consent:** the encounter start screen states that audio is recorded for feedback, and where it is stored. Recordings live in S3 under the encounter ID.

## 13. Repo layout (planned)

```
/AGENTS.md  /CLAUDE.md  /PRD.md  /context.md  /README.md
/.env.example
/docker-compose.yml
/backend/
  pyproject.toml
  app/
    main.py  settings.py  db.py
    schemas/ (case.py, encounter.py, feedback.py)
    models/ (SQLAlchemy tables)
    studio/ (drafting.py, intake.py, autofill/, consistency.py, vhs_import.py, publish.py)
    encounter/ (pipeline.py, classifier.py, engine.py, phraser.py, verifier.py, trust.py, exam.py)
    feedback/ (rubric.py, metrics.py, documentation.py, decisions.py)
    dashboard/
    integrations/ (bedrock.py, elevenlabs.py, tavus.py, nlm_tables.py, storage.py)
    openai_compat/
    prompts/ (versioned .md/.txt prompt files)
    vocab/ (topics.yaml, maneuvers.yaml, trust_events.yaml, lay_lexicon.yaml)
    data/ (rubric_shp_v1.json, loinc_subset.json, nhanes/ extracts, credits.md)
  alembic/
  tests/
  scripts/ (seed_golden_cases.py, run_test_students.py, eval_grounding.py, eval_agreement.py)
/frontend/
  package.json  vite.config.ts  tailwind.config.ts
  src/
    api/ (generated types + client)
    components/ (shared UI)
    features/ (studio/, encounter/, debrief/, dashboard/)
    lib/ (audio, stt client)
    styles/ (tokens)
/cases/ (golden case JSON files, reviewed)
/docs/ (architecture notes, credits, validation results)
```

## 14. Design direction

- **Vibrant color; gradients, depth and illustration allowed** (updated 2026-10-10); not blank white, not enterprise; still professional.
- Use a warm, light, non-white base (or a dark base) with 3–4 saturated accent colors, assigned to meaning:
  - one for the patient and voice;
  - one for chart and data;
  - one for feedback;
  - one for warnings.
- Colors are design tokens in one file.
- Encounter layout as in E-02.
- Large type for the transcript; captions always visible.
- No photorealistic generated people in the UI other than the sponsor portraits (cropped) and the Tavus replica.
- **Direction is explored with local image mockups** (GPT Image via Codex, never committed); the shipped UI is real React/Tailwind screens. Pick one palette with the team before polishing.

## 15. Validation and metrics (what the video can honestly claim)

| ID | Metric | Method |
|---|---|---|
| V-01 | **Grounding rate** | Run N scripted test-student encounters per golden case (including adversarial students who ask for things not in the case). Report the percentage of delivered clinical statements mapped to facts, the number of attempted unsupported statements blocked by the verifier, and the fallback rate. |
| V-02 | **Disclosure accuracy** | For a labeled set of turns, compare engine releases to the expected releases. Report precision and recall of fact release; target zero premature hidden-tier releases. |
| V-03 | **Grader agreement** | Ahmad hand-scores about 15–20 transcripts on the 7 domains. Report weighted Cohen's kappa (quadratic) per domain and overall, with confidence intervals. Logan to confirm the sample size and method. Report honestly even if low. |
| V-04 | **Difficulty calibration** | Novice, competent and expert test students × 3 presets; discoveries and trust reached. "Difficult" must reduce discoveries (report effect size; a permutation test if N allows). |
| V-05 | **Latency** | Median and 90th percentile for commit → first audio; per-step breakdown. |
| V-06 | **Cost per encounter** | Bedrock tokens + ElevenLabs characters/minutes (+ Tavus minutes). |
| V-07 | **Consistency checker recall** | On the 8 imported VHS profiles, the number of issues flagged versus a hand-checked list. |

Every number in the video must come from a script in `backend/scripts/` with its output saved in `docs/validation/`.

## 16. Demo and video plan (content, not timing)

1. **Problem** (with the motion-graphics intro).
2. **Faculty creates the antibiotic-mother case live:** described by voice, guided intake, auto-fill with sources, consistency check, publish.
3. **Encounter with that new patient** (the Key Demonstration), briefly.
4. **Hero encounter with Walter Greene:** hands-free voice, trust-gated disclosure, narrated exam, the ibuprofen catch, chart filling in.
5. **Debrief:** rubric with evidence, trust timeline, missed items, documentation check.
6. **Depression case:** visit 2 changes based on visit 1; tree with ghost paths.
7. **Class dashboard.**
8. **One dense, precise minute on architecture and validation numbers** (V-01–V-05).
9. Close.

Teammates appear in picture-in-picture as they explain their parts; captions throughout. Before every recording, run the test students on the golden cases (the "golden-case gate").

## 17. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Latency too high for natural voice | Fast models, streaming, skip the judge on non-clinical replies, measure per step (V-05). |
| Echo makes the always-on mic transcribe the patient | Echo cancellation, headphones, ignore commits overlapping playback unless barge-in, test early. |
| Tavus doesn't accept v4 model IDs | Config fallback to the newest accepted ElevenLabs model. |
| Image-to-Replica is slow | Pre-build demo faces; stock replicas for live-created cases. |
| LLM invents facts | Engine + verifier + fallback; V-01 proves it. |
| Grader disagrees with Ahmad | Report the actual kappa; show faculty override; frame as a discussion aid (as the rubric itself says). |
| Brief says "support text interaction" but the UI has no typing | Open question (§18). The pipeline has a text entry point (P-02) and live captions. |
| Clinical errors in golden cases | Ahmad reviews; seek an SHP or dietetics reviewer at the mentor session. |
| Licensing problems | A credits file; only licensed assets; no scraping. |
| Personal AWS account costs | Budget alerts; small instances; tear down after the event. |
| C2 clone perception | Lead with C1's Key Demonstration; C2 ideas are supporting features. |

## 18. Open questions
See `context.md` §15 for the full list with owners. The ones that block the build:
1. **Text interaction versus no typing.** Is a hidden text fallback (accessibility) acceptable, or none at all? Does documentation dictation count as "no typing"?
2. **Depression case visit-2 states** (Ahmad).
3. **Tavus account and v4 model ID test.**
4. **Hosting choice** (JJ).
5. **Product name:** working name Rounds; confirm.

## 19. Credits and licenses (to maintain in `backend/app/data/credits.md` and the README)
- VHS sample profiles: `joeljames270/virtual-patient-profiles-sample` (Hugging Face), CC BY 4.0.
- Rutgers SHP sample materials (rubric, CSV, portraits, syllabus): provided by the hosts for the event.
- NHANES (CDC): public domain US government data.
- ICD-10-CM (CDC/CMS); RxNorm (NLM); LOINC (Regenstrief, license terms apply); NLM Clinical Tables API.
- PTB-XL (PhysioNet), CC BY 4.0.
- Radiopaedia images: per-case license (usually CC BY-NC-SA), attribution per image.
- MakeHuman (CC0 output), if the 3D figure is built.
- ElevenLabs, Tavus, AWS Bedrock (Anthropic Claude models): commercial APIs used under their terms.
- Open-source libraries: listed from `pyproject.toml` and `package.json`.
