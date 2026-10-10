"""Publish gate (PRD S-06). A case is published only when a person approved every item."""
from __future__ import annotations

from app.schemas.case import Case
from app.studio import consistency, intake


def blockers(case: Case) -> list[str]:
    out: list[str] = []
    groups = {
        "facts": case.facts, "vitals": case.vitals, "labs": case.labs, "exam findings": case.exam,
        "documents": case.artifacts, "diagnoses": case.diagnoses, "medications": case.medications,
        "allergies": case.allergies, "objectives": case.objectives,
    }
    for name, items in groups.items():
        n = sum(1 for i in items if i.status != "approved")
        if n:
            out.append(f"{n} {name} still need approval.")
    for v in case.visits:
        n = sum(1 for b in v.branches if b.status != "approved")
        if n:
            out.append(f"{v.label}: {n} outcomes still need approval.")
    out += [f"Missing: {g['question']}" for g in intake.gaps(case) if g["blocking"]]
    dismissed = {f.message for f in case.consistency_findings if f.dismissed}
    open_review = [f for f in consistency.check(case) if f.severity == "review" and f.message not in dismissed]
    if open_review:
        out.append(f"{len(open_review)} consistency issues to fix or dismiss.")
    return out
