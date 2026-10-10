# Clinical reasoning and evaluation plan for TwinVerse

Prepared 10 October 2026 for Ahmad and the project team. This is an AI-authored critique written from a medical student's perspective. It is not Ahmad's opinion, a completed faculty review, or a treatment protocol. Every clinical proposal below is **TODO(clinical-review)**. The implementation prepares review work; it does not publish these proposals as patient facts.

## Recommendation

I would keep Challenge 1 as the core and demonstrate three authored cases through the same encounter engine. The educational feature is the connection between a student's question, the fact discovered, the reasoning that follows and an evidence-linked debrief. The cases can illustrate that connection, but their published and approved JSON fields do not establish independent clinical approval.

I would revise the depression case before using it as the clinical centerpiece. Direct safety questions should receive credit immediately. Asking about past mania should uncover information and prompt assessment; it should not automatically select a drug. The pediatric case should teach antibiotic stewardship and the limits of a negative rapid antigen test. Walter's case should keep the dietetics role explicit and describe follow-up as an authored scenario.

## Alina and safety assessment

The source is `cases/alina_reyes.json`, version 1. Fact `f_passive_si` requires trust 1 and topic `suicidal_ideation`; `f_no_plan` depends on its disclosure. Trust begins at 0. A student can ask a clinically appropriate direct question and receive a deflection. This is a simulator design concern, not evidence that real patients always disclose risk immediately.

The National Institute of Mental Health states that asking directly about suicide does not cause or increase suicidal thoughts [1]. I infer that a required rapport score should not teach students to delay safety screening. My preferred teaching variant releases the already authored safety response when asked directly, while rapport affects elaboration and tone. An alternative is an explicitly authored refusal with a debrief stating that assessment remains incomplete. Deflection must never become a negative screen. The existing rule that an abrupt question is a communication note only should remain.

The institute's assessment guide addresses current thoughts, plans, access to means, previous behavior and disposition following a positive screen [2]. The current `f_no_plan` statement bundles separate negatives. I would separate those facts so one question cannot appear to establish all of them. Passive death wishes should prompt additional assessment in the teaching objectives. Approved wording for safety planning, escalation and follow-up is needed; a low questionnaire score cannot substitute for that assessment. Missing details require authored facts, not improvisation by the patient model.

## Alina and the treatment branch

Fact `f_hypomania_hx` describes a past week of little sleep, elevated confidence and spending. Together with `f_family_bipolar`, this raises concern for bipolar-spectrum illness. It does not establish the diagnosis: change from baseline, functional consequences, substances, medication effects and other explanations still need assessment. My provisional formulation is depression with a possible bipolar history requiring clarification and supervision.

The current `dp_bipolar_screen` is true if the topic was asked or the fact disclosed. Branch `b_bipolar_managed` then supplies aripiprazole for bipolar depression; the opposite branch supplies sertraline and later hypomanic features. A screening question is being used as a proxy for diagnosis and prescribing. This is the main branch-design problem.

The CANMAT and ISBD guideline distinguishes mania treatment from acute bipolar depression and does not recommend aripiprazole monotherapy for acute bipolar depression; antidepressant monotherapy is also not recommended for bipolar I depression [3]. I would not substitute another automatic prescription. The teaching objective is recognition and safe escalation, with any treatment authored by the reviewer for a clearly defined illness phase.

My proposed decision points distinguish screening performed, concerning history elicited, findings recognized and communicated, and a supervised management plan made. Only an explicitly documented treatment action should activate a treatment-specific follow-up. A student who asks about mania but ignores the answer should not get the successful branch. A student who omits screening but does not start an antidepressant should not automatically get antidepressant-associated activation. Keep the questionnaire trap, but label each outcome an authored teaching scenario rather than an inevitable trajectory.

There is a timing discrepancy: `context.md` describes a three-week follow-up, while the case schedules day 42. Ahmad should choose the intended interval and review the early monitoring plan. Accepted clinical changes need a new case version, regenerated traces and a new lock; editing version 1 would invalidate the historical evaluations.

## Eli and antibiotic stewardship

Source `cases/eli_brooks.json` contains cough and rhinorrhea, a three-day illness, preserved drinking and play, a mother's antibiotic expectation and yesterday's negative rapid strep antigen test. These facts support a viral upper respiratory infection teaching scenario. They do not exclude every complication.

CDC guidance says clear viral symptoms generally do not require group A streptococcal testing. For symptomatic children aged at least three years with a negative rapid antigen test, it calls for a backup throat culture and a way to contact the family if positive [4]. The case should explain why testing occurred at urgent care and whether a culture is pending or completed. It should not teach that the antigen result definitively excludes streptococcal disease. A molecular test is different and must be named accurately.

I would assess whether the student elicits the mother's concern, explains the working diagnosis and uncertainty, proposes approved symptomatic care and gives specific follow-up instructions. Simply omitting an antibiotic is insufficient: silence also satisfies the current negative predicate. The reviewer should specify expected advice and return precautions with age-appropriate content and sources. The explanation should acknowledge the mother's wish to help her child rather than reward confrontational refusal.

## Walter and the limits of the model

Source `cases/walter_greene.json` links heart and kidney concerns, ibuprofen use, food choices and social barriers. A dietetics student can identify the medication concern and communicate it to the supervising care team. The assessment should not require independent prescribing or imply that one counseling encounter determines later kidney values or hospitalization.

I would retain patient goals, practical food choices and teach-back as visible educational tasks. Clinical targets, medication advice and follow-up values need clinical or dietetics review. Authored branches demonstrate continuity, but cannot estimate the probability of improvement. A reviewer should resolve inconsistencies between the sponsor CSV, full profile and project case rather than silently combine them.

## Critique of this reasoning

This critique identifies plausible teaching hazards from source files; it has not observed learners or patients. Faculty might author guarded safety disclosure to teach persistence. My objection is to presenting missing disclosure as reassuring evidence or making rapport a prerequisite for credit. The rubric should state that distinction.

The bipolar guideline flags the current branch but does not decide Alina's diagnosis or individualized treatment. The case lacks a full assessment. Eli's viral symptoms also raise the question of whether urgent-care testing was indicated. A reviewer should preserve that uncertainty rather than add a result solely to finish a demo.

Ahmad is a fourth-year medical student and can critique these proposals; that is not automatically independent faculty approval. The coordinator must determine who can approve clinical content and independently rate it. The kit does not authenticate those roles.

## Steps 3 through 6

The recovered discussion covers faculty approval, grounded case data, adversarial and feedback evaluation, and difficulty or learning evaluation. The following maps those themes to repository feature IDs; the repository specification governs implementation.

### Step 3 Clinical review and authored behavior

Use the existing cases, official seven-domain rubric, transcripts and 287 locked review packets. First use the new 12-packet sample, one task of each kind per case, to check instructions and evidence citation. This is a workflow rehearsal, not a representative sample or clinical-validity estimate.

Then review the full queue: 189 disclosure turns, 15 semantic candidates, 41 feedback claims and 42 rubric domains. Two reviewers answer independently; a third handles disagreements. AI critique cannot supply an independent label. Case approval and packet agreement are separate decisions. Record approved behavior, alternatives and unresolved items through the existing authoring process after coordinator verification. Feature IDs: S-07, V-02, V-03 and F-05.

Closure requires verified authority, resolved relevant reviews and prespecified criteria. Clinical edits create a new case/protocol version and regenerated probes. This PR supplies preparation and validation mechanics; approval remains pending.

### Step 4 Grounded data and live checks

For this weekend, use sponsor synthetic profiles and faculty-authored facts. Generate utterance variations and adversarial replies only as authored test inputs. Save origin, versions and exact text. Do not convert generated explanations into patient facts or gold labels.

Use the existing V-01 runner for the classifier, disclosure engine, phraser and verifier. It records prompts, replies, fallback, latency and token usage. Run live with operator-configured Bedrock access, then review resulting replies independently without model verdicts. Log semantic failures and unnecessary rejections. Valid numbers and citations do not establish semantic support. Feature IDs: P-01, V-01, V-05 and V-06. Audio latency and voice cost need the integrated voice system.

The supplement separately locks the 12 candidates added by the live probe: negation, an invented student number asserted as a patient fact, wrong units and unsupported conclusions. These difficult candidates do not estimate ordinary conversation failure prevalence. Labels remain empty until human submission.

Synthea generates synthetic patient histories and structured records [5]. It can later expand import coverage after an adapter and clinical review. It does not supply our disclosure expectations, student skill spans or rubric judgments, so it cannot close those label gaps. No external dataset is downloaded by this PR. Patient–Doctor and pathology sources remain excluded pending license and provenance. NHANES may inform later value distributions, but does not establish complete-case plausibility.

### Step 5 Feedback and assessment labels

Start with reviewed utterance spans and the existing simple baseline, keeping patient dialogue acts separate from student skills. A teacher model may propose development labels; reviewers must correct them before evaluation. Hold out whole patients or case families, keep paraphrases in the same split, freeze the test set and report critical-action recall separately. Synthetic labels test training mechanics only. Feature IDs: F-01, F-03, V-03 and P-01.

Review each feedback claim against its fact or exact transcript span. A valid offset proves the quote exists, not that the claim follows. Grade communication, reasoning and safety separately; retain N/A and disagreements. The existing protocol proposes at least 20 double-rated transcripts per domain for feasibility; six authored transcripts cannot satisfy that target. Score coverage and uncertainty matter more than one agreement number. One reviewer provides useful formative feedback but cannot establish inter-rater reliability.

Closure needs genuine complete held-out labels, independently reviewed scores and existing criteria. This PR does not train a critic on invented learner truth or replace the keyword fallback.

### Step 6 Difficulty and learning

First author full difficulty variants with a reviewer: identical clinical truth and objectives, with approved changes to communication complexity and disclosure. Avoid making critical safety information harder to obtain solely to manufacture difficulty. Existing threshold vectors are engineering examples and omit other preset dimensions. Scripted students test monotonicity, replay and faults only. Feature IDs: S-11, V-04 and the existing learner-study protocol.

For the demo, use transparent faculty routing to a case addressing a reviewed missed objective. Do not estimate skill or learning reward from unreviewed totals. Contextual bandits or tree search need trustworthy rewards and learner-transition evidence; adding them now does not close this gate.

For later evaluation, retain the proposed consenting learner design: baseline and held-out follow-up encounters, independent blinded raters, fixed outcomes, missingness by arm and learner-level analysis. Retention and transfer need separate assessment opportunities. The planning assumption of about 74 learners per arm with loss allowance is not a current recruitment target or evidence of power for this product. Prospective intake remains blocked pending institutional determination. Generated students cannot prove learning improvement.

## Decisions for the clinical reviewer

Mark each proposal accept, revise or reject with a source and rationale: safety disclosure; separate safety facts; diagnostic and treatment predicates; Alina's follow-up interval; Eli's testing and culture context; symptomatic advice; Walter's role boundaries; and all follow-up outcomes. Version accepted content and re-run golden-case probes before recording.

## Sources

Online sources checked 10 October 2026. Repository evidence: `AGENTS.md`, `context.md` sections 11–15, `PRD.md` section 15, three case JSON files and Notebook 06–08 validation materials. The machine report records the current source lock.

1. National Institute of Mental Health. Frequently Asked Questions About Suicide. https://www.nimh.nih.gov/health/publications/suicide-faq
2. National Institute of Mental Health. Adult Outpatient Brief Suicide Safety Assessment Guide. https://www.nimh.nih.gov/research/research-conducted-at-nimh/asq-toolkit-materials/adult-outpatient/adult-outpatient-brief-suicide-safety-assessment-guide
3. Yatham and colleagues. CANMAT and ISBD 2018 guidelines, acute bipolar depression section. https://pmc.ncbi.nlm.nih.gov/articles/PMC5947163/ See also the 2023 update: https://pmc.ncbi.nlm.nih.gov/articles/PMC11058959/
4. Centers for Disease Control and Prevention. Clinical Guidance for Group A Streptococcal Pharyngitis. https://www.cdc.gov/group-a-strep/hcp/clinical-guidance/strep-throat.html
5. Synthetic Health. Synthea overview and repository, Apache 2.0 code license. https://synthetichealth.github.io/synthea/ and https://github.com/synthetichealth/synthea
