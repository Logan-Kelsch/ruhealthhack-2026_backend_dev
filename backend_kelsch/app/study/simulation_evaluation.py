"""Execute actual offline code against synthetic references and mathematical outcomes."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import random
from statistics import mean

from app.schemas.case import Case
from app.schemas.encounter import Intent
from app.encounter import verifier
from backend_kelsch.app.action_data.preparation import grouped_split
from backend_kelsch.app.debrief_probe.evaluation import ROOT, run_all
from backend_kelsch.app.grounding.evaluation import encounter_runs, challenges
from backend_kelsch.app.patient_environment.runner import run_script, replay, fingerprint, ScriptTurn
from backend_kelsch.app.study.development_evaluation import label_metrics
from backend_kelsch.app.study.next_review import prepare_next, action_prediction, review_stage
from backend_kelsch.app.study.permutation import PLAN, learner_changes, monte_carlo
from backend_kelsch.app.study.protocol import digest
from backend_kelsch.app.study.workflow import save, approved_case

CRITICAL = ['prescribe_antibiotic', 'start_medication', 'safety_netting']


def progression_recommendation(policy: dict, catalog: list[Case], current_id: str, scores: dict) -> dict:
    """Provisional routing adapter; N/A abstains and authored learner roles stay separate."""
    if policy.get('version') != 'simulation_progression_v1' or policy.get('role_policy') != 'exact role match' or policy.get('unavailable_next_case') != 'repeat compatible current case':
        raise ValueError('unsupported simulation progression policy')
    low, high, safety = (policy[k] for k in ('typical_min_score', 'difficult_min_score', 'safety_review_max_score'))
    if any(type(v) is not int for v in (low, high, safety)) or not 1 <= safety < low < high <= 4:
        raise ValueError('ordered progression score thresholds required')
    if set(scores) != {str(d) for d in range(1, 8)} or any(v != 'N/A' and (type(v) is not int or not 1 <= v <= 4) for v in scores.values()):
        raise ValueError('seven rubric scores or N/A required')
    current = next(c for c in catalog if c.case_id == current_id)
    observed = [v for v in scores.values() if v != 'N/A']
    if not observed:
        return {'status': 'ABSTAIN', 'reason': 'no scored domains', 'case_id': None, 'preset': None}
    if any(scores[d] != 'N/A' and scores[d] <= safety for d in ('6', '7')):
        return {'status': 'REVIEW_REQUIRED', 'reason': 'provisional safety flag', 'case_id': None, 'preset': None}
    compatible = sorted((c for c in catalog if c.briefing.student_role == current.briefing.student_role and c.case_id != current_id), key=lambda c: c.case_id)
    selected = compatible[0] if compatible else current
    score = mean(observed)
    return {'status': 'PROVISIONAL_SIMULATION', 'case_id': selected.case_id,
            'preset': 'difficult' if score >= high else 'typical' if score >= low else 'straightforward',
            'new_compatible_case_available': bool(compatible), 'learner_role': selected.briefing.student_role,
            'reason': 'next compatible case' if compatible else 'repeat current case; no compatible alternative in catalog'}


def progression_checks(policy: dict) -> dict:
    catalog = [Case.model_validate_json((ROOT / 'cases' / (cid + '.json')).read_text())
               for cid in ('walter_greene', 'alina_reyes', 'eli_brooks')]
    controls = [('strong', {str(d): 4 for d in range(1, 8)}, 'PROVISIONAL_SIMULATION', 'difficult'),
                ('middle', {str(d): 2 for d in range(1, 8)}, 'PROVISIONAL_SIMULATION', 'typical'),
                ('weak', {str(d): (2 if d in (6, 7) else 1) for d in range(1, 8)}, 'PROVISIONAL_SIMULATION', 'straightforward'),
                ('missing', {str(d): 'N/A' for d in range(1, 8)}, 'ABSTAIN', None),
                ('safety', {str(d): (1 if d == 7 else 4) for d in range(1, 8)}, 'REVIEW_REQUIRED', None)]
    rows = []
    # Fixed score controls are assertions about mechanics, not measured learner ability.
    for name, scores, status, preset in controls:
        actual = progression_recommendation(policy, catalog, 'walter_greene', scores)
        rows.append({'control': name, 'synthetic_scores': scores, 'recommendation': actual,
                     'pass': actual['status'] == status and actual['preset'] == preset})
    return {'mode': 'OFFLINE SIMULATION ADAPTER EXECUTED', 'policy': policy, 'controls': rows,
            'status': 'PASS' if all(r['pass'] for r in rows) else 'FAIL',
            'limitation': 'Three authored cases have different learner roles; no compatible new-case transfer is available. '
                          'Recommendations remain local simulation outputs, not a production routing policy.'}


def evaluate_actions(data: dict, directory: Path, seed: int) -> dict:
    """A separate synthetic adapter; do not relax human-only annotation import."""
    conversations, rows = data['conversations'], data['annotations']
    turns = {(c['conversation_id'], t['turn_id']): t for c in conversations for t in c['turns']}
    vocab = json.loads((ROOT / 'backend_kelsch/app/data/action_annotation_vocab.json').read_text())['student_skill']
    if len(turns) != sum(len(c['turns']) for c in conversations):
        raise ValueError('duplicate synthetic conversation/turn identity')
    seen, seen_units = set(), set()
    for row in rows:
        unit = (row['conversation_id'], row['turn_id'])
        turn = turns.get(unit)
        if (row['annotation_id'] in seen or unit in seen_units or turn is None or turn['speaker'] != 'student' or
            row.get('speaker') != 'student' or row.get('namespace') != 'student_skill' or
            type(row['start']) is not int or type(row['end']) is not int or
            not 0 <= row['start'] < row['end'] <= len(turn['text']) or
            turn['text'][row['start']:row['end']] != row['span'] or
            not row['labels'] or not set(row['labels']) <= set(vocab) or
            ('other' in row['labels'] and len(row['labels']) != 1) or
            row.get('label_origin') != 'authored_simulation_template'):
            raise ValueError('invalid synthetic exact-span annotation')
        seen.add(row['annotation_id'])
        seen_units.add(unit)
    if len(rows) != len(turns):
        raise ValueError('one whole-sentence annotation per synthetic student turn required')
    if any(r['start'] != 0 or r['end'] != len(turns[(r['conversation_id'], r['turn_id'])]['text']) for r in rows):
        raise ValueError('this sentence-classification demo requires whole-sentence action spans')
    splits = grouped_split(conversations, seed)
    links = {}
    for c in conversations:
        if not c.get('patient_id') or not c.get('family_id') or c['source_sha256'] != digest(c['turns']):
            raise ValueError('synthetic patient/family and transcript hash required')
        for key in [('patient', c['patient_id']), ('family', c['family_id'])] + [('text', ' '.join(t['text'].lower().split())) for t in c['turns']]:
            links.setdefault(key, set()).add(splits[c['conversation_id']])
    if any(len(v) > 1 for v in links.values()):
        raise ValueError('patient/family/duplicate leakage across synthetic splits')
    train = [r for r in rows if splits[r['conversation_id']] == 'train']
    test = [r for r in rows if splits[r['conversation_id']] == 'test']
    if not train or not test:
        raise ValueError('synthetic development and test groups required')
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.multiclass import OneVsRestClassifier
    from sklearn.preprocessing import MultiLabelBinarizer
    mlb = MultiLabelBinarizer(classes=vocab)
    y = mlb.fit_transform([r['labels'] for r in train])
    if any(len(set(y[:, i])) != 2 for i in range(len(vocab))):
        raise ValueError('every simulated label needs positive and negative training support')
    vectorizer = TfidfVectorizer(ngram_range=(1, 2))
    model = OneVsRestClassifier(LogisticRegression(max_iter=1000, random_state=seed))
    model.fit(vectorizer.fit_transform([r['span'] for r in train]), y)
    learned = mlb.inverse_transform(model.predict(vectorizer.transform([r['span'] for r in test])))
    case = Case.model_validate_json((ROOT / 'cases/eli_brooks.json').read_text())
    predictions = []
    for row, labels in zip(test, learned):
        keyword, omitted = action_prediction(row['span'], case)
        predictions.append({'annotation_id': row['annotation_id'], 'start': row['start'], 'end': row['end'],
            'trained_labels': list(labels) or ['other'], 'keyword_annotations': keyword['annotations'],
            'omitted_keyword_hits': omitted, 'model_id': 'synthetic_tfidf_logistic_v1',
            'prompt_version': 'not_applicable', 'span_policy': 'one whole student sentence'})
    # Serialize predictions before loading held-out labels into any metric calculation.
    save(directory / 'frozen_action_predictions.json', predictions)
    predictions = json.loads((directory / 'frozen_action_predictions.json').read_text())
    truth = [set(r['labels']) for r in test]
    result = {'mode': 'OFFLINE EXECUTED', 'reference_kind': 'SIMULATED AUTHOR LABELS',
        'split_counts': dict(Counter(splits.values())), 'annotation_counts': dict(Counter(splits[r['conversation_id']] for r in rows)),
        'patients': len({c['patient_id'] for c in conversations}), 'cross_split_links': 0,
        'synthetic_group_held_out': True, 'real_learner_held_out': False,
        'prediction_sha256': sha256((directory / 'frozen_action_predictions.json').read_bytes()).hexdigest(),
        'trained_sentence_classifier': label_metrics(truth, [set(r['trained_labels']) for r in predictions], CRITICAL),
        'keyword_sentence_classifier': label_metrics(truth, [{label for a in r['keyword_annotations'] for label in a['labels']} for r in predictions], CRITICAL),
        'exact_span_keyword': {'tp': 0, 'fp': 0, 'fn': 0},
        'limitations': ['Training and test use shared authored phrase banks and synthetic neutral context.',
                       'No prompted LLM predictions; no production classifier replacement or real learner performance.',
                       'The trained baseline classifies supplied whole-sentence spans; it does not learn arbitrary span boundaries.',
                       'Wilson intervals and positive-support floors are descriptive engineering diagnostics on template data.']}
    for row, pred in zip(test, predictions):
        expected = {(row['start'], row['end'], label) for label in row['labels']}
        actual = {(a['start'], a['end'], label) for a in pred['keyword_annotations'] for label in a['labels']}
        for key, count in [('tp', len(expected & actual)), ('fp', len(actual - expected)), ('fn', len(expected - actual))]:
            result['exact_span_keyword'][key] += count
    save(directory / 'action_split_assignments.json', splits)
    return result


def difficulty_checks(decisions: dict) -> tuple[dict, list]:
    offsets = decisions['difficulty_probe_offsets']
    if set(offsets) != {'straightforward', 'typical', 'difficult'} or any(type(v) is not int for v in offsets.values()) or not offsets['straightforward'] <= offsets['typical'] <= offsets['difficult']:
        raise ValueError('ordered integer difficulty offsets required')
    runs, _ = encounter_runs()
    # Regenerate using the input offsets rather than silently ignoring a replacement vector.
    discoveries, violations, replay_count = {}, [], 0
    for record in runs:
        base = Case.model_validate_json((ROOT / record['case_source']['path']).read_text())
        original = base.model_dump()
        case = base.model_copy(deep=True)
        for tier in ('reluctant', 'hidden'):
            case.trust.thresholds[tier] = base.trust.thresholds[tier] + offsets[record['preset']]
        case.difficulty.preset = record['preset']
        turns = [ScriptTurn(t['utterance'], Intent.model_validate(t['intent'])) for t in record['turns']]
        trace = run_script(case, turns, source=record['case_source'])
        replay_count += fingerprint(trace) == fingerprint(replay(trace, case))
        record['turns'] = trace['turns']
        record['discovery_count'] = len(trace['final_state']['disclosed'])
        discoveries.setdefault((record['case_id'], record['level']), {})[record['preset']] = record['discovery_count']
        changed = case.model_dump()
        if any(changed[k] != original[k] for k in original if k not in {'trust', 'difficulty'}):
            violations.append('clinical content changed')
    ordered = all(v['straightforward'] >= v['typical'] >= v['difficult'] for v in discoveries.values())
    debrief, records = run_all()
    progression = progression_checks(decisions['progression_policy'])
    return {'mode': 'OFFLINE EXECUTED', 'runs': len(runs), 'turns': sum(len(r['turns']) for r in runs),
            'replay_matches': replay_count, 'clinical_content_unchanged': not violations,
            'ordered_discoveries': ordered, 'threshold_offsets': offsets,
            'discoveries': [{'case_id': cid, 'scripted_level': level, **counts} for (cid, level), counts in discoveries.items()],
            'straightforward_minus_difficult_mean': mean(v['straightforward'] - v['difficult'] for v in discoveries.values()),
            'authored_followup_replays': debrief['counts']['branches_replayed'],
            'uncertain_branch_records': sum(bool(r['branch']['uncertain_predicates']) for r in records),
            'progression': progression,
            'status': 'PASS' if not violations and ordered and replay_count == len(runs) and progression['status'] == 'PASS' else 'FAIL',
            'full_preset_approval': 'SIMULATED ASSUMPTION ONLY', 'observed_learner_difficulty': 'NOT EVALUABLE'}, runs


def synthetic_reviews(directory: Path, policy: dict, runs: list) -> dict:
    stage = prepare_next(directory / 'review_stage')
    workspace = directory / 'review_stage'
    cases = {r['case_id']: Case.model_validate_json((ROOT / r['case_source']['path']).read_text()) for r in runs}
    # Add fresh disclosure and constructor-known semantic items under a separate current-source lock.
    for kind in ('release', 'semantic'):
        tasks, predictions = [], []
        if kind == 'release':
            entries = [(r, t) for r in runs for t in r['turns']]
            for r, t in entries:
                pid = digest([stage['protocol_lock'], kind, r['script_id'], t['turn']])[:24]
                case_hash = r['case_source']['sha256']
                tasks.append({'packet_id': pid, 'kind': kind, 'protocol_lock': stage['protocol_lock'],
                    'case_sha256': case_hash, 'case_version': r['case_version'],
                    'case': approved_case({'case_id': r['case_id'], 'case_sha256': case_hash}),
                    'context': {'student_utterance': t['utterance']},
                    'text_units': [{'turn': t['turn'], 'speaker': 'student', 'text': t['utterance']}]})
                predictions.append({'packet_id': pid, 'answer': {'expected_fact_ids': sorted(t['allowed_fact_ids'])},
                    'model_id': 'disclosure_engine_echo', 'prompt_version': 'not_applicable',
                    'source_mapping': {'script_id': r['script_id'], 'turn': t['turn']}})
        else:
            for c in challenges():
                if c['kind'] not in {'approved_exact', 'invented_number', 'unsupported_prose'}:
                    continue
                pid = digest([stage['protocol_lock'], kind, c['challenge_id']])[:24]
                tasks.append({'packet_id': pid, 'kind': kind, 'protocol_lock': stage['protocol_lock'],
                    'case_sha256': c['case_source']['sha256'], 'case_version': c['case_version'],
                    'case': approved_case({'case_id': c['case_id'], 'case_sha256': c['case_source']['sha256']}),
                    'context': {'reply': c['reply']},
                    'text_units': [{'turn': 1, 'speaker': 'patient', 'text': c['reply']}]})
                problems = verifier.deterministic_checks(cases[c['case_id']], c['reply'], c['cited_fact_ids'], c['allowed_fact_ids'], [], c['student_utterance'])
                predictions.append({'packet_id': pid, 'answer': {'expected_supported': not bool(problems)},
                    'synthetic_constructor_label': {'expected_supported': c['kind'] == 'approved_exact'},
                    'model_id': 'mechanical_check_surrogate_not_semantic_judge', 'prompt_version': 'not_applicable',
                    'source_mapping': {'challenge_id': c['challenge_id']}})
        tasks.sort(key=lambda t: t['packet_id'])
        predictions.sort(key=lambda t: t['packet_id'])
        batch = workspace / kind
        batch.mkdir(mode=0o700)
        manifest = {'workflow_version': 1, 'toy': False, 'scope': 'SIMULATION ONLY; not independent review',
                    'protocol_lock': stage['protocol_lock'], 'packet_ids': [t['packet_id'] for t in tasks], 'view_sha256': digest(tasks)}
        save(batch / 'review_manifest.json', manifest)
        save(batch / 'blinded_tasks.json', tasks)
        save(batch / 'PRIVATE_predictions.json', predictions)
        stage['batches'][kind] = {'tasks': len(tasks), 'manifest_sha256': sha256((batch / 'review_manifest.json').read_bytes()).hexdigest(),
                                'predictions_sha256': sha256((batch / 'PRIVATE_predictions.json').read_bytes()).hexdigest()}
    save(workspace / 'stage.json', stage)
    rng = random.Random(policy['seed'])
    if any(type(policy[k]) is not int or policy[k] < 2 for k in ('flip_every_a', 'flip_every_b')):
        raise ValueError('synthetic perturbation periods must be integers >= 2')
    result = {}
    for kind in stage['batches']:
        batch = workspace / kind
        tasks = json.loads((batch / 'blinded_tasks.json').read_text())
        preds = {r['packet_id']: r for r in json.loads((batch / 'PRIVATE_predictions.json').read_text())}
        rows_by_slot = {}
        for slot in ('a', 'b'):
            rows = []
            for i, task in enumerate(tasks):
                pid = task['packet_id']
                answer = deepcopy(preds[pid].get('synthetic_constructor_label', preds[pid]['answer']))
                if kind == 'domain' and i % 11 == 0:
                    answer = {'score': 'N/A', 'na_reason': 'Synthetic unavailable-domain control; not a human judgment.'}
                if i % policy['flip_every_' + slot] == 1:
                    if kind in {'claim', 'semantic'}:
                        answer['expected_supported'] = not answer['expected_supported']
                    elif kind == 'domain' and answer['score'] != 'N/A':
                        answer['score'] = max(1, min(4, answer['score'] + rng.choice((-1, 1))))
                    elif kind == 'release':
                        answer['expected_fact_ids'] = []
                    elif kind == 'action':
                        a = answer['annotations'][0]
                        a['labels'], a['rubric_mapping'] = ['other'], []
                unit = task['text_units'][0]
                evidence = [] if answer.get('score') == 'N/A' else [{'kind': 'transcript_span',
                    'turn': unit['turn'], 'speaker': unit['speaker'], 'start': 0, 'end': len(unit['text']), 'quote': unit['text']}]
                rows.append({'packet_id': pid, 'answer': answer, 'evidence': evidence,
                    'rationale': 'Generated transport control: seeded perturbation, engine echo or constructor label; not independent review.',
                    'reviewed_at': '2026-10-10T00:00:00Z'})
            rows_by_slot[slot] = rows
            save(batch / ('synthetic_' + slot + '.json'), rows)
        decisions = []
        for a, b in zip(rows_by_slot['a'], rows_by_slot['b']):
            if a['answer'] != b['answer']:
                # A deterministic synthetic tie breaker; independence is not asserted.
                decisions.append(deepcopy(a))
        save(batch / 'synthetic_adjudicator.json', decisions)
        def spec(path):
            return {'path': path.name, 'sha256': sha256(path.read_bytes()).hexdigest()}
        config = {'version': 1, 'mode': 'development_reference',
            'manifest': spec(batch / 'review_manifest.json'), 'tasks': spec(batch / 'blinded_tasks.json'),
            'predictions': spec(batch / 'PRIVATE_predictions.json'),
            'submissions': [spec(batch / ('synthetic_' + s + '.json')) | {'slot': s, 'reviewer_id': 'synthetic-' + s,
                'provenance': {'type': 'synthetic', 'description': 'Seeded simulated source; correlated construction, no person or authority'}}
                for s in ('a', 'b', 'adjudicator')]}
        save(batch / 'reference_simulated_v1.json', config)
        report = review_stage(workspace, kind, batch / 'reference_simulated_v1.json')
        save(batch / 'review_report.json', report)
        result[kind] = {'reference_kind': 'SIMULATED', 'tasks': len(tasks),
            'transport': report['review_transport'], 'paired_agreement': report['review_reference']['paired_agreement_count'],
            'disagreements': report['review_reference']['disagreements'],
            'diagnostic_differences': len(report['diagnostic_answer_differences']),
            'comparison': report['prediction_comparison'], 'domain_agreement': report['paired_domain_agreement']}
    return {'mode': 'OFFLINE EXECUTED WITH SIMULATED REFERENCES', 'batches': result,
            'independent_human_reviews': 0, 'generation_description': policy['generation_description'],
            'limitations': ['Disclosure expectations echo the engine; not independent disclosure accuracy.',
                           'Action, claim and numeric domain references start from baseline predictions and are perturbed.',
                           'Simulated adjudication chooses A; agreement and errors are partly constructed.',
                           'Constructor semantic labels test known injected examples, not a clinically validated semantic judge.']}


def statistical_scenarios(data: dict, draws: int, bootstrap_draws: int) -> dict:
    results = {}
    for scenario in data['scenarios']:
        if scenario.get('source_kind') != 'synthetic_fixture' or not scenario.get('generation_description'):
            raise PermissionError('simulation mode rejects observed learner data')
        if scenario.get('design') != 'unstratified_parallel':
            raise ValueError('only unstratified parallel learner-level assignments supported')
        name = scenario['scenario']
        if name in results:
            raise ValueError('duplicate MCPT scenario')
        values, counts = learner_changes(scenario['roster'], scenario['encounters'])
        plan = dict(PLAN, draws=draws, bootstrap_draws=bootstrap_draws, seed=scenario['seed'])
        stats = monte_carlo(values['feedback'], values['standard'], draws=draws,
                            bootstrap_draws=bootstrap_draws, seed=scenario['seed']) if all(len(v) >= 2 for v in values.values()) else None
        results[name] = {'scope': 'SYNTHETIC MATHEMATICAL SCENARIO; no learning-effect evidence',
            'input_sha256': digest(scenario), 'generation_description': scenario['generation_description'],
            'assumed_feedback_shift': scenario['assumed_feedback_shift'], 'plan': plan, 'plan_sha256': digest(plan),
            'denominators': counts, 'statistics': stats, 'status': 'EVALUATED' if stats else 'NOT EVALUABLE'}
    from backend_kelsch.app.study.simulation_inputs import SCENARIOS
    if set(results) != set(SCENARIOS):
        raise ValueError('all five required MCPT scenarios must be supplied')
    return results
