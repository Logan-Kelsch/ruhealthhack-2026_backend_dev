"""Write the OpenAPI document without starting a server or contacting a service.

Run from backend/:

    python -m scripts.export_openapi path/to/openapi.json

The file is the contract the frontend types are generated from. It must not
contain local configuration or secrets.
"""

import json
import sys
from pathlib import Path

from app.main import app


def main() -> None:
    """Write one deterministic schema file. Two runs with the same code match byte for byte."""
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m scripts.export_openapi OUTPUT.json")
    destination = Path(sys.argv[1])
    schema = app.openapi()
    # Key order is part of the committed file, so a fresh export can be compared exactly.
    text = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
