# context.md — Full Project Context

This file holds everything decided, researched, and discussed about this project so far, so that anyone (or any AI coding session) starting from a fresh clone has the same context as the original planning sessions. It is long on purpose.

- **What to build:** `PRD.md`.
- **How to work in this repo:** `AGENTS.md`.
- **What everything means:** the Shared Dictionary in section 14 of this file.

Working product name: **Rounds** (chosen 2026-10-10; may still change). Docs keep writing **[Product name]** so a rename is one edit.

---

## Contents
1. The event, rules, and judging
2. The team and how we work
3. Working preferences (how to communicate, what to avoid)
4. How the idea was chosen (including rejected ideas)
5. The TwinVerse track and both challenge briefs
6. What the challenge videos said
7. The sponsor dataset (SHP zip) in detail
8. The product idea, in one page
9. Every feature the team agreed on (with origin)
10. Team document review (comments + answers)
11. Key design decisions and their reasons
12. Cases: hero, longitudinal, live-created, presets
13. Technology, vendors, accounts, costs
14. Shared Dictionary (terms + writing rules)
15. Open questions and owners
16. Status log

---

## 1. The event, rules, and judging

### The event
- **Event:** Rutgers Health Hack 2026, the 4th annual. It runs Oct 9–11, 2026 at the Rutgers Robert Wood Johnson Medical School and RWJ University Hospital in the new Helix building, New Brunswick, NJ.
- **Hosts:** Rutgers Health and RWJBarnabas Health. AWS is the main technology partner.
- **Sponsors:** AWS, ElevenLabs, Microsoft, Cigna, NJM Foundation, Anakin and others.
- **Size:** 441 registered participants. The median age is about 21, and about half are first-time hackers.
- **Background mix:**
  - 61% AI, CS or IS backgrounds;
  - 14% medicine;
  - 12% other engineering;
  - 12% business.

### Rules
These come from the kickoff and the brief.
- **Team size** is 4–8.
- **Code must be written after kickoff.** No pre-written code may be reused; knowledge may.
- **Cloud services are required.**
- **Credits:** every third-party tool, library, and dataset must be credited, and its license respected.
- **Synthetic data is allowed,** but how it was made must be documented. No real patient information may be exposed, ever.
- **Intellectual property** created at the event is shared with the university.
- **Submission** is on Devpost by **Sunday Oct 11, 12:00 PM**, with no extensions. It includes:
  - a demo video of **about 4 minutes maximum**;
  - documentation (solution details, tools used, install/deploy steps);
  - a repo link;
  - a **working prototype**.

### Judging
- **Format:** Zoom judging on Sunday afternoon. The video is played, then judges ask questions for 2–3 minutes. There is no live demo, so everything shown is pre-recorded.
- **Scoring is per track and holistic.** All challenges in a track compete for the same top 3; there are 2–3 prizes per track.
- **Judges see C1 and C2 submissions together,** so the app's purpose must be obvious within seconds.
- **The five event-wide judging criteria:**
  1. innovation and creativity;
  2. technical implementation (code quality, architecture, data integration);
  3. impact and relevance to healthcare;
  4. presentation and documentation;
  5. feasibility and scalability in a real healthcare setting.
- **The C1 brief's own evaluation considerations:**
  - architecture and reusability;
  - quality and clinical validity of patient profiles;
  - technical innovation;
  - user experience;
  - quality of the clinical encounter;
  - effectiveness and explainability of feedback.
- **Key Demonstration (C1 brief):** "a faculty member will create a new patient profile using the team's Patient Studio and then conduct an encounter with that newly created patient … without patient-specific code changes." Judging is a video, so this moment must be in the video, recorded for real and unedited in substance.
- **Separate ElevenLabs prize:** "Best Project Built with ElevenLabs" (3 months of Scale tier per member). It stacks with track prizes. Voice must fit naturally, never be forced.
- **Saturday mentor session:** 20–25 minutes with 10–15 mentors (about a third clinicians). Bring a short presentation and a list of questions. Mentors tend to say "no" to safe ideas, so take creative risks before it.

### What the kickoff speakers valued
1. **Practicality.** "Great idea, but where do you get the food?" Show how a school or hospital would actually use it.
2. **Work backward from the customer.** Name the user and their problem.
3. **AI supports judgment; it does not replace it.** Both the Sevaro founder and the RWJUH president said this.
4. **RWJUH already runs AI:** a deterioration-index agent, radiology queue triage and about 65 agents. Don't pitch what they already have.
5. **Deskilling.** The president cited a study where gastroenterologists detected less after their AI was removed. Tools that make people *better*, not dependent, hit a nerve.
6. **"Give clinicians time back to listen to patients."** This is the emotional core for this audience.
7. **Production intent.** A 2025 project is moving to production, and the hosts said this year's challenges "are designed to be pushed to production if they are good."

### Last year's winner (calibration)
"Lunara" (2025 women's health track, same team) won with:
- a clear 3-sentence problem setup;
- a clean feature walkthrough;
- a minute on how it was built and validated: a TF-IDF plus logistic regression model, a precision/recall chart, and a Monte Carlo permutation test.

Lesson: judges reward a clear story, a polished walkthrough and a real validation chart. This year's field is stronger, and questions are live, so **only claim what can be shown**.

---

## 2. The team and how we work

### Roles

| Person | Role |
|---|---|
| Safwan | PM. Runs the original planning chat; the AWS account used for the first draft is his. |
| Anuj (Discord: bluesea) | PM. Owner of the GitHub repo. Owns the video pipeline (motion-graphics intro in After Effects plus ElevenLabs narration). |
| JJ (Jairik) | AWS and backend. Suggested the tech stack and the shared dictionary. |
| Logan | ML. Owns the **case-tree engine and evaluation statistics** and is confident in it ("tree-based ML is literally my specialty"). |
| Ahmad | 4th-year medical student; clinical reviewer. Has done narrated physical exams and OSCEs, and built something similar before. Older notes misspell this name as "Amad". |
| Anye | Contributor. Placement open: presets, image library, video or UI. |
| Kareem | Biomedical engineering freshman. Placement open, same options. |

- **Video speakers:** Anuj, Safwan, JJ, Logan and Ahmad for sure; Anye and Kareem optional.
- **Style:** each person pops in on camera to explain their part (picture-in-picture bubbles, "Yonder" style), with captions. The motion-graphics intro runs 15–30 s.

### Workflow (agreed)
1. **One context, one spec, one first draft.** A single planning chat gathered all context and wrote these docs, so the first prototype is cohesive. Splitting the build across many chats from the start produces apps that don't fit together.
2. **Handoff happens through the repo, not chat messages.** `AGENTS.md`, `PRD.md` and `context.md` (this file) let any teammate's Claude session start with full context.
3. **Then parallel work.** People work on branches with pull requests into `main`, each owning one area. Fixed contracts (API shapes, case schema, folder layout) let people work without blocking each other.
4. **Docs are neutral.** They never refer to "the coder" as anyone in particular and never take sides between teammates.
5. **AWS.** The first draft is built on Safwan's personal AWS account. Hackathon AWS credits had not arrived at the time of writing.
   - Region and resource names live in one config file, so moving to an official team account later is a config change.
   - Each person gets their own IAM user. Root logins are never shared.
6. **Secrets.** API keys live only in a local `.env` file (never committed, never pasted in chat). `.env.example` lists the variable names.

### Mobile
Not needed. If a phone view is ever shown, record a simulator or a phone-sized browser window. No TestFlight.

---

## 3. Working preferences

These apply to people and AI sessions alike.

- **Be completely honest.** Push back with reasons. Ask targeted questions addressed to the right person.
- **Explain technical and medical terms the first time.** Use real terms for depth, but no unexplained abbreviations.
- **No hour-by-hour timelines.** AI-assisted building is fast; give sequencing only.
- **No Q&A prep sheet** for judging. The team will know the product.
- **Don't second-guess the After Effects video pipeline.** It's handled.
- **Docs and agent output must avoid "AI slop" wording** (see the banned list in section 14).
- **UI direction** (Anuj owns UI/UX and frontend):
  - Vibrant and colorful. **Updated 2026-10-10: gradients, depth and illustration are allowed;** the earlier "no gradients, not a showpiece" rule is lifted.
  - Not blank white, not a mundane enterprise look, not brutalist. It must still read as a professional tool.
  - Encounter layout: the **patient in the center** (Tavus video later; a circular profile photo in iteration 1), **live transcript below**, **useful information on the left and right**.
  - No photorealistic generated people in mockups. The first ChatGPT image mockups were rejected as "atrocious" (all-white UI, weird hyperrealistic people).
  - **Updated 2026-10-10:** image mockups are back for exploration only (GPT Image via Codex, short prompts, the patient always an abstract placeholder). They stay local in `design/` and are never committed. Once the direction is settled, the UI is built as real React/Tailwind screens.
  - Small, functional 3D (Blender models) is welcome only where it serves a purpose (see section 9).
- **Iteration 1 voice:**
  - No live video.
  - **The student always speaks; no typing and no push-to-talk.**
  - The microphone is always live with live transcription.

---

## 4. How the idea was chosen

### Before the briefs (all rejected; knowledge kept, code not reused)
- **GlucoTwin** (a personal glucose digital twin using ReplayBG). Testing showed next-day prediction fails on real patients. Rejected.
- **ResponseMirror** (replaying a night of NYC EMS ambulance data).
  - Data findings: 41% of calls held; 3,321 low-acuity calls upgraded; 1,012 waited more than 20 minutes.
  - Rejected: it's a retrospective replay, not a true digital twin under the NASEM (National Academies) definition.
- **Weight twin.** Rejected: easy for judges to attack.
- **Night-shift fatigue twin.** An external hostile review killed it. It duplicates existing tools (2B-Alert / Peak Alert), relies on an unvalidated model combination, and its reaction-time test (PVT) does not equal impairment.
- **Pulse physiology engine** (Kitware, Apache 2.0) for a virtual patient whose vital signs respond to treatment. It loaded in Docker, but was dropped once the written C1 brief made clear the core is Studio + encounter + feedback, not physiology. It remains a possible future extra.

### Track ranking after the briefs
TwinVerse > Sevaro > Wellness Reimagined > Ops Unleashed.
- **TwinVerse:**
  - the highest skill bar, so fewer beginner teams;
  - fits the team (a medical student is the literal end user);
  - voice and avatar are official stretch goals, which fits ElevenLabs;
  - makes the best video.
- **Sevaro:** equally hard, real data, but drier to demo.
- **Wellness:** easy challenges, so it will be crowded. Glucose prediction is graded on accuracy, and our tests showed that is hard.
- **Ops:** the easiest briefs (an LLM plus a form), so the most crowded.

### Challenge choice
- C2 was argued for first: less crowded, more architecture.
- The team chose **C1 as the core**, because it suits the group and Ahmad has built something similar. C1 also has the cleaner judging moment.
- After the sponsor dataset arrived, C1 was reconfirmed. The C2 materials became very prescriptive (a named example system "CareThread", a full sample case, a 100-point sheet), so expect many near-identical C2 builds.
- We **borrow selected C2 ideas**: SBAR-style documentation, longitudinal visits, repeat detection, preview with test students, score override, anonymized export.
- The team explicitly allowed "a good meshing of the two, as long as it fundamentally works."

---

## 5. The TwinVerse track and both challenge briefs

Track tagline from the event site: build intelligent digital twins that "simulate patients, care pathways, and health systems."

### C1 — The Virtual Patient Encounter System (our core)
Summary from the brief: a reusable AI virtual-patient system built from structured patient profiles, going "beyond a simple chatbot" by letting students interact with the patient while seeing the chart. It must handle many patients with **no patient-specific code**.

#### 1. Patient Studio (faculty)
Faculty must be able to:
- create a profile (structured or descriptive);
- add knowledge sources (papers, guidelines, protocols);
- attach artifacts (lab reports, ECGs, X-rays, CT scans, prior notes);
- define when information and artifacts become available;
- review and correct generated information;
- check internal consistency;
- approve and publish;
- maintain multiple reusable profiles.

#### 2. Encounter Interface (student)
A split screen, with the patient interaction on one side and the dynamic chart on the other. It must:
- run any published profile;
- support text, with voice and avatar encouraged;
- keep a consistent identity and conversation state;
- show prior notes, structured information and artifacts;
- release information progressively;
- **prevent invented clinical facts**;
- keep a record of what was disclosed.

#### 3. Encounter Feedback (student)
Driven by faculty learning objectives. It must:
- show findings elicited and missed;
- assess interview structure and sequencing;
- assess communication, empathy, clarity and professionalism;
- be specific and explainable, linked to the encounter;
- give strengths and areas to improve;
- give actionable next steps;
- log every encounter.

#### Clinical validity
- History, medications, diagnoses, labs and artifacts stay consistent.
- No unsupported information is presented as fact.
- Dynamic findings use faculty-approved or validated information.

#### Levels
- **Base:** all of the above.
- **Stretch:**
  - real-time voice;
  - **avatar (marked "ideal")**;
  - multimodal interaction;
  - adaptive behavior;
  - advanced memory and state;
  - richer artifacts;
  - integration APIs (Canvas, the learning platform).

#### Resources and deliverables
- **Resources:** synthetic personas, existing "VHS" prompts, sample encounters, learning objectives, example documentation templates, AWS Bedrock.
- **Deliverables:** a working prototype (profile creation, a complete encounter, feedback), the repo, the demo video, and a 4-minute pitch covering the solution, architecture, technical approach and educational value.

### C2 — The Connected Care Journey (interprofessional education, IPE)
- **Core:** one virtual patient across 3 or more encounters with different professions. The student plays one role; AI plays the patient and the other clinicians.
- **Shared patient state with provenance** for every fact: who said it, when, in which encounter, and in what role.
- It separates established facts from uncertainties and conflicting interpretations. Earlier encounters must visibly influence later ones.
- **Enhanced level:**
  - SBAR handoffs (Situation, Background, Assessment, Recommendation);
  - TeamSTEPPS-aligned communication;
  - explainable, evidence-based grading of the student's communication (not a black-box number).
- **Stretch:** non-linear collaboration, huddles, closed-loop communication, live reconciliation.
- **Final output:** one coordinated care plan, not stapled-together lists.
- **The SHP zip adds:**
  - 13 core features and a 100-point rubric;
  - a full sample case: Mr. Rivera, 78, recovering from a hip fracture;
  - an example system, "CareThread";
  - 5 clinician profiles: Brian Lee (emergency physician), David Bennet (cardiologist), Nasir Mahmoud (PharmD), Priya Narang (hospitalist), Tasha Dunbar (registered dietitian);
  - ideas such as a repeat score, failure injection, preview mode and anonymized export.

---

## 6. What the challenge videos said

The hosts' AI-generated explainers. Every team has them, so copying them makes us one of many.

- **C1 video:**
  - Pitches a "platform-resident" digital-twin simulation versus "sterile" text chatbots.
  - Describes a split screen with artifacts released progressively.
  - Describes a "**mismatch detector**": the patient says they take their meds, but the labs disagree.
  - Calls for logged, explainable feedback mapped to objectives.
  - Describes a decoupled "universal engine" where faculty author JSON/YAML profiles and publish with no code.
  - Slogan: "**the LLM drives the chat, the templates drive the truth.**"
  - It also borrows C2's Denise story, shared state, provenance and SBAR. So the hosts themselves blend C1 and C2.
  - At the end, a bystander calls "shared understanding" a buzzword.
- **C2 video:**
  - Denise, 58, has new type 2 diabetes and early kidney involvement. She sees a primary care doctor, a nephrologist and a nutritionist. Notes are bad, medications conflict, labs aren't forwarded, and her personal goal (no medication changes before her daughter's wedding) is ignored.
  - The mission is a multi-agent simulation with an evolving shared state, provenance and SBAR handoffs.
  - Grading must be explainable "behavioral traces", not "communication score 75/100".
  - The final output is one coordinated plan.
- **How we use them:**
  - **Don't headline the same hooks** (Denise, the mismatch detector, the "LLM drives the chat" slogan).
  - Include the mismatch idea, but **prove grounding visibly** instead of just claiming it.
  - Our phrasing in the pitch may echo their concepts (continuity is the floor, not the goal), never their words.

---

## 7. The sponsor dataset (SHP zip) in detail

The zip is "RU Health Hack 2026 SHP (public)". SHP is the **Rutgers School of Health Professions**: dietetics/nutrition, speech-language pathology, Medical Laboratory Science and other fields. **The likely faculty judges are SHP, not medical school.** The students they picture are health-professions students, so the system must be **profession-neutral**: the student's role is set per case.

### C1 folder contents
- **`faculty-provided-sample-patient-details.csv`:** 8 short patient rows (name, age, background, gender, notes, image path, personality, race/ethnicity, summary).
  - Some rows **disagree with the full profiles** on Hugging Face. For example, Dominic Rivera is a gunshot-wound recovery in the CSV but poorly controlled diabetes in the full profile, and Nisha Patel is MS in the CSV but diabetes in the full profile.
- **8 portraits:** AI-generated, 1024×1536. Walter's image has two staff members behind him, so crop to the face before any avatar use.
- **Full profiles:** Hugging Face `joeljames270/virtual-patient-profiles-sample`, **CC BY 4.0** (free to use with attribution). This is the hosts' existing "VHS" format.
  - The file is concatenated pretty-printed JSON, not true JSONL, so parse it with a `raw_decode` loop.
  - Top-level keys: `patient_overview`, `demographics`, `clinical_profile`, `medication_profile`, `nutrition_profile`, `psychosocial_profile`, `information_disclosure`, `learning_opportunities`, `metadata`.
  - `information_disclosure` has four tiers:
    - `initial_information`: volunteered;
    - `discoverable_information`: said if asked;
    - `reluctant_information`: needs rapport;
    - `hidden_information`: needs deep trust.
  - `learning_opportunities.opportunities[]`: each has `learning_objective`, `expected_discoveries[]` and `possible_patient_reactions[]`.
  - The dataset admits some generation errors.
- **The 8 patients** (full-profile primary diagnosis). Almost all are **nutrition-counseling** cases built around the Nutrition Care Process, PES statements and motivational interviewing.
  - Walter Greene, 72: uncontrolled type 2 diabetes, HFrEF, CKD 3.
  - Marcus Ramirez, 59: heart failure (NYHA stage C) and new type 2 diabetes.
  - Yvette Armstrong, 64: stage II hypertension and type 2 diabetes.
  - Omar Sinclair, 45: dyslipidemia.
  - Nisha Patel, 29: type 2 diabetes.
  - Wyatt Nelson, 18: type 2 diabetes, obesity, dyslipidemia.
  - Vladko Bareche, 31: type 2 diabetes; also smoking, alcohol and cocaine.
  - Dominic Rivera, 22: type 2 diabetes in the full profile; gunshot recovery in the CSV.
- **Official rubric** ("Patient Encounter Performance Rubric", PDF and JSON). See below.
- **Speech-language pathology rubric** (SPLP 6510, pediatric hearing simulation, 100 points). It's a case-specific checklist:
  - introduce yourself (10);
  - needs assessment (30);
  - review the audiogram (30);
  - realistic expectations and empathy (30).

  This proves rubrics vary by program, so rubric import matters.
- **MLSC 4329 Hematology II syllabus** (Medical Laboratory Science). A source for "syllabus → learning objectives".
- **Kaggle pathology results dataset:** `pareshbadnore/diagnostic-pathology-test-results`. Not yet checked: it needs a Kaggle login, and the license is unknown.
- **Hugging Face `Postzeun/Patient-Doctor`:** about 60k dialogues, **no license listed**. Do not use it without a license.

### The official rubric (verbatim structure)
- **Instructions:** "Rate the student's performance as supported by the encounter. Rate only what the scenario makes possible to observe; use N/A when a criterion is not appropriate."
- **Scale:** 4 Strong (consistent, effective, appropriate), 3 Competent (usually effective; minor gaps), 2 Developing (partly effective; important gaps), 1 Unsafe or absent (not demonstrated, misleading, or harmful), or N/A.
- **The 7 domains:**

| # | key | name | review if 1 |
|---|---|---|---|
| 1 | opening_and_purpose | Opening and purpose | no |
| 2 | rapport_respect_empathy | Rapport, respect, and empathy | no |
| 3 | information_gathering | Information gathering | no |
| 4 | listening_and_response_to_cues | Listening and response to cues | no |
| 5 | explanation_and_shared_decisions | Explanation and shared decisions | no |
| 6 | clinical_reasoning_and_synthesis | Clinical reasoning and synthesis | **yes** |
| 7 | professionalism_safety_closure | Professionalism, safety, and closure | **yes** |

- **Score-4 descriptors:**
  1. Introduces self and role; agenda; confirms the immediate concern; sets expectations.
  2. Attentive, nonjudgmental, culturally responsive; acknowledges emotion; builds trust.
  3. Open questions, focused follow-up, clarification, sequencing; explores history, context, risks and goals.
  4. Recognizes cues, uncertainty and changes in the story; doesn't interrupt or ignore.
  5. Clear explanation; checks understanding; invites questions; incorporates preferences and readiness.
  6. Identifies key findings; separates relevant from irrelevant; red flags and uncertainty; plausible assessment.
  7. Boundaries; privacy; communicates limitations; summarizes; next steps, follow-up or escalation.
- **Scoring:** max 28. "Use the total as a discussion aid, not a pass/fail grade. A score of 1 in professionalism, safety, or clinical reasoning should trigger review even when the total is high."
- **Evidence fields:** `strength_demonstrated`, `important_gap_or_missed_opportunity`, `safety_or_accuracy_concern`.

### Walter Greene (likely hero) — key facts from the profile
- **Who he is:**
  - 72, African-American, retired janitor, widowed, lives alone, high-school diploma, Medicare plus Medicaid.
  - His sister lives across the country.
  - He values self-sufficiency and hates being treated as "too old".
- **Clinical profile:**
  - **Diagnoses:** uncontrolled type 2 diabetes (15 years); HFrEF with EF 40%; hypertension; CKD stage 3; coronary artery disease, with CABG 5 years ago; recurrent heart-failure admissions ("frequent flier").
  - **Allergies:** penicillin (hives), shellfish (anaphylaxis), sulfa.
  - **Vitals:** BP 158/92, HR 78, RR 18, 37.0 °C, SpO2 96%.
  - **Anthropometrics:** 5'8", 198 lb, BMI 31.2, waist 43".
  - **Labs:** HbA1c 8.7%, fasting glucose 165, BUN 28, creatinine 1.6, Na 136, K 4.1, LDL 125.
  - **Exam findings:** apical murmur, bilateral crackles, 2+ pedal edema, mild gum disease.
- **Medications:**
  - metformin 500 mg twice a day (skips because of nausea);
  - lisinopril 20 mg (thinks it's only for blood pressure);
  - "Epirocil (Eplerenone)" 25 mg (forgets; worries about fainting);
  - melatonin;
  - **ibuprofen 400 mg as needed, 2–3 times a week for back pain.**
- **Nutrition:**
  - fried and salty food; sweet tea and soda with every meal;
  - skips breakfast, big lunch;
  - **dinner club twice a week** at a high-sodium chain;
  - canned soups.
- **Psychosocial:**
  - sarcastic and grumpy, especially toward students ("You look like a kid");
  - opens up if listened to;
  - loves "shop talk";
  - fears dying, being a burden and losing independence;
  - in the precontemplation or early contemplation stage of change.
- **Disclosure tiers:**
  - **Initial:** complains about pills, says his doctor sent him, jokes about the student.
  - **Discoverable:** dinner club, **ibuprofen**, thinks HF and diabetes are the same "sick thing", soda, skipped breakfast, no one cooks, trouble getting to the store, guilt about his sister.
  - **Reluctant:** feels he failed his wife and kids.
  - **Hidden:** scared about his future; has unused savings he's afraid to spend.
- **Learning objectives:**
  - apply the Nutrition Care Process;
  - write a PES statement;
  - evidence-based interventions;
  - integrate medication management;
  - motivational interviewing;
  - lifestyle barriers;
  - interprofessional and community resources.
- **Teaching gold:** ibuprofen (an NSAID) with heart failure and CKD is a real safety issue. NSAIDs worsen fluid retention, raise blood pressure and strain the kidneys.

**Inconsistencies in Walter's profile** (the consistency checker should catch these; frame them respectfully as "worth faculty review"):
1. The PES objective says "labs show high Na and low K", but his labs are Na 136 and K 4.1, both normal.
2. "Epirocil" is not a real brand name. The generic it names, eplerenone, is real (brand name Inspra).
3. "Lost 10 lbs unintentionally in the last month" conflicts with "poor weight loss despite attempts to eat less".
4. He's "widowed" with a sister as the main support, but one reaction mentions "my kids". Minor, but checkable.

---

## 8. The product idea, in one page

[Product name] is a virtual patient encounter system for health-professions education.

**Faculty side.** Faculty build a patient in a **Patient Studio** by describing them in plain language, typed or spoken. The system drafts a complete profile using **statistically grounded defaults** and asks guided follow-up questions. Faculty review, correct and publish it. Every clinical fact is an approved **fact** with an ID and a source.

**Student side.**
1. The student gets a **briefing card**: role, goal and doorway vitals, as in a real OSCE.
2. They **talk to the patient by voice, hands-free.** The microphone is always live with live transcription; no typing.
3. The patient sits in the center: a profile photo in iteration 1, a Tavus live video avatar later. The transcript runs below. The left panel holds the visit goal, referral note and exam; the right panel holds the chart, which fills in as facts are discovered.
4. The patient reveals information through **trust-gated disclosure**, and it's deterministic. Code decides which facts can be said. The AI only **puts approved facts into words**, and a verifier blocks anything unsupported.
5. The student examines the patient by **narrating** ("I'm going to listen to your heart"), and the faculty-approved finding appears.
6. Afterwards, the student writes **documentation** (a PES statement, SBAR or SOAP, as faculty choose). It's checked against what was actually discovered.

**Feedback.** The debrief uses the **official 7-domain rubric**. Every score cites the exact transcript moments as evidence. It includes:
- an elicited-versus-missed list;
- the **trust timeline** (what raised or lowered trust, with quotes);
- countable communication metrics, such as open versus closed questions and the reflection-to-question ratio from motivational interviewing;
- the **decision tree**: the path the student took versus the "ghost" paths not taken.

**Longitudinal visits.** The patient returns weeks later in a state determined by faculty-authored branches. That makes it a true patient twin: state that changes over time because of the care given.

**Class view.** Faculty see the whole class: which findings were missed most, common wrong turns, and per-student strengths and weaknesses.

**Honest statistics.** We prove the system, not student learning:
- **grounding rate:** the percentage of patient statements traced to approved facts, and the number of unsupported statements blocked;
- **disclosure accuracy:** facts released only when their conditions were met;
- **grader agreement:** with Ahmad's hand scores;
- **difficulty calibration:** using scripted AI test students.

---

## 9. Every feature the team agreed on

Origin codes: **T1** = brainstorm transcript 1; **T2** = transcript 2; **DS** = from the dataset review; **DOC** = the team feedback document; **C2** = borrowed from Challenge 2; **ADD** = proposed during planning and accepted. Priorities are in `PRD.md`.

### Patient Studio
- Plain-language description (typed or spoken) auto-fills the whole profile with sensible values; faculty review and adjust. (T1)
- **Guided intake:** the Studio asks follow-up questions only for missing or risky fields, with a visual of the case assembling and a completeness ring. Called "Jarvis" in the doc; the product name is "guided intake". (DOC)
- **Required baseline** for every patient (vitals, review of systems, social history), so any student question has an approved answer. Fixes the "broken leg patient, student fixates on HIV" problem. (T1)
- **Structured fields:**
  - labs on sliders;
  - imaging;
  - allergies;
  - medications;
  - psychiatric history (prior diagnoses, hospitalizations, medications tried and response, past suicidal or homicidal ideation, substance use);
  - living situation and psychosocial details;
  - personality traits. (T1, DOC)
- **Labs:**
  - CBC, BMP, magnesium, phosphorus, A1C, glucose and troponins.
  - Not all are required per case; sensible baselines are prefilled.
  - Grouped by common orders (panels), with a lookup for esoteric labs. (DOC)
- **Coded pickers:** diagnoses map to ICD-10-CM (plus SNOMED if licensed), labs to LOINC, medications to RxNorm. (T1, ADD, DOC)
- **Statistically grounded auto-fill:**
  - Values come from population distributions (NHANES) and guideline thresholds, never an AI guess.
  - Linked values stay consistent (eGFR from creatinine via CKD-EPI 2021; anion gap; A1C ↔ estimated average glucose).
  - Faculty override everything. (T2, DOC)
- **Faculty-set test values:** a fixed value or a range, seeded so replays are identical. (T1, DOC)
- **Truths:** faculty-approved facts; every patient statement links to one. "Lean into this hard." (T1)
- **Unreliable narrator:** faculty enter both the chart truth and what the patient believes (chart BP 120/80, patient says "I think it was 140 over 100"). (T2)
- **Personality** as structured traits plus example lines (the VHS `possible_patient_reactions` serve as examples). (T2)
- **Difficulty and presentation presets,** from "straightforward, knows their symptoms" to "difficult historian, can barely talk". Each preset is a set of explicit parameters with statistical calibration. (T1, DOC)
- **Preset library plus build-your-own:** presets are editable, or start from scratch. (T1)
- **Imaging and ECG library** from openly licensed, labeled images, matched by description ("ECG with ST elevation"). No real patient data. Credit every license. Radiopaedia was suggested (see the licensing note in section 13). (T1, DOC)
- **Trust-gated disclosure rules,** set per fact. (T1, DS)
- **Consistency checker** for contradictions and unknown drugs (catches Walter's errors). (DS)
- **VHS import:** one click loads the hosts' 8 profiles. Pitch line: "drop-in compatible with your existing VHS". (DS)
- **Syllabus → learning objectives:** attach a syllabus, extract objectives, map feedback to them. (DS)
- **Rubric import:** the official 7-domain rubric is the default; other rubrics (such as the SLP checklist) can be added. (DS)
- **Preview with AI test students** before publishing. Also feeds the statistics. (C2)
- **Knowledge sources** (papers, guidelines, protocols) attached to a case. (Required by the C1 brief.)
- **PrimeKG** (Harvard's disease–drug–phenotype knowledge graph) as a *suggestion* source, for example flagging drug–disease conflicts. Stretch; check the license. (DOC)

### Encounter
- The instructor **assigns a patient plus a role** ("You are the dietitian / cardiologist"). (T1)
- **Briefing card** (OSCE "doorway information"): who, your role, your goal, **doorway vitals**. Not gamified; readable by someone who has never seen the app. (T1, DOC)
- **Split screen** in our layout: patient center, transcript below, left panel (goal, referral, exam), right panel (the progressive chart). (T1, brief, UI preference)
- **Always-on voice:** live transcription; no typing; no push-to-talk. (Team decision)
- **Narrated physical exam:** the student says what they examine and the approved finding appears. Coverage includes palpation, auscultation, percussion, inspection, anterior and posterior drawer, Lachman, McMurray, empty can, Tinel, valgus and varus stress, and more. Every maneuver has a normal default. (T1, DOC)
- **Personal cues** that test rapport, like Ahmad's dog example or Walter's dinner club. Graded on whether the student follows up or rushes past. (T1)
- **Repeat detection:** "I already told you that." (C2/DS)
- **Trust hidden during the encounter** (no gamifying), revealed in the debrief. (T1)
- **Tavus avatar** in the center (iteration 2), with our backend as the brain. (Team decision)
- **3D body figure (optional):** a neutral, low-detail mannequin that highlights the region being examined during narration. Built in Blender from an open base mesh. Cut first if time is short. (DOC)

### Longitudinal and consequences (the twin)
- **Follow-up visits:** the patient returns; the clinician reads the previous note, sees new symptoms and reassesses. (T1)
- **Flawed earlier visit:** a prior AI-written note contains a deliberate mistake the student must catch, without being told. (T1)
- **Consequence timeline:** after the student acts, an animated timeline shows what happens next. (T1)
- **Decision tree** (Logan's chess analogy):
  - States, actions and outcomes. Content comes from faculty-authored branches; the AI only words them.
  - Shown after the encounter: taken path versus ghost paths.
  - **No outcome percentages.** (T1)

### Feedback
- A clear final score, about four charts, and bullet points on what went well and what didn't. (T1)
- Grounded in how OSCEs are graded: history elements (onset, location, duration, character, associated symptoms, radiation, timing), rapport and case-specific checklist items. (T1)
- **Official 7-domain rubric,** with evidence fields and the review flag for a score of 1 in domains 6 or 7. (DS)
- **End-of-encounter documentation** (PES, ADIME, SBAR or SOAP, chosen by faculty), graded, with a **fabrication check**: anything documented that was never actually discovered is flagged. (T1/C2/DS)
- **Motivational-interviewing metrics** (MITI-style counts: reflection-to-question ratio, percentage of open questions). (DS)
- **Faculty can override any score.** (C2)
- **Audio playback with highlights:** feedback anchored to timestamps; play back with highlighted moments. (DOC)
- "Put numbers behind this": a defined set of ways to be right or wrong, so every score is measurable. (T1)

### Faculty dashboard
- Assign a case to the whole class; see the percentage that missed each item and common wrong turns. (T1)
- Per-student strengths and weaknesses; "recommended next case" based on weak areas. (T1, trimmed)
- **Anonymized data export.** (C2)

### Demo and process
- **A bulletproof demo through golden cases,** not faking: fully detailed cases, the AI only words things, and scripted test students are run before every recording. (T1)
- Real performance statistics shown in the video. (T1)
- **Take creative risks before the mentor session;** bring questions. (T1)

### Cut or deferred (and why)

| Idea | Decision |
|---|---|
| Pulling billing codes from real patients | Deferred. A coded picker covers it; Synthea synthetic patients are the safe version. |
| 15–20 fully reviewed presets | 3 golden cases in depth plus about 8–12 Studio-generated cases, labeled "draft" or "reviewed". |
| Fully adaptive "challenge them optimally" | v1: presets plus "recommended next case". |
| Physical-exam buttons | Narration first; buttons break immersion. |
| Visible trust meter during the encounter | Hidden; revealed in the debrief. |
| Prompt Cowboy (prompt generator) | Not needed. |
| AI clinicians talking to each other (C2 top tier) | Cut. AI-written prior visits cover the story. |
| Outcome percentages ("dies 12% of the time") | Cut. Faculty-written paths; optional "common" or "rare" tags. |
| AAMC Core EPAs as the main framework | Replaced by the official SHP rubric. Can be shown as a secondary view. |

---

## 10. Team document review (comments + answers)

The team returned the planning summary as a Word document with comments and inline edits. The resolutions are below.

### Comments
1. **(JJ) "Exam findings and lab results" — expand.**
   - An exam finding is a structured entry per body system and maneuver, with a normal default and a faculty-set abnormal value.
   - A lab result has a LOINC code, value, unit, reference range, range source and date, and is released when ordered (as a panel).
   - Both are facts with IDs, and statements and chart entries cite those IDs.
2. **(JJ) Decision tree — auto-fill? Representation? Presentation?**
   - **Representation:** factored decision points per visit. 2–4 yes/no conditions are evaluated deterministically from tagged encounter events; each outcome applies faculty-written state changes to the next visit. This avoids combinatorial explosion.
   - **Auto-fill:** the Studio can draft branches from the learning objectives, but faculty must approve or rewrite every outcome.
   - **Presentation:** a node editor for faculty; hidden from students during the encounter; in the debrief, a solid taken path, dashed ghost paths and "what would have happened".
3. **(JJ) Guided "Jarvis" intake with a visualization.** Accepted as the centerpiece of the live-creation demo.
4. **(JJ) Grounded methodology for lab sliders.**
   - Values come from NHANES age- and sex-matched distributions where available, otherwise a published reference interval with its source named.
   - Guideline rules shift values: diabetes is A1C ≥6.5% (ADA); CKD stage 3 is eGFR 30–59 (KDIGO).
   - Linked values are computed: eGFR via the CKD-EPI 2021 equation (race-free); anion gap = Na − (Cl + HCO₃); estimated average glucose = 28.7 × A1C − 46.7.
   - A seed per case makes values reproducible. Overrides are labeled "faculty-set".
5. **(JJ) Statistical or deterministic backing for difficulty presets.**
   - A preset is a parameter vector: hidden-fact count, unlock thresholds, tangentiality, red herrings, health literacy, affect.
   - Calibrate with scripted test students at three skill levels; "Hard" must measurably reduce discovery.
6. **(JJ) Faculty-set values with basic statistics.** A fixed value or a seeded range; repeat measures vary within bounds; the source is shown.
7. **(Ahmad) The trust meter is where hallucinations happen.**
   - Agreed. Trust is a **deterministic ledger** of events from a fixed list. Each event needs a quoted transcript span, or it doesn't count.
   - "Interruption" is only measured from voice timing.
   - The tagger is scored against Ahmad's labels.

### Inline additions by the team (accepted)
- The lab list and panel grouping with lookup.
- The psychiatric-history fields.
- **Radiopaedia** for imaging (with licensing caveats).
- **PrimeKG** for prefill suggestions.
- **Doorway vitals** on the briefing card.
- **Physical-exam maneuver coverage** (the list in section 9). The doc lists both "mcmurphy" and "mcmurray's", which are almost certainly the same test (McMurray), and "Tinnel's" should be "Tinel's". Ahmad to confirm.
- **Audio player with highlighted timestamps** in the debrief.
- **Hero depression case:**
  - an improved PHQ-9 as a trap (the sentence is unfinished; read as "the PHQ-9 improved, which looks like success but masks hypomania");
  - side-effect counseling (GI, sexual dysfunction);
  - the patient hides suicidal ideation until rapport is built, and the student "should not immediately lead off with 'Are you having thoughts of harming yourself?'";
  - she mentions her dog;
  - a DIGFAST overview in the debrief.
- **Antibiotic case:** the mother insists her child "always gets better after antibiotics"; negative strep swab; low Centor score.
- **Diabetes case:** A1C 8%; assess psychosocial factors.
- **JJ's note:** a shared "dictionary" so agents avoid slop words, and so everyone uses the same terms. This is section 14.

### Planning pushback recorded
- **Never penalize asking about suicide.** "Asked abruptly as the opening question" is a communication note, not a deduction. Otherwise the tool could teach students to delay safety screening.
- **Antibiotic case clinical check (Ahmad):**
  - IDSA guidance says children with clear viral features (cough, runny nose) generally shouldn't be strep-tested.
  - In children, a negative rapid strep test is usually confirmed with a throat culture.
  - Centor criteria are adult-derived; the McIsaac version adjusts for age.
- **Rubric:** the doc still mentions AAMC EPAs, but the official SHP rubric is primary.
- **Two sentences in the doc were cut off:** "ideally we can bang down everything else but also…" and "Also just so we are on the same page." Their endings are unknown.

### Team discussion 3 (2026-10-10): roles, rubrics, care timeline
Partly mistranscribed audio; these are the conclusions.
- **Learner role = profession or specialty + training level.** Medicine is hierarchical: medical student → resident → attending (the student presents to the resident, the resident to the attending). A medical student is expected to know general medicine, not to act as a specialist, so cases shouldn't assign "cardiologist" to a medical student. Other professions (dietetics, nursing, SLP) keep their own roles.
- **Assignments:** faculty assign a set of cases at once (patients A, B and C), all through the same pipeline; the next assignment covers new material.
- **Score only with the sponsor's rubrics:** the 7-domain encounter rubric (the file's scale is 1–4 or N/A; it was misremembered aloud as 1–5), the case-specific SLP checklist, and C2's SBAR and TeamSTEPPS items. Nothing invented.
- **Everything before the graded encounter is fixed by faculty.** The student is examined in an exact state the faculty defined; a simulation must never land them somewhere the faculty didn't author.
- **Care timeline (sketch, `design/reference-timeline-sketch.jpg`, local only):** faculty order the nodes of a patient's care (role + visit). Each node is a student encounter or a simulated one. A simulated node outputs the same artifacts as a student node (note, chart state), but only faculty-approved content. Follow-ups can loop back to an earlier clinician. C1 itself is one encounter; ordered clinicians come from C2, so we borrow the shape lightly and skip multi-student chains.
- **Faculty-rework worry:** if every student handles visit 1 differently, faculty would have to hand-edit each patient's visit 2. The answer is the factored decision points with faculty-written outcomes (`PRD.md` L-03, L-04): rules select the authored outcome, so no per-student editing and no LLM extrapolation.
- **Fast faculty input:** the LLM only sorts free text into defined fields (for example "BP 140/90" → systolic and diastolic), which is the Studio's guided intake.
- **Scale vision:** faculty build many cases (about 50); after each encounter the system explains what went wrong and routes the student to the faculty case that targets their weakest domains, stepping difficulty up or down by score. Difficulty can come from noise or missing information in the history and prior notes. This matches **"precision medical education"**, an existing term (Triola and Burk-Rafel, *Academic Medicine*, 2023): cite it rather than claim it.
- **Real-world gap noted, out of scope:** real clinicians rarely have every prior clinician's records in one place. That is C2's data problem; our prior notes are faculty-written.

---

## 11. Key design decisions and their reasons

1. **C1 core plus selected C2 features.** C1 is less likely to be cloned from a template, has the cleaner judging moment and fits the team. C2 pieces add depth without the multi-agent sprawl.
2. **The LLM never decides facts.**
   - Code decides what may be said (disclosure engine); the LLM phrases it; a verifier checks it.
   - Numbers must match fact values exactly.
   - There's a template-only fallback if the AI service fails.
   - This is the answer to "how do you know it isn't hallucinating?"
3. **The deterministic trust ledger** answers Ahmad's hallucination concern. Every change cites a transcript span.
4. **Factored decision tree,** not an exhaustive tree. It's small, testable and still displayed as a tree.
5. **No outcome probabilities.** Clinician judges would attack them; faculty-written paths are defensible.
6. **Measure the system, not learning gains.** We can't honestly claim "students learn 40% faster"; we can show grounding, disclosure accuracy, grader agreement and difficulty calibration.
7. **The official SHP rubric is the default.** It's the judges' own instrument.
8. **Profession-neutral roles,** because the SHP audience includes dietetics, SLP and lab science.
9. **VHS-compatible schema:** our case format is a superset of theirs, so their data imports directly.
10. **One case document per patient (JSON),** validated by a schema and stored as Postgres JSONB. Simpler than dozens of tables; it matches the brief's "JSON/YAML profile" framing.
11. **The avatar is only a face; our backend is the brain.** If the avatar vendor's built-in AI talks, we lose the grounding guarantee and the disclosure log.
12. **All-ElevenLabs voice stack** (Scribe v2 Realtime in, Eleven v4 / v4 Turbo out). It fits the product naturally and the ElevenLabs prize.
13. **Iteration 1 has no video** (a circular photo placeholder), but the reply endpoint is designed to be wrapped for Tavus later.
14. **Image-generated mockups are for exploration only** (local, never committed); the shipped UI is coded React/Tailwind.
15. **Reliable, not fake, demo:** golden cases plus scripted test-student runs before each recording.

---

## 12. Cases

### Recommended roles for the three demo cases
Recommended during planning; the PMs had no preference.

| Role in the demo | Case | Why |
|---|---|---|
| **Hero encounter** (the main walkthrough) | **Walter Greene**, from the sponsor dataset. Student is a dietetics student. | The judges wrote him. It uses their rubric and data, the ibuprofen safety catch, the dinner-club rapport cue, motivational interviewing, and the consistency checker catching his profile errors. |
| **Longitudinal / decision-tree showcase** | **Ahmad's depression case** (21-year-old woman, 2 visits). Student is a primary-care clinician. | The clearest "twin": visit 2 depends on visit 1, and the tree shows "what if you had screened for mania". |
| **Live "faculty creates a patient" demo** | **The antibiotic-demanding mother** (pediatric viral upper respiratory infection). | A single visit, one clear objective, describable in 2–3 sentences, so it fits a 60-second live creation. |

Additional case: **the diabetes patient hiding skipped insulin** (A1C 8%, labs contradict her story, psychosocial causes). Recommended student role: dietitian. It's a preset and a mismatch example.

### Depression case draft (Ahmad to correct and finish)
- **Visit 1.** A 21-year-old woman with several weeks of depressed mood. Scored items:
  - screens for bipolar disorder before starting an antidepressant (asks about past mania or hypomania, family history; DIGFAST elements);
  - asks about suicidal ideation, but not as an abrupt opener;
  - counsels on side effects (GI upset, sexual dysfunction);
  - mentions the boxed warning for increased suicidal thinking in young adults (under 25) and plans close follow-up.
- **Hidden:** passive suicidal ideation, disclosed only after rapport. Personal cue: **her dog**.
- **Visit 2 (three weeks later).** State depends on visit 1:
  - If bipolar screening was skipped and an SSRI was started: hypomanic features (less need for sleep, talkativeness, impulsivity). The **PHQ-9 has improved**, which is the trap: a lower depression score looks like success.
  - Either way: did the student check for suicidal thinking again?
- **Debrief:** the tree with ghost paths ("what would have happened if you'd asked about mania") and a short DIGFAST overview.
- **Open for Ahmad:** which choices change the patient versus only the score; the visit-2 state for each combination; finishing the PHQ trap sentence.

### Walter branches (counseling outcomes, faculty-written)
- **3-month follow-up:**
  - If the student addressed ibuprofen, sodium and dinner-club barriers in a way he accepted (motivational interviewing, not lecturing): improved.
  - If lectured: unchanged, and back in the hospital (consistent with "frequent flier").
- Outcomes are written by faculty or Ahmad, not generated.

### Presets
- 3 golden cases in full depth (reviewed by Ahmad).
- Plus about 8–12 cases generated through our own Studio (including the 8 VHS imports), labeled **draft** or **reviewed**.
- About 10 presets in the library, with 1–3 shown in the video.

---

## 13. Technology, vendors, accounts, costs

### Stack
Suggested by JJ and accepted, with additions. Details are in `PRD.md` section 10.
- **Backend:** Python, FastAPI, Pydantic, SQLAlchemy 2, Alembic.
- **Frontend:** TypeScript, React (Vite), Tailwind CSS, reusable components (shadcn/ui), React Flow (tree), Recharts (charts), optionally React Three Fiber (3D figure).
- **Database:** local Postgres (Docker Compose), moving to **AWS RDS** by changing `DATABASE_URL`.
- **Config** from `.env`. The code is modular and not over-engineered.
- **AI:** AWS Bedrock (Claude models; optional Nova Micro for the fast tier) via boto3. A Claude test call through Bedrock succeeded in us-east-1. Model IDs are configured, not hard-coded. Nova Micro is a speed-focused candidate; run the golden-case audit before using it in a demo.

### Voice and avatar
- **Iteration 1** (no video), always-on voice:
  - Speech-to-text: **ElevenLabs Scribe v2 Realtime** over WebSocket, with VAD (voice activity detection) committing each utterance after silence. Word-level timestamps are available. ElevenLabs reports roughly 150–200 ms latency; measure it ourselves.
  - Fallback: Amazon Transcribe streaming.
  - Text-to-speech: **ElevenLabs Eleven v4 Turbo** for live replies (about 100 ms median inference reported). Eleven v4 (released Sept 28, 2026) for non-live audio.
  - v4 supports inline audio tags (for example `[sighs]`). Our engine picks tags deterministically from the patient's state; the AI does not choose them.
- **Iteration 2:** **Tavus** Conversational Video Interface.
  - Tavus handles the student's audio and turn-taking and calls **our** backend as a "custom LLM" through an OpenAI-compatible `/chat/completions` endpoint with streaming.
  - Tavus's TTS layer supports `tts_engine: "elevenlabs"` with `tts_model_name` (any ElevenLabs model ID) and `external_voice_id`. A private voice needs our ElevenLabs API key.
  - **Unverified:** whether Tavus accepts the v4 / v4 Turbo model IDs yet (v4 is about two weeks old; Tavus's docs example shows `eleven_turbo_v2_5`), and whether inline v4 audio tags pass through. Test before relying on either. Fallback: the newest ElevenLabs model Tavus accepts.
  - Tavus docs show both a Persona API and a newer "PAL" API, which disagree on TTS defaults. Check which applies when the account is set up.
  - **Image-to-Replica** (May 2026) builds a face from one image. Conversion time is unknown; if slow, faces are pre-built for demo cases and a stock face is matched by age and sex for live-created patients.
  - **Raven perception** can pass the student's visible cues (for example looking away) to our backend. Use it only if grounded and quoted, the same as other evidence.
  - **Cost:** about 25 free minutes, then roughly $0.32–0.37 per minute. Expected use is about 100–200 minutes.
- **Alternatives considered:** HeyGen LiveAvatar, Anam (one-photo avatar API), Simli, and TalkingHead (an open-source 3D browser avatar as a free fallback).

### Sponsors
- **ElevenLabs:** one month of Creator tier for participants, plus the separate prize.
- **Anakin:** a one-month coupon for web scraping, no prize. Use only if scraping truly fits; currently it doesn't.

### AWS
- Region: **us-east-1**.
- A monthly cost budget ("hackathon-50", $50, with alerts at 80% actual and 100% forecast) protects the personal account. Billing data can lag about a day.
- Services: Bedrock; RDS (Postgres); S3 (audio, images); hosting for the API and frontend; Transcribe (fallback).
- **Hosting:** decide at deploy time. The simplest options are a small EC2 instance running Docker Compose for the API, plus S3 + CloudFront or Amplify Hosting for the frontend.

### Data and licensing notes (must be credited)
- **VHS profiles:** CC BY 4.0. Credit `joeljames270/virtual-patient-profiles-sample`.
- **NHANES** (CDC): US-government public data.
- **ICD-10-CM:** public (CDC/CMS).
- **RxNorm** via NLM RxNav, and **LOINC** (free with license terms and attribution).
- **SNOMED CT** requires a UMLS license (free for US users, but someone must register). Skip unless obtained.
- **NLM Clinical Tables** search service for ICD-10-CM, LOINC and drug autocomplete. Cache results locally so the demo doesn't need the internet.
- **Radiopaedia:** most content is CC BY-NC-SA, set per case. No bulk scraping. Hand-pick about 10–20 images and record each case's attribution.
- **PTB-XL ECG dataset** (PhysioNet, CC BY 4.0): labeled 12-lead ECG signals we can render ourselves.
- **PrimeKG:** check the license before use.
- **MakeHuman** base meshes: CC0 output, suitable for the 3D figure.
- **Synthea:** synthetic patient generator (open source). Deferred.
- **Not usable without a license:** HF `Postzeun/Patient-Doctor`. Kaggle pathology results: unknown license, unchecked.

---

## 14. Shared Dictionary

### 14a. Terms

Use these exact meanings in code, UI, docs and conversation.

| Term | Meaning |
|---|---|
| **Case** | One complete patient package authored in the Studio: profile, facts, disclosure rules, exam findings, labs, artifacts, objectives, rubric, decision points, and visits. Stored as one JSON document. |
| **Profile** | The descriptive part of a case (demographics, history, personality). VHS-compatible. |
| **Fact** | The smallest approved unit of clinical or personal truth, with a stable ID (`f_…`), text, optional value/unit, source, and disclosure rule. The patient may only state facts. |
| **Truth** | The team's earlier word for a fact. Prefer "fact" in code. |
| **Belief** | What the patient thinks is true, when it differs from the chart (the "unreliable narrator"). It's linked to a fact; it's never a fact itself. |
| **Disclosure tier** | `initial` (volunteered), `discoverable` (said if asked), `reluctant` (needs rapport), `hidden` (needs deep trust). Taken from VHS. |
| **Unlock condition** | The rule that makes a fact sayable: topic asked plus a trust threshold, plus any extra condition. |
| **Disclosure log** | A per-visit record of which facts were released, when, why (which condition), and in which turn. |
| **Trust** | A number per visit that changes only through trust events. Hidden from the student during the encounter. |
| **Trust event** | A change in trust from a fixed list (for example "responded to personal cue +1"). Must cite a transcript span. |
| **Turn** | One student utterance plus the patient's reply. |
| **Span** | An exact quoted piece of the transcript (turn ID plus character range or timestamps), used as evidence. |
| **Intent tag** | The classifier's structured reading of a student utterance: topics asked, question type (open/closed), exam maneuver, empathy or reflection, order, and so on. From a closed label set. |
| **Phraser** | The LLM step that turns allowed facts into the patient's words, in character. |
| **Verifier** | The check that every clinical statement in a reply is supported by its cited facts and that numbers match exactly. Fails closed. |
| **Template fallback** | A canned phrasing of allowed facts used when the phraser fails or the AI is unavailable. |
| **Grounding rate** | The percentage of patient statements traced to approved facts. Reported along with how many unsupported statements were blocked. |
| **Exam maneuver** | One physical-exam action from the catalog (for example "cardiac auscultation", "Lachman test"). |
| **Finding** | The approved result of a maneuver (normal default or faculty-set abnormal). |
| **Lab panel** | A group of lab results ordered together (CBC, BMP and so on). |
| **Artifact** | An attached document or image: lab report, ECG, X-ray, CT, prior note. |
| **Release rule** | When a chart item or artifact becomes visible (on order, on topic, at visit start, or on trust). |
| **Chart** | The right-hand panel: what the student has discovered or been given so far. Each entry shows its fact source. |
| **Briefing card** | The pre-encounter card: patient, role, goal, doorway vitals (the OSCE "doorway information"). |
| **Role** | The profession the student plays in this case (dietitian, SLP, physician, nurse, PT, PA…). |
| **Visit** | One encounter session within a case. Longitudinal cases have several. |
| **Patient state** | The patient's condition at the start of a visit (symptoms, values, mood, beliefs). Changes between visits through branches. This is the "twin". |
| **Decision point** | A yes/no condition evaluated at the end of a visit from tagged events (for example "screened for bipolar before an SSRI"). |
| **Branch / outcome** | The faculty-written state change applied to the next visit when a decision point resolves a certain way. |
| **Taken path / ghost path** | In the debrief tree: what the student's choices led to, versus the authored alternatives. |
| **Preset** | A reusable starting configuration: a case template or a difficulty setting. |
| **Difficulty preset** | A parameter vector (hidden-fact count, unlock thresholds, tangentiality, red herrings, health literacy, affect). |
| **Golden case** | A fully authored, clinically reviewed case used for the demo and tests. |
| **Test student** | A scripted AI student at a fixed skill level, used for preview, calibration and statistics. |
| **Rubric** | The scoring instrument. Default: the official 7-domain SHP rubric (4/3/2/1/N/A, max 28, review flag). |
| **Review flag** | Set when domain 6 (clinical reasoning) or 7 (professionalism/safety) scores 1. |
| **Evidence fields** | `strength_demonstrated`, `important_gap_or_missed_opportunity`, `safety_or_accuracy_concern`. |
| **Documentation** | What the student writes after the encounter, in a faculty-chosen template (PES, ADIME, SBAR, SOAP). |
| **Fabrication check** | Flags documented claims that were never discovered in the encounter. |
| **Consistency check** | Flags contradictions within a case (labs versus text, unknown drugs, conflicting history). |
| **Guided intake** | The Studio's question-asking assistant that fills gaps after a plain-language description. |
| **Auto-fill** | Statistically grounded defaults for values the faculty didn't specify. Every value carries a source label. |
| **Cohort** | A class or group of students assigned the same case. |

### Clinical and education abbreviations (always expand on first use in UI and docs)
- **OSCE:** Objective Structured Clinical Examination (station-based practical exams with standardized patients).
- **SP:** standardized patient (a trained actor).
- **SHP:** Rutgers School of Health Professions.
- **VHS:** the hosts' existing virtual-patient system and profile format.
- **IPE:** interprofessional education.
- **NCP:** Nutrition Care Process.
- **PES:** Problem, Etiology, Signs/Symptoms (the dietitian's diagnosis statement).
- **ADIME:** Assessment, Diagnosis, Intervention, Monitoring/Evaluation (the dietetics note format).
- **SBAR:** Situation, Background, Assessment, Recommendation (a handoff format).
- **SOAP:** Subjective, Objective, Assessment, Plan (a clinical note format).
- **MI:** motivational interviewing.
- **MITI:** Motivational Interviewing Treatment Integrity (a coding system with countable targets).
- **TeamSTEPPS:** an evidence-based teamwork framework.
- **HFrEF:** heart failure with reduced ejection fraction.
- **CKD:** chronic kidney disease.
- **eGFR:** estimated glomerular filtration rate.
- **CKD-EPI:** the kidney-function equation (2021 race-free version).
- **NSAID:** non-steroidal anti-inflammatory drug (for example ibuprofen).
- **SSRI:** selective serotonin reuptake inhibitor (a common antidepressant).
- **PHQ-9:** a 9-item depression questionnaire.
- **SI/HI:** suicidal or homicidal ideation.
- **DIGFAST:** a mnemonic for mania symptoms: Distractibility, Indiscretion/impulsivity, Grandiosity, Flight of ideas, Activity increase, Sleep deficit, Talkativeness.
- **URI:** upper respiratory infection.
- **Centor / McIsaac:** strep-throat probability scores (McIsaac adjusts for age).
- **IDSA:** Infectious Diseases Society of America.
- **NHANES:** the CDC's National Health and Nutrition Examination Survey.
- **ICD-10-CM:** the diagnosis code set.
- **SNOMED CT:** a clinical terminology.
- **LOINC:** lab test codes.
- **RxNorm:** drug codes.
- **EHR:** electronic health record.
- **CBC:** complete blood count.
- **BMP:** basic metabolic panel.
- **CMP:** comprehensive metabolic panel.
- **A1C / HbA1c:** 3-month average blood-sugar marker.
- **eAG:** estimated average glucose.
- **ROS:** review of systems.
- **EPA:** Entrustable Professional Activity (AAMC; a medical-school framework).

### Tech terms
- **STT:** speech-to-text.
- **TTS:** text-to-speech.
- **VAD:** voice activity detection; decides when someone has stopped speaking.
- **Barge-in:** the student speaks while the patient is talking; the patient stops.
- **CVI:** Tavus Conversational Video Interface.
- **Replica:** a Tavus face.
- **Persona/PAL:** a Tavus configuration of layers (LLM, TTS, perception).
- **Bedrock:** AWS's hosted model service.
- **RDS:** AWS's hosted Postgres.
- **JSONB:** Postgres binary JSON column.
- **Alembic:** database migrations.
- **OpenAPI:** the machine-readable API description FastAPI generates; frontend types are generated from it.

### 14b. Writing rules (for people and AI agents)
- **Plain, specific, short.** Say what a thing does, with a concrete example.
- **Expand an abbreviation the first time** it appears on a screen or in a doc.
- **No hype or filler. Banned words and phrases** in docs, UI copy, commit messages and patient dialogue:
  - "delve", "leverage" (as a verb), "seamless/seamlessly", "robust", "cutting-edge", "game-changer", "revolutionize", "unlock the power", "harness", "empower", "elevate", "streamline" (unless literal);
  - "in today's fast-paced world", "it's important to note", "it's worth noting";
  - "a testament to", "navigate the complexities", "tapestry", "realm", "synergy", "holistic" (except when quoting the judging format);
  - "state-of-the-art", "next-generation", "best-in-class";
  - "AI-powered" as a standalone selling point.
- **No unsupported claims.** Never say "HIPAA compliant", "clinically validated", "students learn X% faster" or "accurate" without a measured number and its method.
- **Patient dialogue is lay language** matched to the case's health literacy:
  - no clinical jargon the patient wouldn't know;
  - no lists, no markdown;
  - short spoken sentences, contractions allowed.
- **UI copy addresses the user directly** and stays neutral and professional. No gamified language (no "XP", "level up", "streak").

---

## 15. Open questions and owners

1. **Ahmad (hero / longitudinal case):** which choices change the patient versus only the score; the visit-2 state for each combination; finish the PHQ-9 trap sentence; confirm the depression case details.
2. **Ahmad (suicide screening):** rubric wording so asking early is never penalized and only an abrupt opener is noted.
3. **Ahmad (antibiotic case):** viral features (no test needed) or a negative rapid test? What counts as a good outcome?
4. **Ahmad:** confirm the exam-maneuver list (McMurray duplicate, Tinel spelling); confirm Walter's ibuprofen catch and the inconsistencies; share any OSCE rubric (public options: the Kalamazoo checklist, the Master Interview Rating Scale); hand-score about 15–20 transcripts for grader agreement.
5. **PMs:** confirm the case roles in section 12. Find a dietetics or SHP reviewer (ask at the mentor session).
6. **JJ:** Scribe v2 Realtime versus Transcribe; where audio recordings live (S3) and the consent wording; hosting choice.
7. **Logan:** agree on the factored decision-point model; the minimum number of hand-scored transcripts for an agreement statistic (for example weighted Cohen's kappa) you would defend; the acceptable accuracy for event tagging, and what "uncertain" does (proposed: mark "unclear" for faculty).
8. **Kareem and Anye:** who owns the image and ECG library (with credits) and the exam-maneuver catalog? Has anyone used Blender? If not, cut the 3D figure.
9. **Everyone:** the exact 60-second live-creation script. Who plays faculty on camera, and is the description spoken or typed?
10. **Everyone:** can a real faculty member (SHP or medical school) try the Studio before Sunday? One real quote beats any feature.
11. **Mentor session:** should follow-up visits build on *other students'* earlier encounters, or does that drift into C2? v1 is the same student's next visit, plus faculty-approved prior notes.
12. **Brief conflict:** the C1 brief says "support text interaction". The team decided the student never types. The live transcript and the internal text pipeline (used by test students) are text, but there is no typed input. Decide whether a hidden accessibility or text fallback should exist.
13. **Tavus:** someone must create the account (keys go in `.env`). Test the custom LLM, Image-to-Replica timing and ElevenLabs v4 model acceptance.
14. **Kaggle pathology dataset:** someone with a login checks its contents and license.
15. **Product name:** working name Rounds. Confirm or replace; the name is crowded (Bedside Rounds podcast, Rounds AI, others).
16. **Care timeline scope:** v1 is multi-visit cases (L-01) only. Does the faculty-ordered timeline with simulated nodes (PRD L-08) make the video, or stay a sketch?
17. **Ahmad:** the list of learner roles per profession and training level that cases may assign.

---

## 16. Status log

- **Done:**
  - track and challenge chosen;
  - sponsor dataset analyzed;
  - two team brainstorms and the team feedback document incorporated;
  - AWS Bedrock access verified;
  - cost budget alerts set;
  - this context, `PRD.md` and `AGENTS.md` written.
- **Not done:**
  - no application code yet;
  - Tavus account not created;
  - image mockups in progress locally (Anuj); coded UI not started;
  - golden case content incomplete (waiting on Ahmad).
- **Next:** the iteration 1 build per `PRD.md`, then the mentor session, then iteration 2 (Tavus, polish, statistics, video).


### Scripted presenter rehearsal (2026-10-10)

A user-requested notebook rehearses three fixed examples: pneumonia after Philadelphia convention/hotel travel, tobacco use with a patient unwilling to quit, and a 45-year-old woman with panic/anxiety history and an early ST-elevation ECG finding. This is separate from the existing golden cases. `/api/demo` uses authored static playback with estimated display delays and no actual model calls or scores. Educator metadata extraction and fixed dialogue are shown separately; the source snapshot is pinned per session. Text inputs exist only in the presenter notebook/automation boundary; no production student typing UI is introduced. Clinical review remains pending.

The debrief is a separate review after the encounter has ended. Reflection questions
and teaching guidance do not interject into the conversation. The notebook separates
ending the encounter from viewing its debrief. Each review file ends with one
debrief block for the entire completed dialogue, without per-turn references.
