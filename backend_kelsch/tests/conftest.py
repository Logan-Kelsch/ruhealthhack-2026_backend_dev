"""Fixtures for the isolated notebook tests."""
import os
from pathlib import Path

import pytest

os.environ["LLM_ENABLED"] = "false"
os.environ["NLM_LOOKUP_ENABLED"] = "false"
os.environ.pop("ELEVENLABS_API_KEY", None)


@pytest.fixture
def load_golden():
    from app.schemas.case import Case
    cases_dir = Path(__file__).resolve().parents[2] / "cases"

    def load(case_id: str) -> Case:
        return Case.model_validate_json((cases_dir / f"{case_id}.json").read_text())

    return load
