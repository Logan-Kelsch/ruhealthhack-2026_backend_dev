"""Prepare a 12-packet usability sample or separate semantic review supplement."""
import argparse
import json
from pathlib import Path

from backend_kelsch.app.study.review_kit import prepare_kit, analyze_supplement, kit_report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('report', 'sample', 'supplement', 'validate', 'adjudicate', 'verify-export'))
    parser.add_argument('--workspace', type=Path)
    parser.add_argument('--submissions', nargs='*', type=Path, default=[])
    args = parser.parse_args()
    if args.command == 'report':
        result = kit_report()
    else:
        if args.workspace is None:
            parser.error('--workspace outside Git is required')
        if args.command in ('sample', 'supplement'):
            manifest = prepare_kit(args.workspace, args.command)
            result = {'packets': len(manifest['packet_ids']), 'protocol_lock': manifest['protocol_lock']}
        else:
            result = analyze_supplement(args.workspace, args.submissions, command=args.command)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
