"""Private offline reviewer files; Notebook 06 contracts remain unchanged."""
from __future__ import annotations

from collections import Counter
import json
import os
import tempfile
from hashlib import sha256

import yaml
from pathlib import Path

from app.schemas.case import Case
from backend_kelsch.app.debrief_probe.evaluation import ROOT
from backend_kelsch.app.integration.quality import preflight, verify_audit_log
from backend_kelsch.app.study.protocol import digest, make_packets, lock_manifest
from backend_kelsch.app.study.review import _answer, load_reviews

TEMPLATE = Path(__file__).with_name('reviewer.html')


def private_path(path: Path) -> Path:
    """Reject repository destinations, including symlinks and other Git checkouts."""
    path = path.expanduser().resolve()
    if path == ROOT or ROOT in path.parents or any((p / '.git').exists() for p in (path, *path.parents)):
        raise ValueError('private data must be stored outside all Git checkouts')
    return path


def write_private(path: Path, data: str) -> None:
    path = private_path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Do not follow a preexisting symlink or truncate a file via a hard link.
    temp = path.with_name(path.name + '.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(data)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def save(path: Path, value: object) -> None:
    write_private(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def approved_case(packet: dict) -> dict:
    path = ROOT / 'cases' / f"{packet['case_id']}.json"
    case = Case.model_validate_json(path.read_text())
    # Explicit allowlist: no case description, objectives, examples or provisional scores.
    facts = []
    for fact in case.facts:
        if fact.status == 'approved':
            row = fact.model_dump(mode='json', exclude_none=True)
            row['source'] = {k: v for k, v in row['source'].items() if k in {'kind', 'ref'}}
            facts.append(row)
    raw = json.loads(path.read_text())
    return {'case_id': case.case_id, 'version': case.version, 'sha256': packet['case_sha256'],
            'facts': facts, 'authored_trust_rules': raw.get('trust'),
            'trust_event_catalog': yaml.safe_load((ROOT / 'backend/app/vocab/trust_events.yaml').read_text()),
            'trust_event_source': {'path': 'backend/app/vocab/trust_events.yaml',
                'sha256': sha256((ROOT / 'backend/app/vocab/trust_events.yaml').read_bytes()).hexdigest()},
            'source_ref': f"cases/{case.case_id}.json"}


def _probe_thresholds(packet: dict) -> dict:
    from backend_kelsch.app.patient_environment.runner import with_probe_preset
    case = Case.model_validate_json((ROOT / 'cases' / f"{packet['case_id']}.json").read_text())
    return with_probe_preset(case, packet['context']['difficulty_vector']).trust.thresholds


def view(packet: dict) -> dict:
    """Project an allowlisted task; never embed engine/source-key mapping."""
    c, kind = packet['context'], packet['kind']
    context = {}
    if kind == 'release':
        context = {'student_utterance': c['student_utterance'],
                   'prior_student_utterances': c['prior_student_utterances'],
                   'difficulty_vector': c['difficulty_vector'],
                   'effective_thresholds': _probe_thresholds(packet),
                   'note': 'Only student history is supplied. Judge newly expected facts independently; engine releases and patient replies are withheld.'}
    elif kind == 'semantic':
        context = {k: c[k] for k in ('reply', 'student_utterance', 'available_fact_ids', 'previously_disclosed_fact_ids')}
        context['note'] = 'Availability is the candidate task constraint, not an engine verdict.'
    elif kind == 'claim':
        claim = {k: c['claim'][k] for k in ('kind', 'label') if k in c['claim']}
        claim['evidence'] = [{k: v for k, v in ref.items() if k in {
            'kind', 'fact_id', 'turn', 'speaker', 'start', 'end', 'quote', 'case_sha256', 'case_version'}}
            for ref in c['claim'].get('evidence', [])]
        context = {'transcript': c['transcript'], 'candidate_claim': claim}
    elif kind == 'domain':
        rubric = json.loads((ROOT / 'backend/app/data/rubric_shp_v1.json').read_text())
        context = {'transcript': c['transcript'], 'domain': next(d for d in rubric['domains'] if d['id'] == c['domain_id'])}
    elif kind == 'action':
        context = {k: c[k] for k in ('text', 'speaker', 'turn_id', 'namespace')}
        context['vocabulary'] = json.loads((ROOT / 'backend_kelsch/app/data/action_annotation_vocab.json').read_text())['student_skill']
    else:
        raise ValueError('unsupported packet kind')
    return {k: packet[k] for k in ('packet_id', 'kind', 'protocol_lock', 'case_sha256', 'case_version')} | {
        'case': approved_case(packet), 'context': context}


def text_units(packet: dict) -> dict[tuple[int, str], str]:
    c = packet['context']
    if 'transcript' in c:
        return {(t['turn'], s): t[s] for t in c['transcript'] for s in ('student', 'patient') if s in t}
    if packet['kind'] == 'release':
        return {(i + 1, 'student'): text for i, text in enumerate(c['prior_student_utterances'] + [c['student_utterance']])}
    if packet['kind'] == 'semantic':
        return {(1, 'student'): c['student_utterance'], (1, 'patient'): c['reply']}
    return {(1, c['speaker']): c['text']}


def evidence_check(packet: dict, evidence: list) -> None:
    if not isinstance(evidence, list) or not evidence:
        raise ValueError('exact evidence required (except domain N/A)')
    facts = {f['id'] for f in approved_case(packet)['facts']}
    units = text_units(packet)
    for ref in evidence:
        if ref.get('kind') == 'source_fact' and ref.get('fact_id') in facts:
            if ref.get('case_sha256') != packet['case_sha256']:
                raise ValueError('evidence case digest mismatch')
            continue
        text = units.get((ref.get('turn'), ref.get('speaker')))
        a, b = ref.get('start'), ref.get('end')
        if (ref.get('kind') != 'transcript_span' or text is None or type(a) is not int or
                type(b) is not int or not 0 <= a < b <= len(text) or text[a:b] != ref.get('quote')):
            raise ValueError('evidence span/quote mismatch')


def prepare(workspace: Path, *, toy: bool = False, packet_ids: list[str] | None = None) -> dict:
    workspace = private_path(workspace)
    if workspace.exists():
        raise ValueError('use a new private workspace; never overwrite reviews')
    preflight()  # compare current sources with the historical Notebook 06 report
    packets, _ = make_packets(lock_manifest())
    if packet_ids is not None:
        selected = set(packet_ids)
        packets = [p for p in packets if p['packet_id'] in selected]
        if len(packets) != len(selected):
            raise ValueError('unknown packet selection')
    workspace.mkdir(mode=0o700, parents=True)
    manifest = {'workflow_version': 1, 'toy': toy, 'protocol_lock': lock_manifest()['lock_id'],
                'packet_ids': [p['packet_id'] for p in packets], 'view_sha256': digest([view(p) for p in packets])}
    save(workspace / 'manifest.json', manifest)
    for slot in ('a', 'b'):
        render(workspace / f'reviewer_{slot}.html', packets, manifest, slot)
    return manifest


def render(path: Path, packets: list[dict], manifest: dict, slot: str, pairs: dict | None = None) -> None:
    data = {'manifest': manifest, 'slot': slot, 'tasks': [view(p) | {'text_units': [
        {'turn': t, 'speaker': s, 'text': text} for (t, s), text in text_units(p).items()]} for p in packets]}
    if pairs is not None:
        data['independent_answers'] = pairs
    encoded = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c').replace('&', '\\u0026')
    write_private(path, TEMPLATE.read_text().replace('__DATA__', encoded))


def workspace_packets(workspace: Path) -> tuple[dict, list[dict]]:
    workspace = private_path(workspace)
    manifest = json.loads((workspace / 'manifest.json').read_text())
    preflight()
    packets, _ = make_packets(lock_manifest())
    selected = {p['packet_id']: p for p in packets}
    if manifest['protocol_lock'] != lock_manifest()['lock_id'] or any(pid not in selected for pid in manifest['packet_ids']):
        raise ValueError('stale workspace/source lock')
    packets = [selected[pid] for pid in manifest['packet_ids']]
    if digest([view(p) for p in packets]) != manifest['view_sha256']:
        raise ValueError('reviewer context differs from manifest')
    return manifest, packets


def collect(workspace: Path, paths: list[Path], *, allow_toy: bool = False) -> tuple[dict, list[dict], list[dict]]:
    manifest, packets = workspace_packets(workspace)
    if manifest['toy'] and not allow_toy:
        raise ValueError('toy workspace cannot supply genuine reviews')
    index = {p['packet_id']: p for p in packets}
    rows = []
    slot_reviewers = {}
    seen_slots = set()
    for path in paths:
        submission = json.loads(private_path(path).read_text())
        slot = submission.get('slot')
        if submission.get('manifest') != manifest or slot not in ('a', 'b', 'adjudicator') or slot in seen_slots:
            raise ValueError('submission manifest/slot mismatch or duplicate slot')
        seen_slots.add(slot)
        reviewer = submission.get('reviewer_id')
        if not isinstance(reviewer, str) or not reviewer.strip() or reviewer in slot_reviewers.values():
            raise ValueError('distinct pseudonymous reviewers required')
        slot_reviewers[slot] = reviewer
        for entry in submission.get('answers', []):
            packet = index.get(entry.get('packet_id'))
            if packet is None:
                raise ValueError('unknown packet')
            answer = entry.get('answer')
            normalized = _answer(packet, answer)
            if normalized.get('score') == 'N/A' and not normalized['na_reason'].strip():
                raise ValueError('N/A reason must contain text')
            if normalized.get('score') != 'N/A':
                evidence_check(packet, entry.get('evidence'))
            elif entry.get('evidence'):
                raise ValueError('N/A must have no evidence')
            row = {k: packet[k] for k in ('packet_id', 'protocol_lock', 'case_sha256', 'case_version')}
            row.update(reviewer_id=reviewer, reviewer_role='faculty', review_status='approved',
                       reviewed_at=entry.get('reviewed_at'),
                       phase='adjudication' if slot == 'adjudicator' else 'independent', answer=answer)
            rows.append(row)
    return manifest, packets, rows


def validate(workspace: Path, paths: list[Path], *, allow_toy: bool = False) -> dict:
    manifest, packets, rows = collect(workspace, paths, allow_toy=allow_toy)
    # Existing importer validates timestamps, independence, typed answers and adjudication.
    export = private_path(workspace) / 'validated_reviews.jsonl'
    serialized = ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows)
    with tempfile.NamedTemporaryFile(mode='w', dir=private_path(workspace), suffix='.jsonl', delete=False) as stream:
        temp = Path(stream.name)
        stream.write(serialized)
    try:
        result = load_reviews(temp, packets)
        audit = verify_audit_log(result['audit_log'], expected_head=result['audit_head'], packet_ids={p['packet_id'] for p in packets})
    finally:
        temp.unlink()
    if not manifest['toy']:
        write_private(export, serialized)
    save(private_path(workspace) / 'audit.json', result['audit_log'])
    # Notebook 06 audit normalizes answers; bind the extra rationale/evidence separately.
    receipts = [{'submission_sha256': digest(json.loads(private_path(p).read_text()))} for p in paths]
    save(private_path(workspace) / 'evidence_receipt.json', {'manifest_sha256': digest(manifest),
         'submissions': receipts, 'import_audit_head': result['audit_head']})
    report = {'workflow_version': 1, 'toy': manifest['toy'], 'packet_counts': dict(Counter(p['kind'] for p in packets)),
              'technical_import_rows': len(rows), 'genuine_review_rows': 0 if manifest['toy'] else len(rows),
              'resolved_by_kind': result['resolved_by_kind'], 'counts': result['counts'], 'audit': audit,
              'study_gates': 'NOT EVALUABLE', 'reason': 'Toy data never advances gates; genuine partial review requires existing study analysis and independent authority checks.'}
    if manifest['toy']:
        # Do not leave an importer-compatible toy file that could be mistaken for faculty data.
        export.unlink(missing_ok=True)
    save(private_path(workspace) / 'quality.json', report)
    return report


def adjudicate(workspace: Path, paths: list[Path], *, allow_toy: bool = False) -> int:
    manifest, packets, rows = collect(workspace, paths, allow_toy=allow_toy)
    if any(r['phase'] != 'independent' for r in rows):
        raise ValueError('adjudication preparation takes independent submissions only')
    temp = private_path(workspace) / 'pair_check.jsonl'
    write_private(temp, ''.join(json.dumps(r) + '\n' for r in rows))
    try:
        review = load_reviews(temp, packets)
    finally:
        temp.unlink()
    pairs = {pid: pair for pid, pair in review['raw_pairs'].items() if pair[0] != pair[1]}
    # Supplemental evidence/rationale is visible only after both independent answers.
    adjudicator_pairs = {pid: [] for pid in pairs}
    for path in paths:
        submission = json.loads(private_path(path).read_text())
        for entry in submission['answers']:
            pid = entry['packet_id']
            if pid in pairs:
                adjudicator_pairs[pid].append({'slot': submission['slot'], 'answer': entry['answer'],
                    'evidence': entry.get('evidence', []), 'rationale': entry.get('rationale', '')})
    render(private_path(workspace) / 'adjudicator.html', [p for p in packets if p['packet_id'] in pairs], manifest, 'adjudicator', adjudicator_pairs)
    return len(pairs)


def verify_export(workspace: Path, paths: list[Path]) -> dict:
    """Recompute importer output and supplemental evidence receipt before downstream use."""
    manifest, packets, rows = collect(workspace, paths)
    export = private_path(workspace) / 'validated_reviews.jsonl'
    saved = [json.loads(line) for line in export.read_text().splitlines() if line.strip()]
    if saved != rows:
        raise ValueError('export differs from private submissions')
    result = load_reviews(export, packets)
    events = json.loads((private_path(workspace) / 'audit.json').read_text())
    if events != result['audit_log']:
        raise ValueError('audit differs from imported source')
    audit = verify_audit_log(events, expected_head=result['audit_head'], packet_ids={p['packet_id'] for p in packets})
    receipt = json.loads((private_path(workspace) / 'evidence_receipt.json').read_text())
    expected = {'manifest_sha256': digest(manifest), 'submissions': [
        {'submission_sha256': digest(json.loads(private_path(p).read_text()))} for p in paths],
        'import_audit_head': result['audit_head']}
    if receipt != expected:
        raise ValueError('supplemental evidence receipt mismatch')
    return {'export_integrity': 'PASS', 'audit': audit}
