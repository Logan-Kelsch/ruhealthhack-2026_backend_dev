"""Code lookup for diagnoses (ICD-10-CM) via the NLM Clinical Table Search Service.

https://clinicaltables.nlm.nih.gov/ is free and needs no key. A small local list answers
the common codes offline and is used when the lookup is off or unreachable.
"""
from __future__ import annotations

import logging
from functools import lru_cache

import httpx

from app.settings import get_settings

log = logging.getLogger(__name__)
ICD10_URL = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"

LOCAL_ICD10 = {
    "E11.65": "Type 2 diabetes mellitus with hyperglycemia",
    "E11.9": "Type 2 diabetes mellitus without complications",
    "I10": "Essential (primary) hypertension",
    "I50.22": "Chronic systolic (congestive) heart failure",
    "I50.9": "Heart failure, unspecified",
    "N18.30": "Chronic kidney disease, stage 3 unspecified",
    "I25.10": "Atherosclerotic heart disease of native coronary artery without angina pectoris",
    "Z95.1": "Presence of aortocoronary bypass graft",
    "F32.1": "Major depressive disorder, single episode, moderate",
    "F32.A": "Depression, unspecified",
    "F31.9": "Bipolar disorder, unspecified",
    "J06.9": "Acute upper respiratory infection, unspecified",
    "J02.9": "Acute pharyngitis, unspecified",
    "J02.0": "Streptococcal pharyngitis",
    "E78.5": "Hyperlipidemia, unspecified",
    "E66.9": "Obesity, unspecified",
    "M54.50": "Low back pain, unspecified",
}


def _local(q: str) -> list[dict]:
    ql = q.lower()
    return [{"code": c, "display": d} for c, d in LOCAL_ICD10.items() if ql in d.lower() or ql in c.lower()][:10]


@lru_cache(maxsize=512)
def search_icd10(q: str) -> tuple[dict, ...]:
    q = q.strip()
    if not q:
        return ()
    if not get_settings().nlm_lookup_enabled:
        return tuple(_local(q))
    try:
        r = httpx.get(ICD10_URL, params={"sf": "code,name", "terms": q, "maxList": 10}, timeout=5)
        r.raise_for_status()
        data = r.json()
        return tuple({"code": code, "display": name} for code, name in data[3])
    except (httpx.HTTPError, ValueError, IndexError) as exc:
        log.info("NLM lookup unavailable, using local list: %s", exc)
        return tuple(_local(q))
