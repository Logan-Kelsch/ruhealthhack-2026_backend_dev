"""Summarize captured encounter timings (V-05).

    python -m scripts.report_latency --samples samples.json --output docs/validation/latency.json

The input is a list of timing samples already captured for saved turns. A fixture
clock checks that the summary keeps gaps empty. It is not a live vendor measurement.
The script does not call ElevenLabs and does not open a microphone.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.latency import summarize


def main(argv: list[str] | None = None) -> None:
    """Read captured samples and write the validation report. Missing clocks stay missing."""
    parser = argparse.ArgumentParser(description="Summarize captured encounter timings.")
    parser.add_argument("--samples", required=True, help="JSON list of timing samples")
    parser.add_argument("--output", required=True, help="Where to write the report JSON")
    args = parser.parse_args(argv)
    raw = json.loads(Path(args.samples).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise SystemExit("The samples file must be a JSON list.")
    report = summarize(raw)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
