"""Statistically grounded auto-fill (PRD S-04). No LLM involved.

Each missing lab or vital gets a value from, in order:
1. a guideline rule for a condition the case has (for example diabetes -> A1C 7.0 to 9.5),
2. a formula from other values (eGFR, anion gap, total cholesterol),
3. a sample from the typical reference interval.
Sampling is a truncated normal centred in the interval and seeded by the case seed, so
the same case always gets the same numbers. Every value records its source.
"""
from __future__ import annotations

import random
import re
import zlib

from app import catalogs
from app.schemas.case import Case, LabResult, Release, Source, ValueRange, Vital
from app.studio.autofill import formulas

# Condition rules. TODO(clinical-review): confirm each band with the clinical reviewer.
CONDITION_RULES = [
    {
        "id": "diabetes",
        "match": [r"\bE11", r"diabet"],
        "labs": {"a1c": (7.0, 9.5), "glu": (130, 200)},
        "ref": "ADA Standards of Care: A1C 6.5% or more is diagnostic; a band above the usual 7% target",
    },
    {
        "id": "ckd3",
        "match": [r"\bN18\.3", r"ckd|chronic kidney"],
        "egfr": (35, 55),
        "ref": "KDIGO 2024: CKD stage G3 is eGFR 30 to 59; creatinine solved from CKD-EPI 2021",
    },
    {
        "id": "hypertension",
        "match": [r"\bI10\b", r"hypertension|high blood pressure"],
        "vitals": {"sbp": (140, 165), "dbp": (90, 100)},
        "ref": "ACC/AHA 2017: stage 2 hypertension is 140/90 or higher",
    },
    {
        "id": "dyslipidemia",
        "match": [r"\bE78", r"hyperlipid|dyslipid|high cholesterol"],
        "labs": {"ldl": (160, 190)},
        "ref": "ACC/AHA 2018 cholesterol guideline: LDL 160 to 189 is high",
    },
]


def _rng(seed: int, key: str) -> random.Random:
    return random.Random(seed * 1_000_003 + zlib.crc32(key.encode()))


def truncated_normal(seed: int, key: str, low: float, high: float) -> float:
    rng = _rng(seed, key)
    mu, sd = (low + high) / 2, (high - low) / 4
    for _ in range(100):
        x = rng.gauss(mu, sd)
        if low <= x <= high:
            return x
    return mu


def _round(x: float, decimals: int) -> float | int:
    return int(round(x)) if decimals == 0 else round(x, decimals)


def case_conditions(case: Case) -> list[dict]:
    text = " ".join([d.name + " " + " ".join(c.code for c in d.codes) for d in case.diagnoses] + [case.description])
    return [r for r in CONDITION_RULES if any(re.search(p, text, re.IGNORECASE) for p in r["match"])]


def _ref(lab: dict, female: bool) -> tuple[float | None, float | None]:
    if female and "low_f" in lab:
        return lab["low_f"], lab["high_f"]
    return lab.get("low"), lab.get("high")


def _lab(key: str, value, source: Source, female: bool, rng_range: tuple[float, float] | None = None) -> LabResult:
    lab = catalogs.lab_by_key(key)
    low, high = _ref(lab, female)
    return LabResult(
        id=f"lab_{key}",
        key=key,
        name=lab["name"],
        loinc=lab.get("loinc"),
        panel=lab.get("panel"),
        value=value,
        unit=lab.get("unit", ""),
        ref_low=low,
        ref_high=high,
        ref_source=catalogs.lab_catalog()["ref_source"],
        range=ValueRange(low=rng_range[0], high=rng_range[1]) if rng_range else None,
        release=Release(on="order"),
        source=source,
        status="draft",
    )


def autofill_labs(case: Case, panels: list[str]) -> tuple[list[LabResult], list[str]]:
    """Propose values for every lab in the requested panels that the case does not already have."""
    notes: list[str] = []
    if case.profile.age < 18:
        return [], ["Labs are not auto-filled for patients under 18. Enter any results by hand."]
    female = case.profile.sex == "female"
    existing = {lab.key: lab for lab in case.labs}
    conditions = case_conditions(case)
    rule_ranges: dict[str, tuple[tuple[float, float], str]] = {}
    egfr_target: tuple[tuple[float, float], str] | None = None
    for c in conditions:
        for k, rng in c.get("labs", {}).items():
            rule_ranges[k] = (rng, c["ref"])
        if "egfr" in c:
            egfr_target = (c["egfr"], c["ref"])
    values: dict[str, float] = {k: lab.value for k, lab in existing.items() if isinstance(lab.value, (int, float))}
    out: list[LabResult] = []
    catalog = [lab for lab in catalogs.lab_catalog()["labs"] if lab.get("panel") in panels]
    for lab in catalog:
        key = lab["key"]
        if key in existing or lab.get("computed") or lab.get("qualitative"):
            continue
        dec = lab.get("decimals", 1)
        if key == "cr" and egfr_target:
            (lo, hi), ref = egfr_target
            target = truncated_normal(case.seed, "egfr", lo, hi)
            val = _round(formulas.creatinine_for_egfr(target, case.profile.age, female), dec)
            out.append(_lab(key, val, Source(kind="rule", ref=f"{ref}; target eGFR {target:.0f}"), female, (lo, hi)))
        elif key in rule_ranges:
            (lo, hi), ref = rule_ranges[key]
            val = _round(truncated_normal(case.seed, key, lo, hi), dec)
            out.append(_lab(key, val, Source(kind="rule", ref=ref), female, (lo, hi)))
        elif key == "chol" and ("ldl" in rule_ranges or "ldl" in values):
            continue  # computed after LDL/HDL/TG below so the panel adds up
        else:
            low, high = _ref(lab, female)
            if low is None or high is None:
                continue
            val = _round(truncated_normal(case.seed, key, low, high), dec)
            out.append(_lab(key, val, Source(kind="reference", ref=catalogs.lab_catalog()["ref_source"]), female, (low, high)))
        values[key] = out[-1].value
    out += _computed(case, values, existing, panels, female)
    if conditions:
        notes.append("Used condition rules for: " + ", ".join(c["id"] for c in conditions) + ".")
    return out, notes


def _computed(case: Case, values: dict, existing: dict, panels: list[str], female: bool) -> list[LabResult]:
    out = []
    if "bmp" in panels:
        if "egfr" not in existing and "cr" in values:
            v = _round(formulas.egfr_ckd_epi_2021(values["cr"], case.profile.age, female), 0)
            out.append(_lab("egfr", v, Source(kind="computed", ref="CKD-EPI 2021 creatinine equation (race-free)"), female))
        if "anion_gap" not in existing and all(k in values for k in ("na", "cl", "hco3")):
            v = _round(formulas.anion_gap(values["na"], values["cl"], values["hco3"]), 0)
            out.append(_lab("anion_gap", v, Source(kind="computed", ref="Na - (Cl + HCO3)"), female))
    if "lipid" in panels and "chol" not in existing and all(k in values for k in ("ldl", "hdl", "tg")):
        v = _round(formulas.friedewald_total_cholesterol(values["ldl"], values["hdl"], values["tg"]), 0)
        out.append(_lab("chol", v, Source(kind="computed", ref="Friedewald relation: TC = LDL + HDL + TG/5"), female))
    return out


VITAL_LABELS = {"bp": "Blood pressure", "hr": "Heart rate", "rr": "Breathing rate", "temp_c": "Temperature", "spo2": "Oxygen saturation"}


def autofill_vitals(case: Case) -> tuple[list[Vital], list[str]]:
    age = case.profile.age
    band = "adult" if age >= 18 else "child_6_12" if 6 <= age <= 12 else None
    if band is None:
        return [], [f"No vital-sign reference band for age {age}. Enter vitals by hand."]
    ranges = dict(catalogs.lab_catalog()["vitals"][band])
    src = {k: Source(kind="reference", ref=f"Typical resting range ({band.replace('_', ' ')})") for k in ranges}
    for c in case_conditions(case) if band == "adult" else []:
        for k, (lo, hi) in c.get("vitals", {}).items():
            ranges[k] = {**ranges[k], "low": lo, "high": hi}
            src[k] = Source(kind="rule", ref=c["ref"])
    have = {v.key for v in case.vitals}
    out: list[Vital] = []

    def val(k: str):
        r = ranges[k]
        return _round(truncated_normal(case.seed, f"vital_{k}", r["low"], r["high"]), r.get("decimals", 0))

    if "bp" not in have:
        out.append(Vital(key="bp", label=VITAL_LABELS["bp"], value=f"{val('sbp')}/{val('dbp')}", unit="mmHg", source=src["sbp"]))
    for k in ("hr", "rr", "temp_c", "spo2"):
        if k not in have:
            out.append(Vital(key=k, label=VITAL_LABELS[k], value=str(val(k)), unit=ranges[k]["unit"], source=src[k]))
    return out, []
