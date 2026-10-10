"""Prepare fresh action/feedback packets, adjudicate disagreements, and report reviewed results."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend_kelsch.app.study.next_review import prepare_next, review_stage
from backend_kelsch.app.study.workflow import save


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prepare = sub.add_parser('prepare', help='Freeze current authored runs and predictions before independent review')
    prepare.add_argument('--workspace', type=Path, required=True)
    for command in ('adjudicate', 'report'):
        p = sub.add_parser(command)
        p.add_argument('--workspace', type=Path, required=True)
        p.add_argument('--kind', choices=('action', 'claim', 'domain'), required=True)
        p.add_argument('--config', type=Path, required=True)
        if command == 'report':
            p.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        stage = prepare_next(args.workspace)
        result = {'protocol_lock': stage['protocol_lock'], 'batches': {k: v['tasks'] for k, v in stage['batches'].items()},
                  'next_human_step': 'Independent action, claim and rubric reviews; clinical/preset decisions'}
    else:
        result = review_stage(args.workspace, args.kind, args.config, adjudicate=args.command == 'adjudicate')
        if args.command == 'report':
            save(args.output, result)
        result = {'review_transport': result['review_transport'], 'pending_tasks': len(result['pending_packet_ids']),
                  'learner_mcpt': result['learner_mcpt']}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
