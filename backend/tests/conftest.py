import os
from pathlib import Path

import pytest

os.environ["LLM_ENABLED"] = "false"
os.environ["NLM_LOOKUP_ENABLED"] = "false"
os.environ.pop("ELEVENLABS_API_KEY", None)

CASES_DIR = Path(__file__).resolve().parents[2] / "cases"


@pytest.fixture
def load_golden():
    from app.schemas.case import Case

    def _load(case_id: str) -> Case:
        return Case.model_validate_json((CASES_DIR / f"{case_id}.json").read_text(encoding="utf-8"))

    return _load
