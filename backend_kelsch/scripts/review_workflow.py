"""Private offline workflow: prepare, adjudicate, validate, or toy demo."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from backend_kelsch.app.study.protocol import lock_manifest, make_packets
from backend_kelsch.app.study.workflow import adjudicate, prepare, save, text_units, validate, verify_export


def demo(workspace: Path) -> dict:
    packets, _ = make_packets(lock_manifest())
    selected = [next(p for p in packets if p['kind'] == k) for k in ('release', 'semantic', 'claim', 'domain')]
    manifest = prepare(workspace, toy=True, packet_ids=[p['packet_id'] for p in selected])
    paths = []
    now = datetime.now(timezone.utc).isoformat()
    for slot in ('a', 'b'):
        answers = []
        for p in selected:
            kind = p['kind']
            unit, text = next(iter(text_units(p).items()))
            evidence = [{'kind': 'transcript_span', 'turn': unit[0], 'speaker': unit[1], 'start': 0, 'end': len(text), 'quote': text}]
            answer = {'expected_fact_ids': []} if kind == 'release' else {'expected_supported': slot == 'a'}
            if kind == 'domain':
                answer, evidence = {'score': 'N/A', 'na_reason': 'TOY ONLY: demonstrate N/A export, not a clinical judgment', 'evidence': []}, []
            answers.append({'packet_id': p['packet_id'], 'answer': answer, 'evidence': evidence, 'reviewed_at': now})
        path = workspace / f'submission_{slot}.json'
        save(path, {'manifest': manifest, 'slot': slot, 'reviewer_id': f'toy-{slot}', 'answers': answers})
        paths.append(path)
    before = validate(workspace, paths, allow_toy=True)
    adjudicate(workspace, paths, allow_toy=True)
    disagree = [p for p in selected if p['kind'] in ('semantic', 'claim')]
    answers = []
    for p in disagree:
        (turn, speaker), text = next(iter(text_units(p).items()))
        answers.append({'packet_id': p['packet_id'], 'answer': {'expected_supported': False},
            'evidence': [{'kind': 'transcript_span', 'turn': turn, 'speaker': speaker, 'start': 0, 'end': len(text), 'quote': text}], 'reviewed_at': now})
    path = workspace / 'submission_adjudicator.json'
    save(path, {'manifest': manifest, 'slot': 'adjudicator', 'reviewer_id': 'toy-c', 'answers': answers})
    after = validate(workspace, paths + [path], allow_toy=True)
    return {'label': 'TOY TECHNICAL DEMONSTRATION — NOT REVIEWS', 'before': before, 'after': after}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'adjudicate', 'validate', 'verify-export', 'demo'])
    parser.add_argument('--workspace', type=Path, required=True, help='New directory outside every Git checkout')
    parser.add_argument('--submissions', nargs='*', type=Path, default=[])
    args = parser.parse_args()
    if args.command == 'prepare':
        result = prepare(args.workspace)
        print(json.dumps({'packets': len(result['packet_ids']), 'protocol_lock': result['protocol_lock']}))
    elif args.command == 'demo':
        print(json.dumps(demo(args.workspace), indent=2))
    elif args.command == 'adjudicate':
        print(json.dumps({'disagreements': adjudicate(args.workspace, args.submissions)}))
    elif args.command == 'verify-export':
        print(json.dumps(verify_export(args.workspace, args.submissions), indent=2))
    else:
        print(json.dumps(validate(args.workspace, args.submissions), indent=2))


if __name__ == '__main__':
    main()
