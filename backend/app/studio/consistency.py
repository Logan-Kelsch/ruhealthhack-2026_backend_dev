"""Consistency check (PRD S-05). Deterministic rules over the case document.

Each rule returns findings for faculty to fix or dismiss. Nothing here edits the case.
TODO(clinical-review): the clinical reviewer confirms each safety rule before any claim.
"""
from __future__ import annotations

import re

from app import catalogs
from app.schemas.case import Case, ConsistencyFinding
from app.studio.autofill.formulas import bmi

LAB_WORDS = {
    "na": r"sodium|\bna\b", "k": r"potassium|\bk\b", "glu": r"glucose|sugar", "a1c": r"a1c",
    "cr": r"creatinine", "ldl": r"\bldl\b", "hdl": r"\bhdl\b", "egfr": r"egfr",
}


def _all_text(case: Case) -> list[tuple[str, str]]:
    """(ref, text) for every free-text place a contradiction can hide."""
    out = [(f.id, f"{f.text} {f.say or ''}") for f in case.facts]
    out += [("description", case.description), ("profile.summary", case.profile.summary)]
    out += [(f"artifact:{a.id}", a.body or "") for a in case.artifacts]
    out += [(o.id, o.text) for o in case.objectives]
    return [(r, t) for r, t in out if t.strip()]


def _generic(name: str) -> str | None:
    drugs = catalogs.drug_list()
    low = name.lower()
    for brand, generic in drugs["brands"].items():
        if re.search(rf"\b{re.escape(brand)}\b", low):
            return generic
    for g in sorted(drugs["generics"], key=len, reverse=True):
        if re.search(rf"\b{re.escape(g)}\b", low):
            return g
    return None


def _class_of(generic: str) -> list[str]:
    return [c for c, members in catalogs.drug_list()["classes"].items() if generic in members]


def _has_condition(case: Case, pattern: str) -> bool:
    text = " ".join(d.name + " " + " ".join(c.code for c in d.codes) for d in case.diagnoses) + " " + case.description
    return bool(re.search(pattern, text, re.IGNORECASE))


def _lab(case: Case, key: str):
    return next((lab for lab in case.labs if lab.key == key and isinstance(lab.value, (int, float))), None)


def check(case: Case) -> list[ConsistencyFinding]:
    found: list[ConsistencyFinding] = []

    def add(rule: str, message: str, refs: list[str], severity: str = "review"):
        found.append(ConsistencyFinding(id=f"{rule}_{len(found) + 1}", rule=rule, severity=severity, message=message, refs=refs))

    age = case.profile.age
    for ref, text in _all_text(case):
        for m in re.finditer(r"\b(\d{1,3})[- ]year[- ]old\b", text, re.IGNORECASE):
            if int(m.group(1)) != age:
                add("age_mismatch", f"Text says {m.group(0)} but the profile age is {age}.", [ref])
        for m in re.finditer(r"\bin (his|her|their|the) (\d0)s\b", text, re.IGNORECASE):
            decade = int(m.group(2))
            if not decade <= age < decade + 10:
                add("age_mismatch", f"Text says \"{m.group(0)}\" but the profile age is {age}.", [ref])

    for ref, text in _all_text(case):
        for key, word in LAB_WORDS.items():
            lab = _lab(case, key)
            if lab is None:
                continue
            for direction in ("high", "low", "elevated", "decreased"):
                # Needs lab context nearby, so "high sodium foods" is not read as a lab claim.
                pattern = rf"\b{direction}\s+({word})(?!\s+(food|diet|intake|snack))|({word})\s+(level\s+)?(is\s+)?{direction}\b"
                if re.search(pattern, text, re.IGNORECASE) and re.search(r"\blabs?\b|\blevels?\b|blood|result", text, re.IGNORECASE):
                    want = "high" if direction in ("high", "elevated") else "low"
                    if lab.flag() != want:
                        add("lab_text_mismatch", f"Text calls {lab.name} {want}, but the value {lab.value} {lab.unit} is {lab.flag() or 'in range'}.", [ref, f"lab:{lab.key}"])

    for i, med in enumerate(case.medications):
        names = re.split(r"[()/]", med.name)
        unknown = [n.strip() for n in names if n.strip() and _generic(n) is None]
        if unknown and _generic(med.name) is not None:
            add("unknown_drug_name", f"\"{med.name}\": {', '.join(unknown)} is not a drug name we recognise (the generic is {_generic(med.name)}). Check the spelling.", [f"medication:{i}"])
        elif _generic(med.name) is None:
            add("unknown_drug_name", f"\"{med.name}\" is not in the local drug list. Check the spelling or add it.", [f"medication:{i}"])
        if not med.purpose:
            add("medication_without_indication", f"{med.name} has no reason recorded.", [f"medication:{i}"], "info")

    weight_loss_unintended = [r for r, t in _all_text(case) if re.search(r"lost .{0,20}unintentional|unintentional(ly)? .{0,20}(lost|loss)", t, re.IGNORECASE)]
    weight_loss_failing = [r for r, t in _all_text(case) if re.search(r"(poor|no|unable to|can.?t) .{0,15}(lose weight|weight loss)", t, re.IGNORECASE)]
    if weight_loss_unintended and weight_loss_failing:
        add("weight_contradiction", "One place says the patient lost weight without trying; another says they cannot lose weight.", weight_loss_unintended + weight_loss_failing)

    kids = [r for r, t in _all_text(case) if re.search(r"\b(kids|children|grandchildren|son|daughter)\b", t, re.IGNORECASE)]
    support = [(r, t) for r, t in _all_text(case) if re.search(r"support system|only support|lives alone", t, re.IGNORECASE)]
    if kids and support and not any(re.search(r"\b(kids|children|son|daughter)\b", t, re.IGNORECASE) for _, t in support):
        add("family_contradiction", "Children are mentioned, but the support-system description does not include them.", kids[:2] + [r for r, _ in support][:2], "info")

    w = next((v for v in case.vitals if v.key == "weight"), None)
    h = next((v for v in case.vitals if v.key == "height"), None)
    b = next((v for v in case.vitals if v.key == "bmi"), None)
    if w and h and b:
        try:
            calc = bmi(float(w.value), float(h.value))
            if abs(calc - float(b.value)) > 0.5:
                add("bmi_mismatch", f"BMI is listed as {b.value}, but height and weight give {calc:.1f}.", ["vital:bmi", "vital:weight", "vital:height"])
        except ValueError:
            pass

    all_drug_text = [(f"medication:{i}", m.name) for i, m in enumerate(case.medications)] + [(f.id, f.text) for f in case.facts if f.category == "medication"]
    nsaids = [(r, t) for r, t in all_drug_text if (g := _generic(t)) and "nsaid" in _class_of(g) and g != "aspirin"]
    if nsaids and _has_condition(case, r"heart failure|\bI50|\bHF|kidney|\bCKD|\bN18"):
        add("nsaid_with_hf_or_ckd", "The patient takes an NSAID (for example ibuprofen) and has heart failure or kidney disease. This is a safety teaching point; make sure it is a fact students can discover.", [r for r, _ in nsaids], "info")

    egfr = _lab(case, "egfr")
    if egfr and egfr.value < 30 and any(_generic(m.name) == "metformin" for m in case.medications):
        add("metformin_low_egfr", f"Metformin is listed with eGFR {egfr.value}. Metformin is not recommended below 30.", ["lab:egfr"])

    for a in case.allergies:
        a_generic = _generic(a.substance) or a.substance.lower().strip()
        a_classes = set(_class_of(a_generic)) | ({a_generic} if a_generic in catalogs.drug_list()["classes"] else set())
        for i, m in enumerate(case.medications):
            g = _generic(m.name)
            if g and (g == a_generic or a_classes & set(_class_of(g))):
                add("allergy_conflict", f"{m.name} is listed, but the patient is allergic to {a.substance}.", [f"medication:{i}", "allergies"])

    for f in case.facts:
        if f.tier != "initial" and not f.unlock.topics:
            add("fact_unreachable", f"No topic unlocks this fact, so students can never hear it: \"{f.text[:80]}\".", [f.id], "info")
        for req in f.unlock.requires_facts:
            if case.fact(req) is None:
                add("missing_reference", f"Fact {f.id} requires {req}, which does not exist.", [f.id])
    for o in case.objectives:
        for fid in o.expected_discoveries:
            if case.fact(fid) is None:
                add("missing_reference", f"Objective {o.id} expects fact {fid}, which does not exist.", [o.id])
    for v in case.visits:
        dp_ids = {d.id for d in v.decision_points}
        for br in v.branches:
            for dp in br.when:
                if dp not in dp_ids:
                    add("missing_reference", f"Branch {br.id} depends on decision point {dp}, which is not in {v.id}.", [br.id])
    unique: dict[str, ConsistencyFinding] = {}
    for f in found:
        unique.setdefault(f.message, f)
    return list(unique.values())
