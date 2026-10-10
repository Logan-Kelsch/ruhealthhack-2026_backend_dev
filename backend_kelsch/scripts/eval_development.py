"""Replaceable review intake, backend regression ledger, and synthetic MCPT."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from backend_kelsch.app.study.development_reference import load_reference
from backend_kelsch.app.study.development_evaluation import completion_report
from backend_kelsch.app.study.permutation import demo_fixture, evaluate_fixture
from backend_kelsch.app.study.workflow import private_path, save

ROOT = Path(__file__).resolve().parents[2]


def source(path: Path) -> dict:
    path = private_path(path)
    return {'path': str(path), 'sha256': sha256(path.read_bytes()).hexdigest()}


def configure(args) -> dict:
    workspace = private_path(args.workspace)
    destination = private_path(args.output)
    if destination.exists():
        raise ValueError('use a new config version; never overwrite the previous review lock')
    config = {'version': 1, 'mode': 'development_reference',
        'manifest': source(workspace / 'review_manifest.json'),
        'tasks': source(workspace / 'blinded_tasks.json'), 'submissions': []}
    for slot in ('a', 'b', 'adjudicator'):
        path = getattr(args, slot)
        if path:
            description = getattr(args, slot + '_description')
            config['submissions'].append(source(path) | {'slot': slot,
                'reviewer_id': getattr(args, slot + '_id'),
                'provenance': {'type': getattr(args, slot + '_kind'), 'description': description,
                               'authority_verified': False}})
    if args.trace:
        config['trace'] = source(args.trace)
        config['mapping'] = source(workspace / 'PRIVATE_packet_mapping.json')
    if args.predictions:
        config['predictions'] = source(args.predictions)
    # Validate before writing the final config; source contents are never mutated.
    temp = destination.with_name(destination.name + '.pending')
    save(temp, config)
    try:
        load_reference(temp)
    finally:
        temp.unlink()
    save(destination, config)
    return config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('configure', help='Create a new pinned private reference config')
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--trace', type=Path)
    p.add_argument('--predictions', type=Path, help='Optional packet-keyed model predictions for any supported task kind')
    p.add_argument('--output', type=Path, required=True)
    for slot in ('a', 'b', 'adjudicator'):
        p.add_argument('--' + slot, type=Path, required=slot in {'a', 'b'})
        p.add_argument('--' + slot + '-id', default='development-' + slot)
        p.add_argument('--' + slot + '-kind', choices=['ai', 'human', 'synthetic'], default='ai')
        p.add_argument('--' + slot + '-description', default='User-provided AI development review; exact model provenance unverified')
    p = sub.add_parser('evaluate', help='Generate a development ledger, never close human gates')
    p.add_argument('--config', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--export-reference', type=Path)
    p = sub.add_parser('mcpt', help='Analyze synthetic learner fixtures only')
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p = sub.add_parser('demo', help='Offline backend checks plus invented learner arithmetic')
    p.add_argument('--output', type=Path, default=ROOT / 'backend_kelsch/docs/validation/development_completion.json')
    args = parser.parse_args()
    if args.command == 'configure':
        configure(args)
        print('Pinned replaceable development reference created.')
        return
    if args.command == 'evaluate':
        reference = load_reference(args.config) if args.config else None
        report = completion_report(reference)
        if args.export_reference:
            if reference is None:
                parser.error('--export-reference requires --config')
            save(args.export_reference, {'mode': 'development_reference', 'summary': reference['summary'],
                                        'resolved': reference['resolved']})
    elif args.command == 'mcpt':
        data = json.loads(private_path(args.input).read_text())
        report = evaluate_fixture(data)
    else:
        report = completion_report()
        report['synthetic_mcpt'] = evaluate_fixture(demo_fixture())
        # Recompute after adding the statistical fixture, without a self-referential digest.
        from backend_kelsch.app.study.protocol import digest
        report.pop('report_sha256')
        report['report_sha256'] = digest(report)
    if args.command == 'mcpt' or (args.command == 'evaluate' and args.config):
        save(args.output, report)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'mode': report.get('mode', report.get('scope')),
                      'development_gates': report.get('development_gates'),
                      'human_gates': report.get('human_gates', {'student_learning': 'NOT EVALUABLE'})}, indent=2))


if __name__ == '__main__':
    main()
