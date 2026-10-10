"""Imports the sponsor's Virtual Health Simulation (VHS) profiles into draft cases (PRD S-07).

Everything imported is a draft: faculty approve each item before publishing. Free text is
mapped with simple rules (regex), never an LLM, so the import is repeatable. Lines that
cannot be parsed are kept as draft facts with a note, not dropped.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from app import catalogs
from app.schemas.case import (
    Allergy, Briefing, Case, Diagnosis, ExamFinding, Fact, LabResult, Medication, Objective,
    Personality, Profile, Release, Source, Unlock, Vital,
)
from app.studio import consistency

VHS_PATH = catalogs.DATA_DIR / "vhs" / "virtual-patient-profiles-sample.json"
SRC_REF = "data/vhs/virtual-patient-profiles-sample.json"


class VhsImportError(Exception):
    """The bundled sample set could not be turned into drafts. Callers must not save a partial set."""

# Chart-text cues -> topic ids. Topic keywords in vocab/topics.yaml are written for what a
# student says; these are written for how the profile describes the patient.
FACT_TOPIC_HINTS: list[tuple[str, list[str]]] = [
    (r"\b(meds?|medication|pills?|metformin|insulin|lisinopril|dose|prescri)", ["medication_adherence", "medication_list"]),
    (r"\b(supplement|vitamin|tea|herbal|advil|ibuprofen|over.the.counter|otc)", ["otc_medications"]),
    (r"\b(breakfast)", ["diet_breakfast", "diet_general"]),
    (r"\b(juice|soda|water|drink|beverage|coffee)", ["diet_beverages"]),
    (r"\b(salt|sodium|salty)", ["diet_sodium"]),
    (r"\b(eat|food|meal|diet|snack|rice|carb|sugar|sweet|fast food|restaurant|takeout|dinner|lunch)", ["diet_general"]),
    (r"\b(cook|grocery|groceries|store|shopping|kitchen)", ["cooking_shopping"]),
    (r"\b(work|job|hours|shift|retired|employ)", ["occupation"]),
    (r"\b(money|afford|cost|financ|income|insurance|savings|budget)", ["finances_access"]),
    (r"\b(family|sister|brother|mother|father|parent|sibling|kids|children|wife|husband|partner|son|daughter)", ["social_support", "family_history"]),
    (r"\b(alone|lives|living|home|apartment|house)", ["social_living"]),
    (r"\b(friend|community|church|club|neighbor)", ["social_support", "hobbies_personal"]),
    (r"\b(alcohol|beer|wine|drinking)", ["alcohol"]),
    (r"\b(smok|tobacco|cigar|vape)", ["tobacco"]),
    (r"\b(drug use|substance|cannabis|marijuana|cocaine)", ["drugs"]),
    (r"\b(exercise|active|walk|gym|sport|weak)", ["physical_activity"]),
    (r"\b(sleep|insomnia|night)", ["sleep"]),
    (r"\b(stress|anxi|overwhelm)", ["stress"]),
    (r"\b(depress|mood|sad|hopeless|ptsd|trauma|eating disorder|body image)", ["mood", "psychiatric_history"]),
    (r"\b(believe|belief|thinks|trust)", ["beliefs_understanding"]),
    (r"\b(goal|wants? to|hope)", ["goals"]),
    (r"\b(fear|afraid|scared|worr|burden)", ["fears_worries"]),
    (r"\b(tired|fatigue|energy)", ["ros_general"]),
    (r"\b(thirst|urinat|bathroom)", ["ros_gu", "hpi_associated"]),
    (r"\b(breath|short of breath)", ["ros_respiratory"]),
    (r"\b(swell|edema|chest pain|heart)", ["ros_cardiac"]),
    (r"\b(hospital|admission|readmission|er\b|emergency)", ["hospitalizations"]),
    (r"\b(surgery|operation|cabg)", ["surgical_history"]),
    (r"\b(weight|lbs|pounds)", ["weight_change"]),
    (r"\b(injur|wound|pain)", ["hpi_character", "chief_complaint"]),
]

REPORTING_PREFIX = re.compile(r"^(he|she|they)\s+(mentions|reveals|admits|shares|says|states|reports|notes|expresses)(\s+that)?\s+", re.IGNORECASE)

LAB_PATTERNS: list[tuple[str, str]] = [
    (r"a1c", "a1c"), (r"egfr", "egfr"), (r"glucose", "glu"), (r"\bbun\b|urea nitrogen", "bun"), (r"creatinine", "cr"),
    (r"sodium", "na"), (r"potassium", "k"), (r"\bldl", "ldl"), (r"\bhdl", "hdl"), (r"triglycerides", "tg"),
    (r"total cholesterol|^\s*cholesterol\b|^\s*total\b", "chol"), (r"hemoglobin", "hgb"), (r"\balt\b", "alt"),
]

FINDING_TO_MANEUVER: list[tuple[str, str]] = [
    (r"murmur|heart sound|gallop", "cardiac_auscultation"),
    (r"crackle|wheez|rhonch|lung", "lung_auscultation"),
    (r"edema|swelling", "edema_check"),
    (r"pulse", "peripheral_pulses"),
    (r"venous distension|jugular|jvp", "jvp_inspection"),
    (r"gum|teeth|dental|oral", "oropharynx_inspection"),
    (r"skin|nail|tags|sores", "skin_inspection"),
    (r"bowel sound", "abdominal_auscultation"),
]


def load_profiles(path: Path = VHS_PATH) -> list[dict]:
    """The file is several pretty-printed JSON objects back to back, not one array."""
    raw = path.read_text(encoding="utf-8")
    dec, i, out = json.JSONDecoder(), 0, []
    while i < len(raw):
        while i < len(raw) and raw[i].isspace():
            i += 1
        if i >= len(raw):
            break
        obj, i = dec.raw_decode(raw, i)
        out.append(obj)
    return out


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def topics_for(text: str) -> list[str]:
    found: list[str] = []
    for pat, ids in FACT_TOPIC_HINTS:
        if re.search(pat, text, re.IGNORECASE):
            found += [t for t in ids if t not in found]
    if not found:
        for tid, label in catalogs.topics().items():
            if any(p.search(text) for p in label.patterns()):
                found.append(tid)
    return found[:4]


def _src(path: str) -> Source:
    return Source(kind="vhs_import", ref=f"{SRC_REF} :: {path}")


def _fact(fid: str, text: str, tier: str, category: str, path: str, **kw) -> Fact:
    clean = REPORTING_PREFIX.sub("", text.strip())
    clean = clean[:1].upper() + clean[1:]
    return Fact(id=fid, category=category, text=clean, tier=tier, unlock=Unlock(topics=topics_for(clean)), source=_src(path), status="draft", **kw)


MIXED_TOKEN = re.compile(r"\b(?=[a-z0-9]*[a-z])(?=[a-z0-9]*\d)[a-z0-9]+\b", re.IGNORECASE)  # A1c, SpO2, O2


def first_number(text: str) -> re.Match | None:
    """First number in the value part of a line, ignoring labels like "A1c" or "SpO2"."""
    _, sep, value = text.partition(":")
    return re.search(r"(\d+(?:\.\d+)?)", MIXED_TOKEN.sub(" ", value if sep else text))


def parse_labs(lines: list[str], female: bool) -> tuple[list[LabResult], list[str]]:
    labs: dict[str, LabResult] = {}
    unparsed: list[str] = []
    for line in lines:
        prefix, _, rest = line.partition(":") if ":" in line else ("", "", line)
        segments = [s for s in re.split(r",", rest)] if rest else [line]
        any_hit = False
        for seg in segments:
            text = seg if prefix and re.search(r"[a-z]", seg, re.IGNORECASE) else f"{prefix} {seg}"
            num = re.search(r"(\d+(?:\.\d+)?)", MIXED_TOKEN.sub(" ", seg))
            key = next((k for p, k in LAB_PATTERNS if re.search(p, text, re.IGNORECASE)), None)
            if key is None and prefix:
                key = next((k for p, k in LAB_PATTERNS if re.search(p, prefix, re.IGNORECASE)), None)
            if key is None or num is None or key in labs:
                continue
            lab = catalogs.lab_by_key(key)
            low, high = (lab.get("low_f"), lab.get("high_f")) if female and "low_f" in lab else (lab.get("low"), lab.get("high"))
            labs[key] = LabResult(
                id=f"lab_{key}", key=key, name=lab["name"], loinc=lab.get("loinc"), panel=lab.get("panel"),
                value=float(num.group(1)) if "." in num.group(1) else int(num.group(1)), unit=lab.get("unit", ""),
                ref_low=low, ref_high=high, ref_source=catalogs.lab_catalog()["ref_source"],
                release=Release(on="visit_start"), source=_src(f"clinical_profile.laboratory_data: {line.strip()}"),
            )
            any_hit = True
        if not any_hit:
            unparsed.append(line.strip())
    return list(labs.values()), unparsed


def parse_vitals(lines: list[str]) -> tuple[list[Vital], list[str]]:
    vitals: dict[str, Vital] = {}
    unparsed: list[str] = []

    def add(key, label, value, unit, line):
        if key not in vitals:
            vitals[key] = Vital(key=key, label=label, value=value, unit=unit, source=_src(f"clinical_profile: {line.strip()}"))

    for line in lines:
        low = line.lower()
        name = low.split(":")[0]
        if m := re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", line):
            if "bp" in name or "blood pressure" in name:
                add("bp", "Blood pressure", f"{m.group(1)}/{m.group(2)}", "mmHg", line)
                continue
        num = first_number(line)
        if re.search(r"heart rate|^\s*hr\b|^\s*pulse:", name) and num:
            add("hr", "Heart rate", num.group(1), "bpm", line)
        elif re.search(r"respiratory rate|^\s*rr\b", name) and num:
            add("rr", "Breathing rate", num.group(1), "breaths/min", line)
        elif name.startswith("temp") and num:
            c = re.search(r"(\d+(?:\.\d+)?)\s*\W?C\)", line)
            temp_c = float(c.group(1)) if c else round((float(num.group(1)) - 32) * 5 / 9, 1)
            add("temp_c", "Temperature", f"{temp_c:.1f}", "°C", line)
        elif re.search(r"spo2|o2 sat|pulse ox|oxygen sat", name) and num:
            add("spo2", "Oxygen saturation", num.group(1), "%", line)
        elif name.strip() == "weight" and num:
            add("weight", "Weight", num.group(1), "lb", line)
        elif name.strip() == "height" and (h := re.search(r"(\d)'\s*(\d{1,2})", line)):
            add("height", "Height", str(int(h.group(1)) * 12 + int(h.group(2))), "in", line)
        elif name.strip() == "bmi" and num:
            add("bmi", "Body mass index (BMI)", num.group(1), "kg/m2", line)
        elif name.strip() in ("waist circumference",) and num:
            add("waist", "Waist circumference", num.group(1), "in", line)
        else:
            unparsed.append(line.strip())
    return list(vitals.values()), unparsed


def parse_findings(lines: list[str]) -> tuple[list[ExamFinding], list[str]]:
    out: dict[str, ExamFinding] = {}
    unparsed: list[str] = []
    for line in lines:
        m = next((man for p, man in FINDING_TO_MANEUVER if re.search(p, line, re.IGNORECASE)), None)
        if m and m not in out:
            out[m] = ExamFinding(maneuver=m, finding=line.strip(), abnormal=True, source=_src(f"clinical_profile.clinical_findings: {line.strip()}"))
        else:
            unparsed.append(line.strip())
    return list(out.values()), unparsed


def _token_set(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", s.lower()) if len(w) > 3}


def link_discoveries(expected: list[str], facts: list[Fact]) -> list[str]:
    """Link each expected discovery to the fact with the most word overlap (at least 2 words)."""
    ids = []
    for e in expected:
        et = _token_set(e)
        best = max(facts, key=lambda f: len(et & _token_set(f.text)), default=None)
        if best and len(et & _token_set(best.text)) >= 2 and best.id not in ids:
            ids.append(best.id)
    return ids


def _example_lines(opportunities: list[dict]) -> list[str]:
    """Sponsor reaction lines become example lines. The wording is copied, not rewritten."""
    lines: list[str] = []
    for opportunity in opportunities:
        for line in opportunity.get("possible_patient_reactions", []):
            text = str(line).strip()
            # The same sentence can appear on more than one objective. Keep the first copy.
            if text and text not in lines:
                lines.append(text)
    return lines


def import_profile(p: dict, index: int) -> Case:
    """Turn one sponsor profile into a draft case. Free text is mapped with rules, never an LLM."""
    ov, demo, clin = p["patient_overview"], p.get("demographics", {}), p.get("clinical_profile", {})
    meds, nut, psy = p.get("medication_profile", {}), p.get("nutrition_profile", {}), p.get("psychosocial_profile", {})
    disc, learn, meta = p.get("information_disclosure", {}), p.get("learning_opportunities", {}), p.get("metadata", {})
    name = ov["name"]
    sex = str(ov.get("sex", "")).lower()
    female = sex == "female"
    case_id = slug(name)
    facts: list[Fact] = []

    tier_map = {"initial_information": "initial", "discoverable_information": "discoverable", "reluctant_information": "reluctant", "hidden_information": "hidden"}
    for key, tier in tier_map.items():
        for n, line in enumerate(disc.get(key, []), 1):
            facts.append(_fact(f"f_{tier}_{n}", line, tier, "history", f"information_disclosure.{key}[{n - 1}]"))

    for n, line in enumerate(clin.get("current_symptoms", []), 1):
        facts.append(_fact(f"f_symptom_{n}", line, "discoverable", "ros", f"clinical_profile.current_symptoms[{n - 1}]"))
    for n, line in enumerate(clin.get("medical_history", []), 1):
        f = _fact(f"f_history_{n}", line, "discoverable", "history", f"clinical_profile.medical_history[{n - 1}]")
        f.unlock.topics = list(dict.fromkeys(["medical_history"] + f.unlock.topics))[:4]
        facts.append(f)
    for n, m in enumerate(meds.get("medications", []), 1):
        detail = "; ".join(x for x in (m.get("adherence"), m.get("patient_concerns")) if x)
        if detail:
            facts.append(_fact(f"f_med_{n}", f"{m['name']}: {detail}", "discoverable", "medication", f"medication_profile.medications[{n - 1}]"))
    for n, line in enumerate(meds.get("supplements_and_otc", []), 1):
        f = _fact(f"f_otc_{n}", line, "discoverable", "medication", f"medication_profile.supplements_and_otc[{n - 1}]")
        f.unlock.topics = ["otc_medications"]
        facts.append(f)
    for key in ("dietary_pattern", "meal_pattern", "hydration", "physical_activity", "substance_use", "sleep"):
        if nut.get(key):
            facts.append(_fact(f"f_{key}", f"{key.replace('_', ' ').capitalize()}: {nut[key]}", "discoverable", "diet", f"nutrition_profile.{key}"))
    for key in ("goals", "concerns", "beliefs", "fears", "barriers", "motivations"):
        for n, line in enumerate(psy.get(key, []), 1):
            facts.append(_fact(f"f_{key}_{n}", line, "discoverable", "personal", f"psychosocial_profile.{key}[{n - 1}]"))
    if psy.get("support_system"):
        facts.append(_fact("f_support", f"Support system: {psy['support_system']}", "discoverable", "social", "psychosocial_profile.support_system"))
    for n, line in enumerate(meta.get("optional_details", []), 1):
        f = _fact(f"f_optional_{n}", line, "discoverable", "personal", f"metadata.optional_details[{n - 1}]")
        f.cue = True
        facts.append(f)

    labs, lab_left = parse_labs(clin.get("laboratory_data", []), female)
    vitals, vit_left = parse_vitals(clin.get("vital_signs", []) + clin.get("anthropometrics", []))
    exam, find_left = parse_findings(clin.get("clinical_findings", []))
    for n, line in enumerate(lab_left + vit_left + find_left, 1):
        facts.append(Fact(id=f"f_chart_note_{n}", category="other", text=line, tier="discoverable", source=_src(f"clinical_profile (could not map automatically): {line}"), status="draft"))

    diagnoses = [Diagnosis(name=clin["primary_diagnosis"], source=_src("clinical_profile.primary_diagnosis"))] if clin.get("primary_diagnosis") else []
    diagnoses += [Diagnosis(name=d, source=_src("clinical_profile.secondary_diagnoses")) for d in clin.get("secondary_diagnoses", [])]
    medications = [Medication(name=m["name"], dose=m.get("dose"), frequency=m.get("frequency"), purpose=m.get("purpose"), source=_src(f"medication_profile.medications[{i}]")) for i, m in enumerate(meds.get("medications", []))]
    allergies = []
    for a in clin.get("allergies", []):
        if re.search(r"no known", a, re.IGNORECASE):
            continue
        m = re.match(r"\s*([^()]+?)\s*(?:\((.+)\))?\s*$", a)
        allergies.append(Allergy(substance=m.group(1) if m else a, reaction=m.group(2) if m else None, source=_src("clinical_profile.allergies")))

    opportunities = learn.get("opportunities", [])
    objectives = []
    for n, opp in enumerate(opportunities, 1):
        expected = opp.get("expected_discoveries", [])
        text = opp["learning_objective"] + (" (VHS expected: " + "; ".join(expected) + ")" if expected else "")
        objectives.append(Objective(id=f"obj_{n}", text=text, expected_discoveries=link_discoveries(expected, facts)))

    portrait = f"{case_id}.jpg" if (catalogs.DATA_DIR / "portraits" / f"{case_id}.jpg").exists() else None
    case = Case(
        case_id=case_id,
        title=f"{name}: {clin.get('primary_diagnosis', '')}".strip(": "),
        description=ov.get("description", ""),
        seed=index + 1,
        profile=Profile(
            name=name, age=int(ov["age"]), sex=sex if sex in ("male", "female") else "other",
            portrait=portrait, occupation=demo.get("occupation"),
            summary=" ".join([ov.get("description", "")] + [f"Assumption: {a}" for a in meta.get("assumptions", [])]),
            personality=Personality(
                summary=psy.get("personality", ""), communication_style=psy.get("communication_style", ""),
                health_literacy="low" if re.search(r"limited|low", " ".join(psy.get("barriers", [])), re.IGNORECASE) else "medium",
                example_lines=_example_lines(opportunities),
            ),
        ),
        briefing=Briefing(setting="Outpatient clinic", reason_for_visit=clin.get("primary_diagnosis", ""), goal="", student_role=""),
        facts=facts, vitals=vitals, labs=labs, exam=exam, diagnoses=diagnoses, medications=medications, allergies=allergies,
        objectives=objectives, documentation_template="PES",
        credits=[{"what": "Patient profile", "source": "Rutgers Virtual Health Simulation sample profiles (event-provided)"}],
    )
    # Run the same rules faculty see later, and keep the findings on the draft for review.
    case.consistency_findings = consistency.check(case)
    return case


def import_all(path: Path | None = None) -> list[Case]:
    """Load the bundled sample set. The path is read at call time so a missing file fails the import."""
    source = VHS_PATH if path is None else path
    try:
        profiles = load_profiles(source)
        # Build every draft before anything is saved. A bad profile must not leave a partial set.
        cases = [import_profile(profile, index) for index, profile in enumerate(profiles)]
    except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        raise VhsImportError("The sponsor sample set could not be imported.") from exc
    if not cases:
        raise VhsImportError("The sponsor sample set could not be imported.")
    return cases
