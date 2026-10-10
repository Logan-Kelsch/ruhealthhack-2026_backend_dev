"""Toy-only technical tests; no test label is an independent faculty review."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from backend_kelsch.app.debrief_probe.evaluation import ROOT
from backend_kelsch.app.study.protocol import lock_manifest, make_packets
from backend_kelsch.app.study.workflow import (approved_case, evidence_check, prepare, private_path,
    save, validate, verify_export, view, workspace_packets, adjudicate)
from backend_kelsch.scripts.review_workflow import demo


def test_toy_independence_adjudication_and_na(tmp_path):
    work = tmp_path / 'toy'
    result = demo(work)
    assert result['before']['counts']['awaiting_adjudication'] == 2
    assert result['after']['counts']['adjudicated'] == 2
    assert result['after']['audit']['events'] == 10
    assert result['after']['genuine_review_rows'] == 0
    assert not (work / 'validated_reviews.jsonl').exists()
    with pytest.raises(ValueError, match='toy workspace'):
        validate(work, [work / 'submission_a.json'])
    a = (work / 'reviewer_a.html').read_text()
    assert 'toy-b' not in a and 'independent_answers":' not in a
    assert 'independent_answers":' in (work / 'adjudicator.html').read_text()


def test_all_locked_packet_views_are_allowlisted():
    packets, _ = make_packets(lock_manifest())
    assert len(packets) == 287
    for packet in packets:
        poisoned = deepcopy(packet)
        poisoned['context'].update(level='SECRET_LEVEL', score='SECRET_SCORE', actual_disclosures='SECRET_RELEASE',
                                    verifier_verdict='SECRET_VERDICT', explicit_intent='SECRET_INTENT')
        if packet['kind'] == 'claim':
            poisoned['context']['claim'].update(confidence='SECRET_CONFIDENCE', label_origin='SECRET_ORIGIN')
        data = json.dumps(view(poisoned))
        assert 'SECRET_' not in data
        assert all(f['status'] == 'approved' for f in view(packet)['case']['facts'])
        assert all('by' not in f['source'] for f in view(packet)['case']['facts'])


def test_private_destinations_reject_git_and_symlinks(tmp_path):
    with pytest.raises(ValueError):
        prepare(ROOT / 'private')
    (tmp_path / 'link').symlink_to(ROOT, target_is_directory=True)
    with pytest.raises(ValueError):
        private_path(tmp_path / 'link' / 'answers.json')
    checkout = tmp_path / 'checkout'
    checkout.mkdir(); (checkout / '.git').mkdir()
    with pytest.raises(ValueError):
        private_path(checkout / 'private.json')


def test_exact_unicode_and_approved_fact_evidence():
    packet = next(p for p in make_packets(lock_manifest())[0] if p['kind'] == 'release')
    packet = deepcopy(packet)
    packet['context']['student_utterance'] = '🙂 no fever'
    packet['context']['prior_student_utterances'] = []
    ref = {'kind': 'transcript_span', 'turn': 1, 'speaker': 'student', 'start': 2, 'end': 10, 'quote': 'no fever'}
    evidence_check(packet, [ref])
    with pytest.raises(ValueError, match='mismatch'):
        evidence_check(packet, [ref | {'end': 11}])
    with pytest.raises(ValueError):
        evidence_check(packet, [ref | {'start': True}])
    fact = approved_case(packet)['facts'][0]
    evidence_check(packet, [{'kind': 'source_fact', 'fact_id': fact['id'], 'case_sha256': packet['case_sha256']}])
    with pytest.raises(ValueError):
        evidence_check(packet, [{'kind': 'source_fact', 'fact_id': 'invented', 'case_sha256': packet['case_sha256']}])


def test_stale_view_and_source_rejected(tmp_path):
    work = tmp_path / 'toy'; demo(work)
    manifest = json.loads((work / 'manifest.json').read_text())
    save(work / 'manifest.json', manifest | {'view_sha256': 'bad'})
    with pytest.raises(ValueError, match='context'):
        workspace_packets(work)


def test_duplicate_identity_and_tampered_spans_rejected(tmp_path):
    work = tmp_path / 'toy'; demo(work)
    a, b = work / 'submission_a.json', work / 'submission_b.json'
    sub = json.loads(b.read_text()); sub['reviewer_id'] = 'toy-a'; save(b, sub)
    with pytest.raises(ValueError, match='distinct'):
        validate(work, [a,b], allow_toy=True)
    sub['reviewer_id'] = 'toy-b'; sub['answers'][0]['evidence'][0]['quote'] = 'invented'; save(b, sub)
    with pytest.raises(ValueError, match='span'):
        validate(work, [a,b], allow_toy=True)


def test_export_and_supplemental_evidence_integrity(tmp_path):
    # Simulate non-toy transport only; these generated labels never feed study metrics.
    work = tmp_path / 'transport'; demo(work)
    manifest = json.loads((work / 'manifest.json').read_text()) | {'toy': False}
    save(work / 'manifest.json', manifest)
    paths = [work / f'submission_{slot}.json' for slot in ('a','b','adjudicator')]
    for path in paths:
        sub = json.loads(path.read_text()); sub['manifest'] = manifest; save(path, sub)
    result = validate(work, paths)
    assert result['audit']['events'] == 10
    assert verify_export(work, paths)['export_integrity'] == 'PASS'
    audit = json.loads((work / 'audit.json').read_text()); audit[0]['chain_sha256'] = 'bad'; save(work / 'audit.json', audit)
    with pytest.raises(ValueError, match='audit'):
        verify_export(work, paths)
    validate(work, paths)
    sub = json.loads(paths[0].read_text()); sub['answers'][0]['rationale'] = 'tampered after export'; save(paths[0], sub)
    with pytest.raises(ValueError, match='receipt'):
        verify_export(work, paths)


def test_adjudication_without_two_independent_answers_rejected(tmp_path):
    work = tmp_path / 'toy'; demo(work)
    with pytest.raises(ValueError, match='both independent'):
        validate(work, [work / 'submission_a.json', work / 'submission_adjudicator.json'], allow_toy=True)
