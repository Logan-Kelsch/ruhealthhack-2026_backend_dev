"""Next-stage evidence must stay blinded, pinned, and separate from learner effects."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from backend_kelsch.app.study.next_review import prepare_next, review_stage, action_prediction
from backend_kelsch.app.study.protocol import digest


@pytest.fixture(scope='module')
def stage(tmp_path_factory):
    workspace = tmp_path_factory.mktemp('next-stage-parent') / 'stage'
    prepared = prepare_next(workspace)
    return workspace, prepared


def make_config(stage, tmp_path, kind, disagree=False, partial=False):
    workspace, prepared = stage
    base = workspace / kind
    manifest = json.loads((base / 'review_manifest.json').read_text())
    tasks = json.loads((base / 'blinded_tasks.json').read_text())
    predictions = json.loads((base / 'PRIVATE_predictions.json').read_text())
    by_id = {r['packet_id']: r['answer'] for r in predictions}
    config = {'version': 1, 'mode': 'development_reference', 'submissions': []}
    def spec(path):
        return {'path': str(path), 'sha256': sha256(path.read_bytes()).hexdigest()}
    config['manifest'] = spec(base / 'review_manifest.json')
    config['tasks'] = spec(base / 'blinded_tasks.json')
    config['predictions'] = spec(base / 'PRIVATE_predictions.json')
    for slot in ('a', 'b'):
        rows = []
        for t in tasks:
            answer = deepcopy(by_id[t['packet_id']])
            if disagree and slot == 'b' and t == tasks[0]:
                answer = {'expected_supported': False}
            u = t['text_units'][0]
            ev = [] if answer.get('score') == 'N/A' else [{'kind': 'transcript_span', 'turn': u['turn'],
                'speaker': u['speaker'], 'start': 0, 'end': len(u['text']), 'quote': u['text']}]
            rows.append({'packet_id': t['packet_id'], 'answer': answer, 'evidence': ev,
                         'rationale': 'Synthetic importer exercise, not an independent review',
                         'reviewed_at': '2026-10-10T16:00:00Z'})
        if partial and slot == 'b':
            rows.pop()
        path = tmp_path / (slot + '.json')
        path.write_text(json.dumps({'manifest': manifest, 'slot': slot, 'reviewer_id': 'fixture-' + slot, 'answers': rows}))
        config['submissions'].append(spec(path) | {'slot': slot, 'reviewer_id': 'fixture-' + slot,
            'provenance': {'type': 'synthetic', 'description': 'Tests only'}})
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(config))
    return path, config


def test_prepare_blinds_answers_and_deduplicates_action_units(stage):
    workspace, prepared = stage
    assert set(prepared['batches']) == {'action', 'claim', 'domain'}
    assert prepared['batches']['domain']['tasks'] == 42
    action = json.loads((workspace / 'action/blinded_tasks.json').read_text())
    keys = [(t['case']['case_id'], t['context']['text']) for t in action]
    assert len(keys) == len(set(keys))
    for kind in prepared['batches']:
        tasks = json.loads((workspace / kind / 'blinded_tasks.json').read_text())
        manifest = json.loads((workspace / kind / 'review_manifest.json').read_text())
        assert digest(tasks) == manifest['view_sha256']
        html = (workspace / kind / 'reviewer_a.html').read_text()
        assert 'PRIVATE_predictions' not in html and 'source_mapping' not in html
        for t in tasks:
            assert 'expected' not in t and 'answer' not in t and 'score' not in t['context']
        assert all('expected_actions' not in t['context'] for t in tasks)
    claims = json.loads((workspace / 'claim/blinded_tasks.json').read_text())
    assert any(t['context']['candidate_claim'].get('text') for t in claims)
    assert any(u['speaker'].startswith('note:') for t in claims for u in t['text_units'])
    assert 'PENDING' in (workspace / 'clinical_and_difficulty_decisions.md').read_text()


def test_prepare_refuses_overwrite(stage):
    with pytest.raises(ValueError, match='new workspace'):
        prepare_next(stage[0])


@pytest.mark.parametrize('kind', ['action', 'claim', 'domain'])
def test_roundtrip_reports_development_comparison_not_learning(stage, tmp_path, kind):
    path, _ = make_config(stage, tmp_path, kind)
    result = review_stage(stage[0], kind, path)
    assert result['review_transport'] == 'PASS'
    assert result['prediction_comparison']['held_out'] is False
    assert result['learner_mcpt'] == 'NOT EVALUABLE'
    assert result['human_authority'] == 'NOT VERIFIED'
    if kind == 'domain':
        assert result['paired_domain_agreement'] is not None


def test_pending_is_preserved_and_adjudication_waits_for_pairs(stage, tmp_path):
    path, _ = make_config(stage, tmp_path, 'claim', partial=True)
    result = review_stage(stage[0], 'claim', path)
    assert result['pending_packet_ids'] and result['prediction_comparison'] is None
    with pytest.raises(ValueError, match='finish both'):
        review_stage(stage[0], 'claim', path, adjudicate=True)


def test_adjudicator_gets_only_disagreements_and_exact_original_evidence(stage, tmp_path):
    path, _ = make_config(stage, tmp_path, 'claim', disagree=True)
    review_stage(stage[0], 'claim', path, adjudicate=True)
    html = (tmp_path / 'adjudicator.html').read_text()
    encoded = html.split('const data=', 1)[1].split(';\nconst $=', 1)[0]
    data = json.loads(encoded)
    assert len(data['tasks']) == 1
    pair = next(iter(data['independent_answers'].values()))
    assert len(pair) == 2 and all(r['evidence'] and r['rationale'] for r in pair)
    assert 'PRIVATE_predictions' not in html


def test_new_predictions_cannot_be_substituted_after_review(stage, tmp_path):
    path, config = make_config(stage, tmp_path, 'claim')
    changed = tmp_path / 'changed_predictions.json'
    rows = json.loads((stage[0] / 'claim/PRIVATE_predictions.json').read_text())
    rows[0]['answer']['expected_supported'] = False
    changed.write_text(json.dumps(rows))
    config['predictions'] = {'path': str(changed), 'sha256': sha256(changed.read_bytes()).hexdigest()}
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match='frozen before'):
        review_stage(stage[0], 'claim', path)


def test_wrong_stage_kind_rejected(stage, tmp_path):
    path, _ = make_config(stage, tmp_path, 'claim')
    with pytest.raises(ValueError, match='frozen stage'):
        review_stage(stage[0], 'domain', path)


def test_changed_current_sources_require_new_batch(stage, tmp_path, monkeypatch):
    path, _ = make_config(stage, tmp_path, 'claim')
    monkeypatch.setattr('backend_kelsch.app.study.next_review.source_lock', lambda: {'changed': 'source'})
    with pytest.raises(ValueError, match='current sources differ'):
        review_stage(stage[0], 'claim', path)


def test_unsupported_human_claim_is_retained_as_diagnostic(stage, tmp_path):
    path, config = make_config(stage, tmp_path, 'claim')
    for spec in config['submissions']:
        source = tmp_path / (spec['slot'] + '.json')
        value = json.loads(source.read_text())
        value['answers'][0]['answer']['expected_supported'] = False
        # A note citation is legal evidence for a feedback claim, never for a rubric score.
        task = json.loads((stage[0] / 'claim/blinded_tasks.json').read_text())[0]
        u = next(u for u in task['text_units'] if u['speaker'].startswith('note:'))
        value['answers'][0]['evidence'] = [{'kind': 'transcript_span', 'turn': 0, 'speaker': u['speaker'],
                                          'start': 0, 'end': len(u['text']), 'quote': u['text']}]
        source.write_text(json.dumps(value))
        spec['sha256'] = sha256(source.read_bytes()).hexdigest()
    path.write_text(json.dumps(config))
    result = review_stage(stage[0], 'claim', path)
    assert result['prediction_comparison']['metrics']['claim']['fp'] == 1
    assert len(result['diagnostic_answer_differences']) == 1


def test_keyword_offsets_do_not_invent_occurrence(load_golden, monkeypatch):
    from app.schemas.encounter import Hit, Intent
    monkeypatch.setattr('backend_kelsch.app.study.next_review.keyword_classify',
                        lambda *a: Intent(actions=[Hit(id='safety_netting', span='Return.')]))
    answer, dropped = action_prediction('Return. Return.', load_golden('eli_brooks'))
    assert answer['annotations'][0]['labels'] == ['other']
    assert dropped[0]['reason'] == 'span absent or ambiguous'
