"""Review replacement cannot erase provenance, evidence, or unresolved coverage."""
import copy
from hashlib import sha256
import json

import pytest

from backend_kelsch.app.study.development_reference import load_reference
from backend_kelsch.app.study.development_evaluation import prediction_comparison, reviewed_domain_agreement
from backend_kelsch.app.study.protocol import digest


@pytest.fixture
def bundle(tmp_path):
    task = {'packet_id': 'p1', 'kind': 'semantic', 'protocol_lock': 'locked',
        'case_sha256': 'case-hash', 'case': {'sha256': 'case-hash', 'facts': [{'id': 'f1'}]},
        'context': {'reply': 'Hi.'}, 'text_units': [{'turn': 1, 'speaker': 'patient', 'text': 'Hi.'}]}
    row = {'packet_id': 'p1', 'answer': {'expected_supported': True}, 'rationale': 'Greeting adds no clinical claim.',
        'reviewed_at': '2026-10-10T15:00:00Z',
        'evidence': [{'kind': 'transcript_span', 'turn': 1, 'speaker': 'patient', 'start': 0, 'end': 3, 'quote': 'Hi.'}]}
    manifest = {'protocol_lock': 'locked', 'packet_ids': ['p1'], 'view_sha256': digest([task])}
    config = {'version': 1, 'mode': 'development_reference', 'submissions': []}
    def write(name, value):
        path = tmp_path / name
        path.write_text(json.dumps(value))
        return {'path': name, 'sha256': sha256(path.read_bytes()).hexdigest()}
    config['manifest'] = write('manifest.json', manifest)
    config['tasks'] = write('tasks.json', [task])
    for slot in ('a', 'b'):
        config['submissions'].append(write(slot+'.json', [row]) | {'slot': slot, 'reviewer_id': slot,
            'provenance': {'type': 'ai', 'description': 'AI fixture'}})
    path = tmp_path / 'reference.json'
    def save():
        path.write_text(json.dumps(config))
        return path
    save()
    return config, task, row, manifest, write, save


def test_replace_sources_with_human_envelopes_still_requires_authority(bundle):
    config, task, row, manifest, write, save = bundle
    before = load_reference(save())
    for spec in config['submissions']:
        spec.update(write(spec['slot']+'.json', {'manifest': manifest, 'slot': spec['slot'], 'reviewer_id': spec['reviewer_id'], 'answers': [row]}))
        spec['provenance'] = {'type': 'human', 'description': 'Declared human reviewer, verification separate'}
    after = load_reference(save())
    assert before['summary']['resolved_count'] == after['summary']['resolved_count'] == 1
    assert after['summary']['human_gate'] == 'NOT EVALUABLE'
    assert after['summary']['reviewer_authority'] == 'NOT VERIFIED'
    assert after['resolved']['p1']['sources'][0]['provenance']['type'] == 'human'


def test_disagreement_needs_a_third_source(bundle):
    config, _, row, _, write, save = bundle
    negative = copy.deepcopy(row)
    negative['answer']['expected_supported'] = False
    config['submissions'][1].update(write('b.json', [negative]))
    assert load_reference(save())['summary']['pending_count'] == 1
    config['submissions'].append(write('c.json', [negative]) | {'slot': 'adjudicator', 'reviewer_id': 'c',
        'provenance': {'type': 'ai', 'description': 'AI adjudication fixture'}})
    result = load_reference(save())
    assert result['summary']['pending_count'] == 0
    assert result['resolved']['p1']['answer'] == {'expected_supported': False}


@pytest.mark.parametrize('mutation', ['duplicate', 'bad_span', 'bad_label', 'bad_timestamp', 'unknown', 'bad_fact'])
def test_bad_reviews_rejected(bundle, mutation):
    config, _, row, _, write, save = bundle
    bad = copy.deepcopy(row)
    if mutation == 'bad_span': bad['evidence'][0]['end'] = 2
    if mutation == 'bad_label': bad['answer']['expected_supported'] = 'true'
    if mutation == 'bad_timestamp': bad['reviewed_at'] = '2026-10-10T15:00:00'
    if mutation == 'unknown': bad['packet_id'] = 'unknown'
    if mutation == 'bad_fact': bad['evidence'] = [{'kind': 'source_fact', 'fact_id': 'missing', 'case_sha256': 'case-hash'}]
    config['submissions'][0].update(write('a.json', [bad, bad] if mutation == 'duplicate' else [bad]))
    with pytest.raises(ValueError): load_reference(save())


def test_tampered_source_rejected_even_if_task_ids_match(bundle):
    _, _, _, _, _, save = bundle
    path = save()
    (path.parent/'a.json').write_text('[]')
    with pytest.raises(ValueError, match='digest'): load_reference(path)


def test_missing_or_pending_answers_stay_missing(bundle):
    config, _, row, _, write, save = bundle
    row['answer']['expected_supported'] = None
    config['submissions'][0].update(write('a.json', [row]))
    assert load_reference(save())['summary']['pending_count'] == 1


def test_duplicate_identity_rejected(bundle):
    config, _, _, _, _, save = bundle
    config['submissions'][1]['reviewer_id'] = 'a'
    with pytest.raises(ValueError, match='distinct'): load_reference(save())


def test_predictions_require_exact_coverage_and_provenance(bundle):
    config, _, _, _, write, save = bundle
    config['predictions'] = write('predictions.json', [{'packet_id': 'p1', 'answer': {'expected_supported': False}, 'model_id': 'fixture-model', 'prompt_version': '1'}])
    result = prediction_comparison(load_reference(save()))
    assert result['metrics']['semantic']['fn'] == 1
    config['predictions'] = write('predictions.json', [])
    with pytest.raises(ValueError, match='exactly'): prediction_comparison(load_reference(save()))


def test_na_domains_are_excluded_from_numeric_agreement():
    ref = {'tasks': {'p': {'kind': 'domain', 'context': {'domain_id': 1}}},
        'submissions': {'a': {'p': {'answer': {'score': 'N/A'}}}, 'b': {'p': {'answer': {'score': 4}}}}}
    result = reviewed_domain_agreement(ref)
    assert result['domains'] == {} and result['pairs_with_na_by_domain'] == {'1': 1}


@pytest.mark.parametrize('kind,answer', [
    ('release', {'expected_fact_ids': ['f1']}),
    ('claim', {'expected_supported': True}),
    ('domain', {'score': 3}),
    ('domain', {'score': 'N/A', 'na_reason': 'No opportunity to observe this domain.'}),
    ('action', {'annotations': [{'start': 0, 'end': 3, 'span': 'Hi.', 'labels': ['other'], 'rubric_mapping': []}]}),
])
def test_all_development_task_kinds_can_use_the_same_source_location(bundle, kind, answer):
    config, task, row, manifest, write, save = bundle
    task['kind'] = kind
    task['context'].update(text='Hi.', speaker='student', domain_id=1)
    row['answer'] = answer
    if answer.get('score') == 'N/A': row['evidence'] = []
    manifest['view_sha256'] = digest([task])
    config['tasks'] = write('tasks.json', [task])
    config['manifest'] = write('manifest.json', manifest)
    for spec in config['submissions']: spec.update(write(spec['slot']+'.json', [row]))
    result = load_reference(save())
    assert result['summary']['coverage_by_kind'] == {kind: 1}
    assert result['summary']['human_gate'] == 'NOT EVALUABLE'
