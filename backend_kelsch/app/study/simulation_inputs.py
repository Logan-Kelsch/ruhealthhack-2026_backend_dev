"""Versioned synthetic replacements; never fabricate reviewer authority or consent."""
from __future__ import annotations

from copy import deepcopy
import random

from backend_kelsch.app.study.protocol import digest

VERSION = 'simulation_demo_v1'
SCENARIOS = ('no_effect', 'beneficial_effect', 'adverse_effect', 'missingness', 'repeated_encounters')
PHRASES = {
    'summarize': ('Let me summarize what you said.', 'So to recap what you said.'),
    'check_understanding': ('Does that make sense?', 'Can you tell me in your own words?'),
    'ask_permission': ('Would it be okay if we discuss this?', 'Can I share some information?'),
    'give_information': ('Let me explain what this means.', 'This happens because of the issue we discussed.'),
    'plan_next_steps': ('The next step is another discussion.', 'Let us plan a follow-up discussion.'),
    'safety_netting': ('Call us if things get worse.', 'Come back if things get worse.'),
    'closing': ('Thank you for coming.', 'Take care and goodbye.'),
    'confront_or_lecture': ('You must do what I say.', 'You need to stop arguing.'),
    'start_medication': ('I will start you on a new medication.', 'I will begin taking a new medication.'),
    'prescribe_antibiotic': ('I will prescribe an antibiotic.', 'I will prescribe you an antibiotic.'),
    'order_test': ('I will order a test.', 'I will draw some blood.'),
    'other': ('What worries you most?', 'Tell me about your day.'),
}


def envelope(component: str, generation: str, **data) -> dict:
    return {'version': VERSION, 'source_kind': 'synthetic_fixture', 'component': component,
            'generation_description': generation, **data}


def action_corpus(families: int = 30) -> dict:
    """Whole-sentence spans, two conversations per linked synthetic patient/family."""
    conversations, annotations = [], []
    for family in range(families):
        for repeat in range(2):
            cid = f'synthetic-family-{family:02d}-encounter-{repeat}'
            turns = []
            for label, phrases in PHRASES.items():
                # Neutral unique context prevents exact duplicate turns crossing splits.
                # Shared phrase banks still make this a deliberately easy template corpus.
                phrase = phrases[(family + repeat) % len(phrases)]
                text = f'In practice discussion {family}-{repeat}, {phrase[0].lower() + phrase[1:]}'
                labels = [label]
                if label == 'prescribe_antibiotic':
                    labels.append('start_medication')
                if label == 'safety_netting' and phrase.startswith('Come back'):
                    labels.append('plan_next_steps')
                tid = str(len(turns) + 1)
                turns.append({'turn_id': tid, 'speaker': 'student', 'text': text})
                annotations.append({'annotation_id': cid + ':' + tid, 'conversation_id': cid, 'turn_id': tid,
                    'speaker': 'student', 'start': 0, 'end': len(text), 'span': text, 'labels': sorted(labels),
                    'rubric_mapping': [], 'namespace': 'student_skill', 'label_origin': 'authored_simulation_template'})
            for text in ('I will not prescribe an antibiotic.', 'I will not start you on a new medication.',
                         'I have not explained any warning signs yet.'):
                text = f'In practice discussion {family}-{repeat}, ' + text[0].lower() + text[1:]
                tid = str(len(turns) + 1)
                turns.append({'turn_id': tid, 'speaker': 'student', 'text': text})
                annotations.append({'annotation_id': cid + ':' + tid, 'conversation_id': cid, 'turn_id': tid,
                    'speaker': 'student', 'start': 0, 'end': len(text), 'span': text, 'labels': ['other'],
                    'rubric_mapping': [], 'namespace': 'student_skill', 'label_origin': 'authored_simulation_template'})
            conversations.append({'conversation_id': cid, 'patient_id': f'synthetic-patient-{family:02d}',
                'family_id': f'synthetic-family-{family:02d}', 'case_id': 'eli_brooks',
                'turns': turns, 'source_sha256': digest(turns)})
    return envelope('action_corpus', 'Code-authored phrase banks from the closed action vocabulary, plus explicit negations. '
                    'Sentence-level exact spans; unique neutral context, linked repeat conversations. '
                    'Shared phrase banks across held-out groups make this template generalization, not novel learner language. '
                    'These hypothetical utterances are not clinical recommendations.',
                    conversations=conversations, annotations=annotations)


def learner_fixture(scenario: str, *, seed: int = 2026, learners_per_arm: int = 12) -> dict:
    """Generate integer rubric-shaped mathematical outcomes, not backend-derived grades."""
    if scenario not in SCENARIOS:
        raise ValueError('unknown synthetic scenario')
    rng = random.Random(seed)
    n = 2 * learners_per_arm
    ids = [f'simulated-learner-{i:03d}' for i in range(n)]
    shuffled = rng.sample(ids, n)
    feedback = set(shuffled[:learners_per_arm])
    roster = [{'learner_id': lid, 'arm': 'feedback' if lid in feedback else 'standard'} for lid in ids]
    encounters = []
    effect = -1 if scenario == 'adverse_effect' else 0 if scenario == 'no_effect' else 1
    for i, row in enumerate(roster):
        # Match the background mathematical changes by arm to make the null control exact.
        rank = sum(r['arm'] == row['arm'] for r in roster[:i])
        background = (-1, 0, 1)[rank % 3]
        for phase in ('baseline', 'followup'):
            if scenario == 'missingness' and phase == 'followup' and rank % 7 == 0:
                continue
            repeats = 3 if scenario == 'repeated_encounters' and i % 3 == 0 else 1
            score = 2 if phase == 'baseline' else max(1, min(4, 2 + background + (effect if row['arm'] == 'feedback' else 0)))
            scores = {str(d): score for d in range(1, 8)}
            # N/A is never imputed. One learner has no common scored domains in the missingness scenario.
            if i % 5 == 0:
                scores['7'] = 'N/A'
            if scenario == 'missingness' and i == 1:
                scores = {str(d): 'N/A' for d in range(1, 8)}
            for repeat in range(repeats):
                encounters.append({'learner_id': row['learner_id'], 'arm': row['arm'],
                    'encounter_id': f"{row['learner_id']}-{phase}-{repeat}", 'phase': phase,
                    'case_id': 'mathematical-fixture-' + phase, 'scores': deepcopy(scores),
                    'score_origin': 'synthetic_latent_arithmetic; not transcript-derived clinical grades'})
    return envelope('learner_scenario', 'Balanced randomized synthetic roster; baseline=2, background cycle=-1/0/+1 matched '
                    'by arm, assumed feedback shift, scores clipped to 1–4. N/A, phase loss and duplicate score records '
                    'exercise analysis mechanics. Case IDs are disjoint arithmetic fixtures, not independently validated '
                    'clinical transfer cases. Matching background changes makes the null an exact test control, not a power simulation.',
                    scenario=scenario, seed=seed, assumed_feedback_shift=effect,
                    design='unstratified_parallel', roster=roster, encounters=encounters)


def default_inputs(seed: int = 2026) -> dict:
    return {
        'action_corpus.json': action_corpus(),
        'review_policy.json': envelope('review_policy', 'Seeded perturbations of frozen rule-based/constructor labels. '
            'Two synthetic source IDs plus a synthetic tie breaker exercise transport, disagreement and adjudication. '
            'They are correlated simulations, not independent people, clinical judgments or gold labels.',
            seed=seed, flip_every_a=17, flip_every_b=13),
        'case_preset_decisions.json': envelope('case_preset_decisions', 'Assume current authored case content and outcomes '
            'for a demo only; copy case hashes and threshold-probe offsets. Code-authored progression estimates use '
            'mean rubric thresholds 2/3, the existing domain 6/7 score-1 review flag, and exact-role compatibility. '
            'No case or progression estimate is clinically approved.',
            decision='ASSUMED_FOR_SIMULATION', difficulty_probe_offsets={'straightforward': -2, 'typical': 0, 'difficult': 2},
            clinical_review='PENDING', full_presets='UNVALIDATED THRESHOLD PROBE ESTIMATES',
            progression_policy={'version': 'simulation_progression_v1', 'typical_min_score': 2,
                'difficult_min_score': 3, 'safety_review_max_score': 1,
                'role_policy': 'exact role match', 'unavailable_next_case': 'repeat compatible current case',
                'scope': 'Simulation adapter only; no persisted learner recommendation or clinical approval'}),
        'learner_scenarios.json': envelope('learner_scenarios', 'Five mathematical controls generated independently of '
            'backend rubric output; substitute genuine authorized blinded outcomes later.',
            scenarios=[learner_fixture(s, seed=seed) for s in SCENARIOS]),
    }
