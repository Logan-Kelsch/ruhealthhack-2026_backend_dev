"""Loads the fixed vocabularies (app/vocab) and reference data (app/data) once."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

APP_DIR = Path(__file__).resolve().parent
VOCAB_DIR = APP_DIR / "vocab"
DATA_DIR = APP_DIR / "data"


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@dataclass(frozen=True)
class Label:
    id: str
    description: str
    keywords: tuple[str, ...] = ()
    sensitive: bool = False
    extra: dict = field(default_factory=dict, compare=False, hash=False)

    def patterns(self) -> list[re.Pattern]:
        return [re.compile(k, re.IGNORECASE) for k in self.keywords]


@lru_cache
def topics() -> dict[str, Label]:
    raw = _load_yaml(VOCAB_DIR / "topics.yaml")["topics"]
    return {t["id"]: Label(t["id"], t["description"], tuple(t.get("keywords", [])), bool(t.get("sensitive", False))) for t in raw}


@lru_cache
def actions() -> dict[str, Label]:
    raw = _load_yaml(VOCAB_DIR / "actions.yaml")["actions"]
    return {a["id"]: Label(a["id"], a["description"], tuple(a.get("keywords", []))) for a in raw}


@lru_cache
def maneuvers() -> dict[str, dict]:
    raw = _load_yaml(VOCAB_DIR / "maneuvers.yaml")["maneuvers"]
    return {m["id"]: m for m in raw}


@lru_cache
def trust_events() -> dict[str, dict]:
    raw = _load_yaml(VOCAB_DIR / "trust_events.yaml")["events"]
    return {e["id"]: e for e in raw}


@lru_cache
def lay_lexicon() -> list[dict]:
    return _load_yaml(VOCAB_DIR / "lay_lexicon.yaml")["terms"]


@lru_cache
def lab_catalog() -> dict:
    return _load_yaml(DATA_DIR / "lab_reference.yaml")


def lab_by_key(key: str) -> dict | None:
    return next((lab for lab in lab_catalog()["labs"] if lab["key"] == key), None)


@lru_cache
def drug_list() -> dict:
    return _load_yaml(DATA_DIR / "drugs.yaml")


@lru_cache
def rubric(rubric_id: str = "shp_patient_encounter_v1") -> dict:
    if rubric_id != "shp_patient_encounter_v1":
        raise KeyError(f"unknown rubric {rubric_id}")
    with open(DATA_DIR / "rubric_shp_v1.json", encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache
def documentation_templates() -> dict:
    return _load_yaml(DATA_DIR / "documentation_templates.yaml")["templates"]
