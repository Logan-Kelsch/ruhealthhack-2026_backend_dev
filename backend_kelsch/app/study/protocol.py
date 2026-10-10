"""Version-locked, blinded packet preparation for Notebook 06.

No observed learner transcript or completed review is bundled with the repository.
"""
from __future__ import annotations

import gzip
from hashlib import sha256
import json
from pathlib import Path

from app.schemas.case import Case
from backend_kelsch.app.action_data.preparation import grouped_split
from backend_kelsch.app.debrief_probe.evaluation import CASES, ROOT

PROTOCOL = ROOT / "backend_kelsch/app/data/study_protocol_v1.json"
VOCAB = ROOT / "backend_kelsch/app/data/action_annotation_vocab.json"
REPORTS = ("dataset_audit.json", "action_data.json", "patient_environment.json",
           "grounding_eval.json", "debrief_eval.json")


def digest(data: object) -> str:
    return sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def lock_manifest() -> dict:
    paths = [PROTOCOL, VOCAB, ROOT / "backend/app/data/rubric_shp_v1.json"]
    paths += [ROOT / p for p in (
        "backend_kelsch/app/study/protocol.py", "backend_kelsch/app/study/review.py",
        "backend_kelsch/app/study/analysis.py", "backend_kelsch/scripts/eval_study.py",
        "backend_kelsch/app/action_data/preparation.py",
        "backend/app/schemas/case.py", "backend/app/schemas/encounter.py",
        "backend/app/feedback/debrief.py", "backend/app/feedback/decisions.py",
        "backend/app/feedback/documentation.py", "backend/app/feedback/rubric.py",
        "backend/app/encounter/visit.py")]
    paths += [ROOT / "cases" / f"{cid}.json" for cid in CASES]
    paths += [ROOT / "backend_kelsch/docs/validation" / name for name in REPORTS]
    paths += [ROOT / "backend_kelsch/docs/validation/grounding_traces.json.gz",
              ROOT / "backend_kelsch/docs/validation/debrief_traces.json.gz"]
    sources = {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in paths}
    protocol = json.loads(PROTOCOL.read_text())
    return {"protocol_id": protocol["protocol_id"], "protocol_status": protocol["status"],
            "source_sha256": sources, "lock_id": digest(sources)}


def load_previous() -> tuple[dict, list[dict]]:
    base = ROOT / "backend_kelsch/docs/validation"
    with gzip.open(base / "grounding_traces.json.gz", "rt") as f:
        grounding = json.load(f)
    with gzip.open(base / "debrief_traces.json.gz", "rt") as f:
        debrief = json.load(f)
    return grounding, debrief


def validate_corpus(corpus: dict, lock: dict) -> list[dict]:
    """Require independently supplied consent/provenance before action packets."""
    if not corpus:
        return []
    if (corpus.get("protocol_lock") != lock["lock_id"] or
        corpus.get("origin") != "consented_synthetic_case_encounters" or
        corpus.get("contains_real_patient_data") is not False or
        corpus.get("deidentified") is not True or
        corpus.get("consent_and_ethics_verified") is not True or
        not corpus.get("consent_policy_ref") or not corpus.get("ethics_determination_ref")):
        raise ValueError("external corpus requires protocol lock, documented consent/ethics and synthetic-only deidentification")
    conversations = corpus.get("conversations")
    if not isinstance(conversations, list) or not conversations:
        raise ValueError("nonempty reviewed conversation corpus required")
    seen_conv = set()
    case_hashes = {cid: lock["source_sha256"][f"cases/{cid}.json"] for cid in CASES}
    for conv in conversations:
        cid = conv.get("conversation_id")
        if not cid or ":" in cid or cid in seen_conv or not conv.get("patient_id") or not conv.get("family_id"):
            raise ValueError("unique conversation and patient/family IDs required")
        seen_conv.add(cid)
        if (not conv.get("learner_id") or not conv.get("assignment_ref") or
            conv.get("arm") not in {"feedback", "standard"} or
            conv.get("phase") not in {"baseline", "followup"}):
            raise ValueError("pseudonymous learner, assignment and phase required")
        if conv.get("case_id") not in CASES or conv.get("case_sha256") != case_hashes[conv["case_id"]] or conv.get("case_version") != Case.model_validate_json((ROOT / "cases" / f"{conv['case_id']}.json").read_text()).version:
            raise ValueError("case hash/version mismatch")
        if not conv.get("consent_ref"):
            raise ValueError("transcript source and consent reference required")
        ids = set()
        for turn in conv.get("turns", []):
            if (not turn.get("turn_id") or ":" in turn["turn_id"] or turn["turn_id"] in ids or
                turn.get("speaker") not in {"student", "patient"} or
                not isinstance(turn.get("text"), str) or not turn["text"].strip()):
                raise ValueError("invalid conversation turn")
            ids.add(turn["turn_id"])
        if not ids or not any(t["speaker"] == "student" for t in conv["turns"]):
            raise ValueError("student turn required")
        if conv.get("source_sha256") != digest(conv["turns"]):
            raise ValueError("transcript source digest mismatch")
    by_learner = {}
    for conv in conversations:
        by_learner.setdefault(conv["learner_id"], set()).add(conv["arm"])
    if any(len(arms) != 1 for arms in by_learner.values()):
        raise ValueError("learner cannot switch assigned arms")
    return conversations


def make_packets(lock: dict, corpus: dict | None = None) -> tuple[list[dict], dict]:
    """Reviewer view omits actual disclosures, verdicts, provisional scores and levels."""
    grounding, debrief = load_previous()
    conversations = validate_corpus(corpus, lock) if corpus else []
    packets = []
    mapping = {}

    def add(kind: str, key: str, case_id: str, context: dict, source_sha256: str, version: int):
        if (case_id not in CASES or source_sha256 != lock["source_sha256"][f"cases/{case_id}.json"] or
            version != Case.model_validate_json((ROOT / "cases" / f"{case_id}.json").read_text()).version):
            raise ValueError("packet case differs from locked authored source")
        pid = sha256(f"{lock['lock_id']}|{kind}|{key}".encode()).hexdigest()[:24]
        if pid in mapping:
            raise ValueError("packet ID collision")
        packet = {"packet_id": pid, "kind": kind, "protocol_lock": lock["lock_id"],
                  "case_id": case_id, "case_sha256": source_sha256,
                  "case_version": version, "context": context,
                  "expected": None, "review_status": "pending"}
        packets.append(packet)
        mapping[pid] = {"kind": kind, "key": key, "case_id": case_id,
                        "case_sha256": source_sha256, "case_version": version}
    for run in grounding["runs"]:
        prior_student = []
        for turn in run["turns"]:
            add("release", f"{run['script_id']}:{turn['turn']}", run["case_id"],
                {"student_utterance": turn["utterance"], "prior_student_utterances": prior_student.copy(),
                 "difficulty_vector": run["preset"], "case_path": run["case_source"]["path"]},
                run["case_source"]["sha256"], run["case_version"])
            prior_student.append(turn["utterance"])
    for item in grounding["challenges"]:
        add("semantic", item["challenge_id"], item["case_id"],
            {"reply": item["reply"], "student_utterance": item["student_utterance"],
             "available_fact_ids": item["allowed_fact_ids"],
             "previously_disclosed_fact_ids": item["previously_disclosed"],
             "case_path": item["case_source"]["path"]},
            item["case_source"]["sha256"], item["case_version"])
    rubric = json.loads((ROOT / "backend/app/data/rubric_shp_v1.json").read_text())
    for record in debrief:
        transcript = [{"turn": t["idx"], "student": t["student_text"], "patient": t["reply_text"]} for t in record["transcript"]]
        for idx, claim in enumerate(record["claims"]):
            add("claim", f"{record['case_id']}:{record['scenario']}:{idx}", record["case_id"],
                {"claim": claim, "transcript": transcript, "case_path": record["case_source"]["path"]},
                record["case_source"]["sha256"], record["case_version"])
        for domain in rubric["domains"]:
            add("domain", f"{record['case_id']}:{record['scenario']}:{domain['id']}", record["case_id"],
                {"domain_id": domain["id"], "domain_key": domain["key"],
                 "rubric_source": "backend/app/data/rubric_shp_v1.json",
                 "transcript": transcript, "case_path": record["case_source"]["path"]},
                record["case_source"]["sha256"], record["case_version"])
    for conv in conversations:
        for turn in conv["turns"]:
            if turn["speaker"] != "student":
                continue
            add("action", f"{conv['conversation_id']}:{turn['turn_id']}", conv["case_id"],
                {"turn_id": turn["turn_id"], "speaker": "student", "text": turn["text"],
                 "namespace": "student_skill"}, conv["case_sha256"], conv["case_version"])
        transcript = [{"turn": i + 1, t["speaker"]: t["text"]} for i, t in enumerate(conv["turns"])]
        # Shared rubric scorer accepts a seven-domain case; the observation
        # is evaluated only after independent faculty scores are imported.
        for domain in rubric["domains"]:
            add("domain", f"observed:{conv['conversation_id']}:{domain['id']}", conv["case_id"],
                {"domain_id": domain["id"], "domain_key": domain["key"],
                 "rubric_source": "backend/app/data/rubric_shp_v1.json",
                 "transcript": transcript, "case_path": f"cases/{conv['case_id']}.json",
                 "observed_conversation": True}, conv["case_sha256"], conv["case_version"])
    # Stable blinded order; source-key mapping never appears in reviewer packets.
    packets.sort(key=lambda p: p["packet_id"])
    return packets, mapping


def split_audit(conversations: list[dict]) -> dict:
    if not conversations:
        return {"status": "NOT EVALUABLE", "conversations": 0, "patients": 0,
                "assignments": None, "cross_split_links": None}
    splits = grouped_split(conversations)
    links: dict[tuple[str, str], set[str]] = {}
    for conv in conversations:
        for key in (("patient", conv["patient_id"]), ("family", conv["family_id"])):
            links.setdefault(key, set()).add(splits[conv["conversation_id"]])
        for turn in conv["turns"]:
            links.setdefault(("text", digest(" ".join(turn["text"].lower().split()))), set()).add(splits[conv["conversation_id"]])
    leaks = [str(k) for k, v in links.items() if len(v) > 1]
    if leaks:
        raise ValueError("patient/family/duplicate text crosses split")
    return {"status": "PASS", "conversations": len(conversations),
            "patients": len({c["patient_id"] for c in conversations}),
            "assignments": splits, "cross_split_links": 0}
