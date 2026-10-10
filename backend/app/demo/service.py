"""Fixed dialogue playback with pinned snapshots and atomic, idempotent turns."""
from __future__ import annotations
import copy
import hashlib
import json
import re
from uuid import uuid4
from sqlalchemy import update
from sqlalchemy.orm import Session
from app import catalogs
from app.models.tables import DemoSessionRow
from app.schemas.demo import MetadataExtraction, SourceSpan, ScriptFixture
from app.services import Conflict, NotFound
from app.settings import BACKEND_DIR

FIXTURE = BACKEND_DIR / "app/data/scripted_clinical_demo_v1.json"
SAFETY_NOTICE = "This completed encounter included time-critical findings. Review when supervising-clinician escalation was needed and how you communicated the urgency."

def scenarios() -> list[dict]:
    data = ScriptFixture.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    return data.model_dump()["cases"]

def educator_scenarios() -> list[dict]:
    return [{"scenario_id":c["scenario_id"], "fixture_version":c["fixture_version"],
             "title":c["title"], "patient":c["patient"], "goal":c["educator"]["goal"],
             "example_description":c["educator"]["example_description"],
             "suggested_student_sequence":[t["suggested_student_text"] for t in c["turns"]],
             "sources":c["educator"]["sources"], "clinical_review_status":"pending"} for c in scenarios()]

# Categories preserve verbatim text, including negations. No diagnosis is inferred.
CATEGORIES = {
    "presenting_concern": r"fever|cough|breath|diarrhea|nausea|sweat|fatigue|chest|symptom",
    "history": r"hypertension|panic|anxiety|previous|history",
    "exposure": r"convention|philadelphia|philly|hotel|travel",
    "medications": r"takes|lisinopril|sertraline|medicin|medication",
    "allergies": r"allerg",
    "tobacco_and_readiness": r"smok|quit|willing|pack|tobacco",
    "findings": r"ecg|electrocardiogram|st elevation|radiograph",
    "learning_goal": r"goal|objective",
}

def extract_metadata(text: str, patient: dict) -> dict:
    categorized, unmatched = [], []
    for m in re.finditer(r"[^.!?]+(?:[.!?]|$)", text):
        start, end = m.start(), m.end()
        while start < end and text[start].isspace(): start += 1
        if start == end: continue
        chunk = text[start:end]
        found = [key for key, pat in CATEGORIES.items() if re.search(pat, chunk, re.I)]
        if re.search(r"\b\d{1,3}[ -]year[ -]old\b|\b(man|woman|male|female)\b", chunk, re.I):
            found.append("demographics")
        spans = [SourceSpan(category=key, text=chunk, start=start, end=end) for key in found]
        categorized.extend(spans)
        if not spans: unmatched.append(SourceSpan(category="unclassified", text=chunk, start=start, end=end))
    age = re.search(r"\b(\d{1,3})[ -]year[ -]old\b", text, re.I)
    sex = re.search(r"\b(woman|female|man|male)\b", text, re.I)
    name_match = re.search(re.escape(patient["name"]), text, re.I)
    return MetadataExtraction(description=text, name=name_match.group() if name_match else None,
        age_years=int(age.group(1)) if age else None,
        sex=("female" if sex.group().lower() in {"female","woman"} else "male") if sex else None,
        categorized_spans=categorized, unmatched_spans=unmatched).model_dump()

def prepare(db: Session, scenario_id: int, description: str) -> dict:
    if not description.strip(): raise Conflict("Educator description cannot be blank")
    case = next((c for c in scenarios() if c["scenario_id"] == scenario_id), None)
    if case is None: raise NotFound("Demo scenario not found")
    extraction = extract_metadata(description, case["patient"])
    warnings = ["The fixed fixture defines the patient and replies. Extracted text is retained for educator review and does not change the dialogue.",
                "This is rule-based structuring and scripted playback; no LLM has been called."]
    for key in ("age_years","sex"):
        if extraction[key] is not None and extraction[key] != case["patient"][key]:
            warnings.append(f"Description {key} differs from the fixed fixture; the fixture value will be used.")
    if extraction["name"] is None: warnings.append("The fixed patient name was not found in the description.")
    digest = hashlib.sha256(json.dumps(case,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    sid = str(uuid4())
    output = {"preparation_id":sid, "scenario_id":scenario_id,"fixture_version":case["fixture_version"],
              "fixture_sha256":digest,"patient":case["patient"],"extracted_metadata":extraction,
              "warnings":warnings,"execution_mode":"scripted_playback","clinical_review_status":"pending",
              "simulated_delay_ms":1600,"actual_model_calls":0}
    db.add(DemoSessionRow(id=sid, status="educator", revision=0,
                         payload={"case":case,"preparation":output,"turns":[],"requests":{}}))
    db.commit()
    return output

def load(db: Session, sid: str) -> DemoSessionRow:
    row = db.get(DemoSessionRow, sid)
    if row is None: raise NotFound("Demo session not found")
    return row

def save(db: Session, row: DemoSessionRow, payload: dict, status: str) -> None:
    # Prevent two tabs, retries, or workers from consuming the same sequence position.
    result = db.execute(update(DemoSessionRow).where(DemoSessionRow.id==row.id,
        DemoSessionRow.revision==row.revision).values(payload=payload,status=status,revision=row.revision+1),
        execution_options={"synchronize_session":False})
    if result.rowcount != 1:
        db.rollback()
        raise Conflict("Demo changed concurrently; reload and retry with the same request_id")
    db.commit()
    db.expire_all()

def start(db: Session, sid: str) -> dict:
    row = load(db,sid)
    if row.status == "educator": save(db,row,row.payload,"student")
    return view(db,sid)

def _chart(item: dict) -> dict:
    return {k:v for k,v in item.items() if k!="release_step"}

def view(db: Session, sid: str) -> dict:
    row = load(db,sid)
    if row.status == "educator": raise Conflict("Start student mode before reading the session")
    p, case = row.payload, row.payload["case"]
    n = len(p["turns"])
    return {"session_id":sid,"scenario_id":case["scenario_id"],
            "fixture_sha256":p["preparation"]["fixture_sha256"],"status":row.status,
            "patient_name":case["patient"]["name"],"age_years":case["patient"]["age_years"],
            "presenting_concern":case["patient"]["presenting_concern"],
            "next_step":n+1 if row.status=="student" else None,"total_steps":len(case["turns"]),
            "transcript":p["turns"],"chart":[_chart(c) for c in case["chart"] if c["release_step"]<=n],
            "execution_mode":"scripted_playback","input_handling":"sequence_position_only","actual_model_calls":0}

def turn(db: Session, sid: str, expected_step: int, request_id: str, text: str) -> dict:
    if not text.strip(): raise Conflict("Student text cannot be blank")
    row = load(db,sid)
    p = copy.deepcopy(row.payload)
    request = {"expected_step":expected_step,"text":text}
    if request_id in p["requests"]:
        saved = p["requests"][request_id]
        if saved["request"] != request: raise Conflict("request_id was already used with a different payload")
        # Old sessions may have saved an inline coaching notice before this boundary.
        return {**saved["response"], "safety_notice": None}
    if row.status != "student": raise Conflict("Demo session is not accepting turns")
    case, step = p["case"], len(p["turns"])+1
    if expected_step != step: raise Conflict(f"Expected step {step}; reload the session")
    scripted = case["turns"][step-1]
    t = {"step":step,"student_text":text,"patient_text":scripted["patient_text"],
         "fact_ids":scripted["fact_ids"],"simulated_delay_ms":scripted["simulated_delay_ms"]}
    p["turns"].append(t)
    chart = [_chart(c) for c in case["chart"] if c["release_step"]==step]
    complete = step==len(case["turns"])
    output = {"session_id":sid,"turn":t,"chart_added":chart,
              # Keep the existing response contract; teaching feedback is post-encounter only.
              "safety_notice":None,
              "next_step":None if complete else step+1,"complete":complete,
              "execution_mode":"scripted_playback","actual_model_calls":0}
    p["requests"][request_id] = {"request":request,"response":output}
    save(db,row,p,"ready_to_end" if complete else "student")
    return output

def end(db: Session, sid: str) -> dict:
    row = load(db,sid)
    if row.status=="educator": raise Conflict("Start student mode before ending")
    if row.status!="ended": save(db,row,row.payload,"ended")
    return view(db,sid)

def debrief(db: Session, sid: str) -> dict:
    row = load(db,sid)
    if row.status!="ended": raise Conflict("End the demo session before requesting debrief")
    p, case = row.payload, row.payload["case"]
    if len(p["turns"]) != len(case["turns"]):
        raise Conflict("Complete the entire dialogue before requesting debrief")
    domains = {d["id"]:d["name"] for d in catalogs.rubric()["domains"]}
    match = all(t["student_text"].strip()==s["suggested_student_text"]
                for t,s in zip(p["turns"],case["turns"]))
    # Stored sessions from earlier versions keep their questions, without per-turn delivery.
    authored = case["debrief"]
    questions = authored["questions"] if isinstance(authored, dict) else authored
    reflections = [{"id":q["id"], "domain_id":q["domain_id"],
                    "domain_name":domains[q["domain_id"]],
                    "question":q["question"] if match else
                    "Review the completed dialogue. How would you approach this domain differently in a future encounter?"}
                   for q in questions]
    return {"session_id":sid, "delivery":"after_dialogue", "reflections":reflections,
            "transcript":p["turns"], "completed_steps":len(p["turns"]),
            "total_steps":len(case["turns"]),"follows_rehearsal_script":match,
            "method":"scripted_guided_reflection","assessment_status":"not_scored",
            "interpretation":"Review the entire completed dialogue using these authored reflection questions. They are not a judgment that you made an error. Replies depend on sequence position, not interpretation of your input. No rubric score or learning outcome is assigned.",
            "safety_notice":SAFETY_NOTICE if any(c["urgent"] for c in case["chart"]) else None}
