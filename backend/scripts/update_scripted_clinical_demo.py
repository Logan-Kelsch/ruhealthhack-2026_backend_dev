"""Import readable scenario JSON into the notebook/API scripts, or export fresh review copies."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.demo.authoring import export_scripts, import_scripts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", type=Path, help="One, two, or three edited scenario JSON files")
    parser.add_argument("--check", action="store_true", help="Validate and preview changes without writing")
    parser.add_argument("--export", type=Path, metavar="DIRECTORY", help="Export current scripts for review")
    args = parser.parse_args()
    if args.export is not None and (args.files or args.check):
        parser.error("Use --export on its own")
    if args.export is None and not args.files:
        parser.error("Provide edited JSON files, or use --export DIRECTORY")
    try:
        if args.export is not None:
            print("\n".join(str(p) for p in export_scripts(args.export)))
        else:
            print(json.dumps(import_scripts(args.files, check=args.check), indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Import/export failed: {exc}\n")


if __name__ == "__main__":
    main()
