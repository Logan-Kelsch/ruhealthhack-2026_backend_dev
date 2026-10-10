# AGENTS.md — How to work in this repo

This file is for any AI coding agent (Claude Code, Codex, Cursor and others) and for any person on the team. Claude Code loads it automatically through `CLAUDE.md`.

## Read first (in this order)
1. **`context.md`:** the full background (event rules, judging, team, sponsor data, every decision and why) and the **Shared Dictionary** (§14). Use its terms exactly.
2. **`PRD.md`:** what to build, with feature IDs (S-, E-, L-, F-, D-, P-), acceptance criteria, data model, pipeline, API and repo layout.
3. This file: the rules for working.

If something you are asked to do conflicts with these docs, say so before doing it. If the docs are wrong, fix the docs in the same pull request.

## What we're building (one paragraph)
[Product name] is a virtual patient encounter system for health-professions education (Rutgers Health Hack 2026, TwinVerse track, Challenge 1).

- **Faculty** build patients in a Patient Studio: plain-language description, guided intake, statistically grounded auto-fill, consistency check, publish.
- **Students** talk to the patient **by voice, hands-free**. The patient only states faculty-approved facts and opens up as trust is earned.
- **The debrief** scores the student on the official 7-domain rubric, with every score citing transcript evidence.
- **Follow-up visits** change based on what the student did.

Working product name is **Rounds** (may change); keep writing `[Product name]` in docs.

## Non-negotiable rules

### Clinical truth and safety
1. **The LLM never decides facts.** Code (the disclosure engine) decides which facts may be said; the LLM only phrases them; the verifier checks the reply. Never let a prompt "fill in" a clinical value at runtime.
2. **Every clinical statement, chart item, finding and score cites its source:** a fact ID, or a transcript span for feedback. No citation means it doesn't ship, and the verifier fails closed.
3. **Auto-filled values come from data or rules, never an LLM guess.** Use NHANES, a published reference interval, a guideline rule or a formula, and record the `source` on every value.
4. **No real patient data, ever.** Synthetic only, and document how it was made.
5. **Never penalize asking about suicidal ideation.** An abrupt opener is a communication note only.
6. **No unsupported claims** in UI, docs or the video. That means no "HIPAA compliant", "clinically validated" or "improves learning by X%". Only state numbers produced by scripts in `backend/scripts/` and saved in `docs/validation/`.

### Product decisions already made (don't relitigate without the team)
7. **The student never types during an encounter.** The microphone is always live with streaming transcription. There is **no push-to-talk and no text box.**
   - A backend text endpoint exists for test students, scripts and the Tavus integration. It must not appear as a student-facing input.
   - Whether a hidden accessibility fallback is allowed is an open question; don't add one unless the team decides.
8. **Iteration 1 has no video avatar.** The patient is a circular profile photo in the center. Iteration 2 adds Tavus, with our backend as the LLM, and ElevenLabs v4 (Turbo for live) as the voice.
9. **Encounter layout:**
   - patient center;
   - live transcript below;
   - goal, referral and exam on the left;
   - progressive chart on the right.
10. **Trust is hidden during the encounter** and shown in the debrief. Trust changes only through listed trust events, each with a quoted span.
11. **The default rubric is the official SHP 7-domain rubric:**
    - 1–4 or N/A per domain;
    - max 28;
    - a review flag if domain 6 or 7 scores 1;
    - the total is "a discussion aid, not a pass/fail grade".
12. **Decision trees are factored and authored.**
    - Each visit has 2–4 yes/no decision points, evaluated from tagged events.
    - Faculty-written outcomes; no probabilities.

### Secrets and accounts
13. **No secrets, account IDs, emails or keys in the repo, in commits or in chat.** Keys go in `.env` (git-ignored), with names listed in `.env.example`.
    - The team shares one `.env` directly (not through the repo). The same file is stored as the GitHub secret `APP_ENV`, which CI copies to the server (see `infra/README.md`).
14. **Never log in to accounts or enter credentials on someone's behalf.** Root is never shared. For local development the team shares one IAM key, limited to the app's own permissions (`AppPermissions` in `infra/cloudformation/app.yaml`), so a new teammate only needs the shared `.env`. Account admin work (deploying stacks, creating keys) uses each person's own IAM user.
15. **AWS region and resource names come from config** (one settings module plus `.env`). Model IDs come from config, never hard-coded.
16. Keep costs low: small instances, no always-on extras, and tear down after the event. A budget alert exists on the account.

## Engineering conventions

### Stack
- **Backend:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, boto3, pytest.
- **Frontend:** React + TypeScript (Vite), Tailwind, shadcn/ui, React Flow, Recharts.
- **Database:** Postgres (Docker locally, RDS in the cloud).
- **AI:** AWS Bedrock (Claude; optional Nova Micro for the fast tier).
- **Voice:** ElevenLabs (Scribe v2 Realtime STT, Eleven v4 / v4 Turbo TTS).
- **Avatar:** Tavus (iteration 2).

### Style
- **Modular, not over-engineered.** One module per responsibility (see the PRD §13 layout).
  - No microservices, Redis, vector databases or Kubernetes. Cognito is used for sign-in only (see `infra/README.md`).
  - Add a dependency only when it removes real work, and say why in the pull request.
- **The case is one JSON document** validated by Pydantic (`backend/app/schemas/case.py`) and stored in a JSONB column. Change the schema there first, then migrations, then generated types.
- **Generated API types:** the frontend uses types generated from FastAPI's OpenAPI schema (`openapi-typescript`). Don't hand-write API types; regenerate after backend changes.
- **The disclosure engine, trust rules, decision-point evaluation, auto-fill formulas and verifier number checks are pure functions** with unit tests. Same input, same output.
- **Prompts live in `backend/app/prompts/`** as versioned files. Record the prompt version and model ID on every logged LLM call.
- **Fixed vocabularies** live in `backend/app/vocab/*.yaml`: topics, exam maneuvers, trust events, lay lexicon. The classifier may only output labels from these.
- **Classifier and verifier calls use temperature 0 and structured (JSON schema) output.**
- **Fail closed:** if a check can't run, use the template fallback rather than an unchecked reply.
- **Log everything an encounter needs for replay and feedback** (PRD P-01).
- **Match the surrounding code:** naming, comment density, idiom. Comments explain *why*, not *what*.
- **UI:**
  - Vibrant colors; gradients, depth and illustration allowed (updated 2026-10-10); not blank white; professional.
  - Colors are tokens in one file.
  - Expand abbreviations on first use on each screen.
  - No gamified language.

### Writing (code comments, UI copy, docs, commits, patient dialogue)
Follow `context.md` §14b:
- Plain, specific, short.
- **Banned words:** delve, leverage (verb), seamless, robust, cutting-edge, game-changer, revolutionize, harness, empower, elevate, "it's important to note", "it's worth noting", tapestry, realm, synergy, state-of-the-art, next-generation, best-in-class, "AI-powered" as a selling point.
- Patient dialogue is lay language at the case's health-literacy level: spoken, short, no lists or markdown.

### Docs neutrality
Docs never refer to "the coder" as a particular person and never take sides between teammates. Every design decision states its functional reason.

## Workflow

- **The first commit of docs went straight to `main`.** From now on, use **branches and pull requests into `main`**. Name branches `feat/<feature-id>-<short-name>`, `fix/<short-name>` or `docs/<short-name>`.
- **One owner per area at a time.** Areas match top-level modules:
  - Studio;
  - encounter pipeline;
  - voice/avatar;
  - feedback;
  - decision tree;
  - dashboard;
  - frontend shell and design;
  - data and credits.
- **Contracts first.** If your change alters the case schema, an API shape or a vocabulary file, land that change in its own small pull request so others can rebase onto it.
- **Pull request description:** feature IDs, what changed, how it was tested, and any doc updates. Keep pull requests small enough to review in a few minutes.
- **Tests before merge:**
  - `pytest` for the backend;
  - type check and build for the frontend;
  - for pipeline changes, run `python -m scripts.run_test_students` (from `backend/`) on the golden cases; it exits non-zero if any reply fails the audit.
- **Golden-case gate:** before recording any video, run the test students on all golden cases and check that grounding is 100% and nothing regressed.
- **Commit messages:** imperative mood, plain language, reference feature IDs. No AI co-author trailers or "generated with" lines; commits are authored by the person who pushes them.

## Setup

Backend (Python 3.12+). `pip` shown; `uv sync` / `uv run` also work from `backend/`.
```bash
cp .env.example .env
```
```bash
docker compose up -d db
```
```bash
cd backend && python -m venv .venv && .venv/Scripts/pip install -e . pytest
```
```bash
cd backend && .venv/Scripts/python -m alembic upgrade head && .venv/Scripts/python -m scripts.seed_golden_cases
```
```bash
cd backend && .venv/Scripts/python -m uvicorn app.main:app --reload
```
(On macOS/Linux use `.venv/bin/` instead of `.venv/Scripts/`.) API docs are at http://localhost:8000/docs.

Checks:
- Tests (offline, SQLite): `cd backend && LLM_ENABLED=false .venv/Scripts/python -m pytest -q`
- Test students on the golden cases, no database: `.venv/Scripts/python -m scripts.run_test_students` (`--offline` for no Bedrock, `--transcript` to print the conversations, `--save` to write `docs/validation/test_students.json`)
- Verifier on labeled lines (needs Bedrock): `.venv/Scripts/python -m scripts.eval_verifier --runs 2`
- Set `LLM_ENABLED=false` to run everything without AWS (keyword classifier and template replies).

Frontend (not built yet):
```bash
cd frontend && npm install && npm run dev
```

Expected `.env` variable names (no values in the repo):
- `DATABASE_URL`, `AWS_REGION`, `AWS_PROFILE`;
- `BEDROCK_MODEL_FAST`, `BEDROCK_MODEL_STRONG`;
- `ELEVENLABS_API_KEY`, `ELEVENLABS_TTS_MODEL_LIVE`, `ELEVENLABS_TTS_MODEL_HQ`, `ELEVENLABS_STT_MODEL`;
- `TAVUS_API_KEY`, `TAVUS_REPLICA_ID`, `TAVUS_PERSONA_ID`;
- `S3_BUCKET`, `STT_VAD_SILENCE_SECS`.

Verify current model IDs before use:
- Bedrock: `aws bedrock list-inference-profiles --region us-east-1`.
- ElevenLabs and Tavus: their developer docs.

## When you're unsure
- **Clinical content:** ask Ahmad (clinical reviewer). Don't invent clinical rules; mark them `TODO(clinical-review)`.
- **Statistics and the decision-tree model:** ask Logan.
- **AWS and backend infrastructure:** ask JJ.
- **Product scope and the video:** ask the PMs (Safwan, Anuj).
- **Anything else:** state your assumption in the pull request and keep going.

## Doc map
- `context.md`: everything known so far; Shared Dictionary in §14; open questions in §15.
- `PRD.md`: requirements, IDs, data model, pipeline, API, layout, validation, risks.
- `AGENTS.md`: this file.
- `CLAUDE.md`: imports this file for Claude Code.
- `README.md`: setup, deploy and credits (to be written as code lands; required for submission).
