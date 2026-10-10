"""Load the golden cases from /cases into the database as published.

    python -m scripts.seed_golden_cases
Safe to re-run: refreshes the same case_id and version.
"""
from pathlib import Path

from app import db as dbmod
from app import services
from app.schemas.case import Case
from app.studio import publish

CASES_DIR = Path(__file__).resolve().parents[2] / "cases"


def main() -> None:
    with next(dbmod.get_session()) as s:
        for path in sorted(CASES_DIR.glob("*.json")):
            case = Case.model_validate_json(path.read_text(encoding="utf-8"))
            problems = publish.blockers(case)
            if problems:
                print(f"skip {case.case_id}: {'; '.join(problems)}")
                continue
            row = services.upsert_golden(s, case)
            print(f"seeded {row.case_id} v{row.version}")


if __name__ == "__main__":
    main()
