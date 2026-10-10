"""Synthetic transport tests; no clinical judgments or learner outcomes."""
import json
from datetime import datetime, timezone

import pytest

from backend_kelsch.app.study.protocol import lock_manifest, make_packets
from backend_kelsch.app.study.review_kit import (
    sample_ids, supplement, prepare_kit, supplement_workspace, analyze_supplement,
)
from backend_kelsch.app.study.workflow import save, view


def submissions(work, packets, manifest):
    paths = []
    for slot in ('a', 'b'):
        path = work / f'submission_{slot}.json'
        entries = []
        for i, p in enumerate(packets):
            text = p['context']['reply']
            entries.append({'packet_id': p['packet_id'],
                'answer': {'expected_supported': slot == 'b' and i == 0},
                'evidence': [{'kind': 'transcript_span', 'turn': 1, 'speaker': 'patient',
                             'start': 0, 'end': len(text), 'quote': text}],
                'reviewed_at': datetime.now(timezone.utc).isoformat()})
        save(path, {'manifest': manifest, 'slot': slot, 'reviewer_id': f'test-{slot}', 'answers': entries})
        paths.append(path)
    return paths


def test_sample_coverage_and_separate_blinded_supplement(tmp_path):
    base = lock_manifest(); historical, _ = make_packets(base)
    selected = [p for p in historical if p['packet_id'] in sample_ids()]
    assert len(selected) == 12
    assert len({(p['case_id'], p['kind']) for p in selected}) == 12
    lock, packets = supplement()
    assert len(packets) == 12 and lock['historical_protocol_lock'] == base['lock_id']
    assert not ({p['packet_id'] for p in packets} & {p['packet_id'] for p in historical})
    for p in packets:
        data = json.dumps(view(p))
        assert 'expected_mechanics' not in data and 'faculty_expected_supported' not in data
        assert 'deterministic_blocked' not in data and 'challenge_id' not in data
    prepare_kit(tmp_path / 'sample', 'sample')
    prepare_kit(tmp_path / 'supplement', 'supplement')
    assert len(make_packets(lock_manifest())[0]) == 287


def test_stale_source_private_path_and_toy_rejection(tmp_path):
    work = tmp_path / 'supplement'; manifest = prepare_kit(work, 'supplement')
    packets = supplement()[1]; paths = submissions(work, packets, manifest)
    a = json.loads(paths[0].read_text()); save(paths[0], a | {'toy': True})
    with pytest.raises(ValueError, match='toy'):
        analyze_supplement(work, paths, command='validate')
    save(work / 'manifest.json', manifest | {'protocol_lock': 'stale'})
    with pytest.raises(ValueError, match='lock'):
        supplement_workspace(work)
    (tmp_path / 'checkout').mkdir(); (tmp_path / 'checkout/.git').mkdir()
    with pytest.raises(ValueError, match='outside'):
        prepare_kit(tmp_path / 'checkout/private', 'supplement')


def test_partial_disagreement_adjudication_and_receipt(tmp_path):
    work = tmp_path / 'supplement'; manifest = prepare_kit(work, 'supplement')
    packets = supplement()[1]; paths = submissions(work, packets, manifest)
    assert analyze_supplement(work, paths[:1], command='validate')['resolved'] == 0
    result = analyze_supplement(work, paths, command='validate')
    assert result['resolved'] == 11 and result['counts']['awaiting_adjudication'] == 1
    assert result['clinical_accuracy'] == 'NOT EVALUABLE'
    assert analyze_supplement(work, paths, command='adjudicate')['disagreements'] == 1
    b = json.loads(paths[1].read_text())
    third = work / 'third.json'
    save(third, b | {'slot': 'adjudicator', 'reviewer_id': 'test-c', 'answers': b['answers'][:1]})
    paths.append(third)
    assert analyze_supplement(work, paths, command='validate')['resolved'] == 12
    assert analyze_supplement(work, paths, command='verify-export')['export_integrity'] == 'PASS'
    b['answers'][0]['rationale'] = 'altered after export'; save(paths[1], b)
    with pytest.raises(ValueError, match='receipt'):
        analyze_supplement(work, paths, command='verify-export')


def test_invalid_evidence_duplicate_reviewers_and_early_adjudication(tmp_path):
    work = tmp_path / 'supplement'; manifest = prepare_kit(work, 'supplement')
    packets = supplement()[1]; paths = submissions(work, packets, manifest)
    a = json.loads(paths[0].read_text())
    a['answers'][0]['evidence'][0]['quote'] = 'invented'; save(paths[0], a)
    with pytest.raises(ValueError, match='span'):
        analyze_supplement(work, paths, command='validate')
    paths = submissions(work, packets, manifest)
    b = json.loads(paths[1].read_text()); save(paths[1], b | {'reviewer_id': 'test-a'})
    with pytest.raises(ValueError, match='distinct'):
        analyze_supplement(work, paths, command='validate')
    save(paths[1], b | {'slot': 'adjudicator', 'reviewer_id': 'test-c'})
    with pytest.raises(ValueError, match='both independent'):
        analyze_supplement(work, paths, command='validate')
