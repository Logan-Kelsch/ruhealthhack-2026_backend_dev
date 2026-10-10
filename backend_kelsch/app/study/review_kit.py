"""Small review rehearsal and separately locked semantic supplement.

No generated answer is a faculty label. Historical Notebook 06 stays locked.
"""
from __future__ import annotations

import json
import tempfile
from collections import Counter
from hashlib import sha256
from pathlib import Path

from backend_kelsch.app.debrief_probe.evaluation import ROOT, CASES
from backend_kelsch.app.grounding.live import extra_challenges
from backend_kelsch.app.integration.quality import preflight, verify_audit_log
from backend_kelsch.app.study.protocol import digest, lock_manifest, make_packets
from backend_kelsch.app.study.review import _answer, load_reviews
from backend_kelsch.app.study.workflow import (
    evidence_check, prepare, private_path, render, save, view, write_private,
)


def sample_ids() -> list[str]:
    """One locked work item per case/task; a usability sample, not an estimate."""
    preflight()
    packets, _ = make_packets(lock_manifest())
    return [next(p['packet_id'] for p in packets if p['case_id'] == cid and p['kind'] == kind)
            for cid in CASES for kind in ('release', 'semantic', 'claim', 'domain')]


def supplement() -> tuple[dict, list[dict]]:
    preflight()
    candidates = extra_challenges()
    paths = ['backend_kelsch/app/grounding/live.py',
             'backend_kelsch/app/study/review_kit.py',
             'backend_kelsch/app/study/workflow.py',
             'backend_kelsch/app/study/reviewer.html']
    sources = {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}
    base = lock_manifest()
    identity = {'supplement_version': 'semantic_supplement_v1',
                'historical_protocol_lock': base['lock_id'],
                'source_sha256': sources, 'candidate_sha256': digest(candidates)}
    identity['lock_id'] = digest(identity)
    packets = []
    for c in candidates:
        packets.append({'packet_id': digest([identity['lock_id'], c['challenge_id']])[:24],
            'kind': 'semantic', 'protocol_lock': identity['lock_id'],
            'case_id': c['case_id'], 'case_sha256': c['case_source']['sha256'],
            'case_version': c['case_version'], 'expected': None, 'review_status': 'pending',
            'context': {'reply': c['reply'], 'student_utterance': c['student_utterance'],
                        'available_fact_ids': c['allowed_fact_ids'],
                        'previously_disclosed_fact_ids': c['previously_disclosed']}})
    return identity, sorted(packets, key=lambda p: p['packet_id'])


def prepare_kit(workspace: Path, kind: str) -> dict:
    if kind == 'sample':
        return prepare(workspace, packet_ids=sample_ids())
    if kind != 'supplement':
        raise ValueError('unknown review kit kind')
    workspace = private_path(workspace)
    if workspace.exists():
        raise ValueError('use a new private workspace')
    lock, packets = supplement()
    manifest = {'workflow_version': 1, 'toy': False, 'supplement': lock,
                'protocol_lock': lock['lock_id'],
                'packet_ids': [p['packet_id'] for p in packets],
                'view_sha256': digest([view(p) for p in packets])}
    workspace.mkdir(parents=True, mode=0o700)
    save(workspace / 'manifest.json', manifest)
    for slot in ('a', 'b'):
        render(workspace / f'reviewer_{slot}.html', packets, manifest, slot)
    return manifest


def supplement_workspace(workspace: Path) -> tuple[dict, list[dict]]:
    workspace = private_path(workspace)
    manifest = json.loads((workspace / 'manifest.json').read_text())
    lock, packets = supplement()
    expected = {'workflow_version': 1, 'toy': False, 'supplement': lock,
                'protocol_lock': lock['lock_id'],
                'packet_ids': [p['packet_id'] for p in packets],
                'view_sha256': digest([view(p) for p in packets])}
    if manifest != expected:
        raise ValueError('supplement source/context lock mismatch')
    return manifest, packets


def collect_supplement(workspace: Path, paths: list[Path]) -> tuple[dict, list[dict], list[dict], list[dict]]:
    manifest, packets = supplement_workspace(workspace)
    index = {p['packet_id']: p for p in packets}
    slots, reviewers, rows, submissions = set(), set(), [], []
    for path in paths:
        submission = json.loads(private_path(path).read_text())
        slot, reviewer = submission.get('slot'), submission.get('reviewer_id')
        if (submission.get('manifest') != manifest or slot not in ('a', 'b', 'adjudicator')
                or slot in slots or submission.get('toy') is True):
            raise ValueError('submission manifest/slot mismatch or toy input')
        if not isinstance(reviewer, str) or not reviewer.strip() or reviewer in reviewers:
            raise ValueError('distinct private reviewer pseudonyms required')
        slots.add(slot); reviewers.add(reviewer)
        if not isinstance(submission.get('answers'), list):
            raise ValueError('answers must be a list')
        for entry in submission['answers']:
            p = index.get(entry.get('packet_id'))
            if p is None:
                raise ValueError('unknown supplement packet')
            _answer(p, entry.get('answer'))
            evidence_check(p, entry.get('evidence'))
            rows.append({k: p[k] for k in ('packet_id', 'protocol_lock', 'case_sha256', 'case_version')} | {
                'reviewer_id': reviewer, 'reviewer_role': 'faculty', 'review_status': 'approved',
                'phase': 'adjudication' if slot == 'adjudicator' else 'independent',
                'reviewed_at': entry.get('reviewed_at'), 'answer': entry['answer']})
        submissions.append(submission)
    return manifest, packets, rows, submissions


def analyze_supplement(workspace: Path, paths: list[Path], *, command: str) -> dict:
    manifest, packets, rows, submissions = collect_supplement(workspace, paths)
    serialized = ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows)
    with tempfile.NamedTemporaryFile(mode='w', dir=private_path(workspace), delete=False) as f:
        temp = Path(f.name); f.write(serialized)
    try:
        result = load_reviews(temp, packets)
    finally:
        temp.unlink()
    audit = verify_audit_log(result['audit_log'], expected_head=result['audit_head'],
                             packet_ids={p['packet_id'] for p in packets})
    receipt = {'manifest_sha256': digest(manifest), 'submission_sha256': [digest(s) for s in submissions],
               'import_audit_head': result['audit_head']}
    workspace = private_path(workspace)
    if command == 'adjudicate':
        if any(s['slot'] == 'adjudicator' for s in submissions):
            raise ValueError('adjudication preparation takes independent submissions only')
        pairs = {pid: [] for pid, pair in result['raw_pairs'].items() if pair[0] != pair[1]}
        for s in submissions:
            for entry in s['answers']:
                if entry['packet_id'] in pairs:
                    pairs[entry['packet_id']].append({k: entry.get(k) for k in ('answer', 'evidence', 'rationale')} | {'slot': s['slot']})
        render(workspace / 'adjudicator.html', [p for p in packets if p['packet_id'] in pairs], manifest, 'adjudicator', pairs)
        return {'disagreements': len(pairs)}
    if command == 'verify-export':
        if ((workspace / 'supplement_reviews.jsonl').read_text() != serialized
                or json.loads((workspace / 'supplement_audit.json').read_text()) != result['audit_log']
                or json.loads((workspace / 'supplement_receipt.json').read_text()) != receipt):
            raise ValueError('supplement export/audit/receipt differs from submissions')
        return {'export_integrity': 'PASS', 'audit': audit}
    if command != 'validate':
        raise ValueError('unknown supplement command')
    write_private(workspace / 'supplement_reviews.jsonl', serialized)
    save(workspace / 'supplement_audit.json', result['audit_log'])
    save(workspace / 'supplement_receipt.json', receipt)
    report = {'supplement_version': 'semantic_supplement_v1', 'packets': len(packets),
              'submitted_review_rows': len(rows), 'resolved': len(result['resolved']),
              'counts': result['counts'], 'audit': audit,
              'clinical_accuracy': 'NOT EVALUABLE',
              'reason': 'Review transport only; authority and matched model predictions are not verified here.'}
    save(workspace / 'supplement_quality.json', report)
    return report


def kit_report() -> dict:
    lock, packets = supplement()
    return {'version': 1, 'historical_packets': 287,
            'usability_sample': {'packets': len(sample_ids()), 'cases': len(CASES), 'kinds': 4,
                                'selection': 'first hash-ordered packet per case and kind; not representative'},
            'supplement': {'packets': len(packets), 'counts': dict(Counter(p['kind'] for p in packets)),
                           'lock': lock}, 'human_reviews_imported_by_this_run': 0,
            'gates': {'review_preparation': 'PASS', 'clinical_approval': 'NOT EVALUABLE',
                      'semantic_accuracy': 'NOT EVALUABLE', 'rubric_accuracy': 'NOT EVALUABLE',
                      'trained_action_extraction': 'NOT EVALUABLE', 'difficulty_calibration': 'NOT EVALUABLE',
                      'learning_gain': 'NOT EVALUABLE'}}
