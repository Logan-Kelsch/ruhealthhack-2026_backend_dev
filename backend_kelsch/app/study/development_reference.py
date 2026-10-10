"""Replaceable private review sources for development, without faculty impersonation."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path

from backend_kelsch.app.study.protocol import digest
from backend_kelsch.app.study.workflow import private_path


def read_source(base: Path, spec: dict) -> tuple[Path, bytes]:
    path = private_path(base / spec['path'])
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != spec.get('sha256'):
        raise ValueError('reference source digest mismatch')
    return path, raw


def answers(raw: bytes) -> tuple[list, dict | None]:
    """Accept browser submission envelopes or the user's JSONL exports."""
    text = raw.decode()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return [json.loads(line) for line in text.splitlines() if line.strip()], None
    if isinstance(value, dict) and 'answers' in value:
        return value['answers'], value
    if isinstance(value, list):
        return value, None
    if isinstance(value, dict) and 'packet_id' in value:
        return [value], None
    raise ValueError('expected submission envelope or JSONL answers')


def normalize_answer(task: dict, answer: dict) -> dict:
    if not isinstance(answer, dict):
        raise ValueError('answer must be an object')
    if task['kind'] in {'semantic', 'claim'}:
        if type(answer.get('expected_supported')) is not bool:
            raise ValueError('support label must be boolean')
        return {'expected_supported': answer['expected_supported']}
    if task['kind'] == 'release':
        ids = answer.get('expected_fact_ids')
        facts = {f['id'] for f in task['case']['facts']}
        if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids) or len(set(ids)) != len(ids) or not set(ids) <= facts:
            raise ValueError('release label must contain unique source fact IDs')
        return {'expected_fact_ids': sorted(ids)}
    if task['kind'] == 'domain':
        score = answer.get('score')
        if score == 'N/A':
            if not isinstance(answer.get('na_reason'), str) or not answer['na_reason'].strip():
                raise ValueError('N/A requires a reason')
            return {'score': 'N/A'}
        if type(score) is not int or score not in range(1, 5):
            raise ValueError('domain score must be 1–4 or N/A')
        return {'score': score}
    if task['kind'] == 'action':
        from backend_kelsch.app.study.review import _answer
        return _answer(task, answer)
    raise ValueError('unsupported development task kind')


def evidence_check(task: dict, row: dict) -> None:
    """Check existence and exact anchors; this does not establish semantic truth."""
    evidence = row.get('evidence')
    if row['answer'].get('score') == 'N/A':
        if evidence != []:
            raise ValueError('N/A must have no evidence')
        return
    if not isinstance(evidence, list) or not evidence:
        raise ValueError('exact evidence required')
    facts = {f['id'] for f in task['case']['facts']}
    units = {(u['turn'], u['speaker']): u['text'] for u in task['text_units']}
    for e in evidence:
        if task['kind'] == 'domain' and e.get('kind') != 'transcript_span':
            raise ValueError('scored domains require transcript evidence')
        if e.get('kind') == 'source_fact':
            if e.get('fact_id') not in facts or e.get('case_sha256') != task['case_sha256']:
                raise ValueError('source fact/hash mismatch')
        else:
            text = units.get((e.get('turn'), e.get('speaker')))
            a, b = e.get('start'), e.get('end')
            if e.get('kind') != 'transcript_span' or text is None or type(a) is not int or type(b) is not int or not 0 <= a < b <= len(text) or text[a:b] != e.get('quote'):
                raise ValueError('transcript evidence offset/quote mismatch')


def load_reference(config_path: Path) -> dict:
    """Resolve pairs by labels, not by rationale differences; never unlock study gates."""
    config_path = private_path(config_path)
    config = json.loads(config_path.read_text())
    if config.get('version') != 1 or config.get('mode') != 'development_reference':
        raise ValueError('version 1 development reference required')
    base = config_path.parent
    _, raw = read_source(base, config['manifest'])
    manifest = json.loads(raw)
    _, raw = read_source(base, config['tasks'])
    tasks = json.loads(raw)
    ids = [t['packet_id'] for t in tasks]
    if not ids or len(set(ids)) != len(ids) or ids != manifest['packet_ids'] or digest(tasks) != manifest['view_sha256']:
        raise ValueError('task manifest/content mismatch')
    if any(t['protocol_lock'] != manifest['protocol_lock'] or t['case_sha256'] != t['case']['sha256'] for t in tasks):
        raise ValueError('task source lock mismatch')
    index = {t['packet_id']: t for t in tasks}
    submissions = {}
    reviewer_ids = set()
    receipts = []
    for spec in config['submissions']:
        slot, reviewer = spec['slot'], spec['reviewer_id']
        provenance = spec['provenance']
        if slot not in {'a', 'b', 'adjudicator'} or slot in submissions or not isinstance(reviewer, str) or not reviewer.strip() or reviewer in reviewer_ids:
            raise ValueError('distinct reviewer IDs and slots required')
        if provenance.get('type') not in {'ai', 'human', 'synthetic'} or not provenance.get('description'):
            raise ValueError('explicit reviewer provenance required')
        _, raw = read_source(base, spec)
        entries, envelope = answers(raw)
        if envelope is not None and (envelope.get('manifest') != manifest or envelope.get('slot') != slot or envelope.get('reviewer_id') != reviewer):
            raise ValueError('submission envelope mismatch')
        current = {}
        for row in entries:
            pid = row.get('packet_id')
            if pid not in index or pid in current:
                raise ValueError('unknown or duplicate review task')
            if not isinstance(row.get('rationale'), str) or not row['rationale'].strip():
                raise ValueError('review rationale required')
            stamp = row.get('reviewed_at')
            if not isinstance(stamp, str) or datetime.fromisoformat(stamp.replace('Z', '+00:00')).tzinfo is None:
                raise ValueError('timezone-aware review timestamp required')
            answer = row.get('answer')
            # Browser exports may include pending rows; preserve them as missing labels.
            if answer is None or isinstance(answer, dict) and answer.get('expected_supported', False) is None:
                continue
            normalized = normalize_answer(index[pid], answer)
            evidence_check(index[pid], row)
            current[pid] = {'answer': normalized, 'provenance': provenance, 'source_sha256': spec['sha256']}
        submissions[slot] = current
        reviewer_ids.add(reviewer)
        receipts.append({k: spec[k] for k in ('slot', 'sha256', 'provenance')})
    if not {'a', 'b'} <= submissions.keys():
        raise ValueError('A and B sources required')
    resolved, disagreements, waiting = {}, [], []
    agreement = 0
    for pid in ids:
        pair = [submissions[s].get(pid) for s in ('a', 'b')]
        if any(r is None for r in pair):
            waiting.append(pid)
            continue
        if pair[0]['answer'] == pair[1]['answer']:
            agreement += 1
            resolved[pid] = {'answer': pair[0]['answer'], 'status': 'paired_consensus', 'sources': pair}
        else:
            disagreements.append(pid)
            decision = submissions.get('adjudicator', {}).get(pid)
            if decision:
                resolved[pid] = {'answer': decision['answer'], 'status': 'adjudicated', 'sources': pair + [decision]}
            else:
                waiting.append(pid)
    if set(submissions.get('adjudicator', {})) - set(disagreements):
        raise ValueError('adjudication may only resolve paired disagreements')
    summary = {'mode': config['mode'], 'protocol_lock': manifest['protocol_lock'],
        'config_sha256': sha256(config_path.read_bytes()).hexdigest(), 'source_receipts': receipts,
        'task_count': len(ids), 'resolved_count': len(resolved), 'pending_count': len(waiting),
        'paired_agreement_count': agreement, 'paired_count': sum(pid in submissions['a'] and pid in submissions['b'] for pid in ids),
        'disagreements': len(disagreements), 'reviewer_authority': 'NOT VERIFIED',
        'human_gate': 'NOT EVALUABLE', 'coverage_by_kind': dict(Counter(index[p]['kind'] for p in resolved))}
    return {'summary': summary, 'tasks': index, 'resolved': resolved, 'pending': waiting,
            'disagreements': disagreements, 'submissions': submissions, 'config': config, 'base': base}
