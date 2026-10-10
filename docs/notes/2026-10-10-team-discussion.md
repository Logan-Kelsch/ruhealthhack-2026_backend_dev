# Team discussion notes, 2026-10-10

Written up from the PM discussion (Safwan, Ahmad, Anuj), so the team can come back to it. Parts of the recording are a separate conversation between Logan and JJ; only points clearly about Rounds are kept here. Items marked **Open** need a team decision before anyone builds them.

## The pitch: lead with value-based care

- Value-based care is how we open whenever we talk about Rounds. Payment follows outcomes, and outcomes depend on conversations: the allergy that gets caught, the plan a patient can actually follow at home, the follow-up that keeps someone out of the emergency department.
- Two halves of the value:
  - **Saving time.** Educators build a case in minutes from a description instead of writing scripts and briefing actors, and the debrief points at the transcript so review takes less time.
  - **Getting more out of each hour of education.** Every learner gets as many practice visits as they need, the same patient for everyone, and feedback tied to their own words.
- We state no numbers (hours saved, scores improved) until a script in `backend/scripts/` produces them (AGENTS rule 6).
- The pneumonia demo case (Frank Russo) is built around this: the good outcome is a safe home plan rather than an avoidable admission, and the bad branch ends in the emergency department.

## Learner side

| Point from the discussion | Status |
|---|---|
| Patient card: plain grey/white person icon, no gradient, no age on the card, hook line instead of repeating the name | Done |
| Doorway vitals in one row: temperature in °F with °C in parentheses, then heart rate, breathing rate, blood pressure, oxygen, height, weight, body mass index | Done (briefing). Visit chart now shows °F first too |
| Visit screen fits one screen, no page scroll | Done at 1280×720 and up. Phones still stack and scroll |
| Chart column on the right was too wide | Narrowed |
| Transcript is a fixed box that follows the newest line, learner on the right and patient on the left in different colors | Done |
| Bottom-left panel with tabs for referral and documents, labs, and the exam log | Done. A newly released item opens its tab |
| X-ray, ECG and lab images with hover to enlarge and click to zoom | **Not built.** See "Images" below |
| Narrated physical exam with the patient reacting | Partly there: exam findings come from the case and the patient says "Okay, go ahead." Narration of the finding by the patient is not built |
| Practice (tutor) mode vs assessment mode, set by faculty | **Not built.** Needs backend (a mode on the assignment or case) |
| Practice mode: live check-offs when the learner hits a faculty criterion, and a flag for clearly unsafe moves | **Not built.** The engine already tags actions and decision points per turn, so check-offs could be read from the turn result |

## Educator side

| Point from the discussion | Status |
|---|---|
| Remove "Good morning" and ages from the home page | Done |
| Home page is simple, and building a case is the obvious first step, with the three steps explained | Done |
| Remove "Your cases" from home | Done. The case library is one click away |
| Sections named by condition ("Section 1 · Endometriosis"), assignments with progress, completed-assignment analytics ("20% didn't recognize the MI on the EKG") | **Not built.** No backend for sections or assignments (PRD D-01/D-02). Nothing is mocked on the home page |
| Case builder: description first, optional notes, then guided steps with grey examples, suggestions and a fill button | Done (see below) |
| Use our AWS connection so Haiku fills fields | Done for words. See "Haiku and numbers" |
| Attachments need a faculty description of what the learner should take from them | **Not built** in the builder. The case schema already stores attachments with license and attribution |
| Gallery of real images by condition from openly licensed sources | **Not built.** Needs approval to download a small set (PRD S-09) |
| Import and export (JSON, PDF) | **Not built.** A sample-set import exists. No export button yet |

## Case builder (built in this pass)

- Steps: description and notes → who they are → the visit → history → how they talk → vitals → learning goals and save.
- "Suggest the details" sends the description and notes to the fast model (Haiku on Bedrock). It fills **empty** fields only, and each filled field is marked "Suggested" until the educator changes it.
- "Suggest typical values" fills vitals from published resting ranges for the patient's age, shifted by guideline rules for conditions such as hypertension. Each value names its source.
- Conditions can be searched as ICD-10 codes or added as typed.
- Save creates one draft case and opens it in Studio, where every item still needs approval before publishing. The original "Create draft" path is kept for drafting everything in one go.

## Haiku and numbers

The discussion assumed Haiku would also set values such as a high blood pressure. AGENTS rule 3 says auto-filled values come from data or rules, never a model guess. So:

- Haiku fills words: name, history, personality, goals, conditions, medications.
- Numbers come from the rules engine, with a source on every value.

If the team wants model-suggested numbers anyway, that is a change to rule 3 and should be decided together.

## Images (asked during the session)

Already in the backend: attachments of type X-ray, CT, ECG, lab report or prior note, each with an image link, license, attribution and a release rule. Publishing requires a license and attribution (S-09).

Missing:
1. **Images.** About 10 to 20 openly licensed X-rays and ECGs, each saved with its source link, author and license. Radiopaedia is non-commercial only (CC BY-NC-SA), so avoid it or flag it.
2. **A builder step** to pick or attach an image, write what the learner should take from it, and choose when it appears.
3. **Learner view.**
   - The visit screen's public chart does not currently include the image link or attribution, so a small backend change is needed.
   - Then hover to enlarge, click to zoom, and the credit as a caption.

## Questions to settle

- Should prior X-rays and labs also show on the briefing, or only once the visit starts?
- Is it OK to download a small set of openly licensed demo images (about 20 files, under 10 MB)?
- Practice vs assessment mode: is it set per case, per assignment, or per learner?
- Sections and assignments: who owns the backend (D-01/D-02), and is it in scope before judging?
- "Rounds logo on image 2 is getting…" was cut off in the message. What was the issue?
- Alina Reyes's case title ("…what the questionnaire hides") gives away the hidden fact to learners. Rename?
- The "Not built yet · E-15 video" tag shows on the call frame. Keep it for honesty, or hide it for the demo?

## Mentor session prep

Questions to bring to the mentors, from the discussion:
- What would make faculty actually build a case themselves rather than ask someone else to?
- Which feedback would a clerkship director act on: per-learner debriefs, or patterns across a section?
- How do programs handle practice vs graded encounters today, and who sets that?
- Which image sources do programs already trust and license?
