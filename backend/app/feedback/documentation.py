"""Checks the student's note against what the encounter actually revealed (PRD F-06).

Two outputs:
- unsupported: statements in the note that no disclosed fact or released chart item backs
  (possible fabrication);
- missing: key findings the student did discover but left out of the note.

LLM path labels each statement with the ids that support it; ids are validated. The
fallback is deterministic: numbers in the note must appear in the evidence, and key
findings are matched by word overlap.
"""
from __future__ import annotations

import re

from app.encounter.verifier import numbers_in
from app.integrations.bedrock import LLMUnavailable, complete_json
from app.schemas.case import Case

STOP = set("a an and are as at be been but by for from had has have he her his i in is it its me my no not of on or our she so that the their them they this to was we were with you your about after before very just also than".split())


def _tokens(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP and len(w) > 2}


def evidence_items(case: Case, turns: list[dict], chart: list[dict]) -> list[dict]:
    """Everything the student could legitimately know: disclosed facts and the chart."""
    items: dict[str, dict] = {}
    for t in turns:
        for d in t["engine"].get("disclosures", []):
            f = case.fact(d["fact_id"])
            if f:
                items[f.id] = {"id": f.id, "kind": "fact", "text": f.text, "key": f.safety or any(f.id in o.expected_discoveries for o in case.objectives)}
    for c in chart:
        ref = f"{c['kind']}:{c['ref']}"
        text = f"{c['label']}: {c['value']}" if c.get("value") else c["label"]
        items.setdefault(ref, {"id": ref, "kind": c["kind"], "text": text, "key": bool(c.get("flag")) or c["kind"] == "exam"})
    return list(items.values())


def _note_text(note: dict[str, str]) -> str:
    return "\n".join(f"{k}: {v}" for k, v in note.items() if v and v.strip())


def rule_based_check(note: dict[str, str], items: list[dict], case: Case) -> dict:
    text = _note_text(note)
    backing = " ".join(i["text"] for i in items) + f" {case.profile.age}"
    allowed_numbers = numbers_in(backing)
    unsupported = [
        {"statement": s.strip(), "reason": "contains a number that did not come up in the encounter"}
        for s in re.split(r"(?<=[.;\n])\s+", text)
        if s.strip() and any(n not in allowed_numbers for n in numbers_in(s))
    ]
    note_tokens = _tokens(text)
    missing = []
    for i in items:
        if not i["key"]:
            continue
        toks = _tokens(i["text"])
        if toks and len(toks & note_tokens) / len(toks) < 0.34:
            missing.append({"id": i["id"], "text": i["text"]})
    return {"unsupported": unsupported, "missing": missing[:8], "supported": [], "method": "rule-based"}


def llm_check(note: dict[str, str], items: list[dict], case: Case) -> tuple[dict, dict]:
    evidence = "\n".join(f"[{i['id']}] {i['text']}" for i in items)
    user = (
        f"TEMPLATE: {case.documentation_template}\nPATIENT: {case.profile.name}, {case.profile.age}\n\n"
        f"EVIDENCE (the only things the student learned):\n{evidence}\n\nSTUDENT NOTE:\n{_note_text(note)}"
    )
    data, call = complete_json(purpose="documentation", prompt_name="documentation", user=user, strong=True, max_tokens=2000)
    if not isinstance(data, dict):
        raise LLMUnavailable("documentation output was not an object")
    ids = {i["id"] for i in items}
    note_norm = re.sub(r"\s+", " ", _note_text(note).lower())
    out = {"unsupported": [], "missing": [], "supported": [], "method": "llm"}
    for s in data.get("statements", []):
        stmt = str(s.get("statement", "")).strip()
        if not stmt or re.sub(r"\s+", " ", stmt.lower()) not in note_norm:
            continue  # must quote the note itself
        cites = [c for c in s.get("supported_by", []) if c in ids]
        is_inference = s.get("type") == "assessment_or_plan"
        if cites or is_inference:
            out["supported"].append({"statement": stmt, "supported_by": cites, "assessment_or_plan": is_inference})
        else:
            out["unsupported"].append({"statement": stmt, "reason": str(s.get("reason", "not found in the encounter"))})
    key_ids = {i["id"] for i in items if i["key"]}
    by_id = {i["id"]: i for i in items}
    for m in data.get("missing", []):
        mid = m.get("id") if isinstance(m, dict) else m
        if mid in key_ids:
            out["missing"].append({"id": mid, "text": by_id[mid]["text"]})
    return out, call.to_dict()


def check_documentation(case: Case, note: dict[str, str] | None, turns: list[dict], chart: list[dict], use_llm: bool) -> tuple[dict | None, list[dict]]:
    if not note or not any(v and v.strip() for v in note.values()):
        return None, []
    items = evidence_items(case, turns, chart)
    calls: list[dict] = []
    if use_llm:
        try:
            result, call = llm_check(note, items, case)
            calls.append(call)
            # Numbers are checked by code even on the LLM path.
            rb = rule_based_check(note, items, case)
            seen = {u["statement"] for u in result["unsupported"]}
            result["unsupported"] += [u for u in rb["unsupported"] if u["statement"] not in seen]
            return result, calls
        except LLMUnavailable:
            pass
    return rule_based_check(note, items, case), calls
