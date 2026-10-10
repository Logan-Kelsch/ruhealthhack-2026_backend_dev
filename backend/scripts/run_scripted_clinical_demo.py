"""Execute all actual demo HTTP handlers against isolated SQLite, without cloud calls."""
from __future__ import annotations
import argparse
import json
import tempfile
import time
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db import Base, get_session
from app.main import create_app
from app.models import tables  # noqa: F401
from app.settings import get_settings


def run(output: Path | None = None, scenario: int | None = None) -> dict:
    settings = get_settings()
    previous = settings.scripted_demo_enabled
    settings.scripted_demo_enabled = True
    try:
        with tempfile.TemporaryDirectory(prefix="rounds-scripted-api-") as directory:
            engine = create_engine(f"sqlite:///{directory}/demo.sqlite",connect_args={"check_same_thread":False})
            Base.metadata.create_all(engine)
            app = create_app()
            def session():
                with Session(engine,expire_on_commit=False) as db: yield db
            app.dependency_overrides[get_session]=session
            runs, calls = [], []
            with TestClient(app) as client:
                def request(method,path,body=None):
                    start=time.perf_counter()
                    response=client.request(method,path,**({"json":body} if body is not None else {}))
                    calls.append({"method":method,"path":path,"status":response.status_code,
                                  "http_handler_ms":round((time.perf_counter()-start)*1000,3)})
                    response.raise_for_status()
                    return response.json()
                catalog=request("GET","/api/demo/educator/scenarios")
                for case in catalog:
                    if scenario is not None and case["scenario_id"]!=scenario: continue
                    prep=request("POST","/api/demo/educator/preparations",{"scenario_id":case["scenario_id"],"description":case["example_description"]})
                    started=request("POST","/api/demo/sessions",{"preparation_id":prep["preparation_id"],"accept_fixed_script":True})
                    sid=started["session_id"]
                    for n,text in enumerate(case["suggested_student_sequence"],1):
                        request("POST",f"/api/demo/sessions/{sid}/turns",{"expected_step":n,"request_id":f"rehearsal_{n}","text":text})
                    ended=request("POST",f"/api/demo/sessions/{sid}/end")
                    debrief=request("GET",f"/api/demo/sessions/{sid}/debrief")
                    assert debrief["follows_rehearsal_script"] and debrief["assessment_status"]=="not_scored"
                    runs.append({"scenario_id":case["scenario_id"],"preparation":prep,"session":ended,"debrief":debrief})
            engine.dispose()
        report={"schema_version":"scripted_demo_report_v1","execution":"actual_http_handlers_isolated_sqlite",
                "patient_generation":"authored_static_playback","model_calls":0,
                "clinical_review":"pending","student_assessment":"not_scored",
                "cases":len(runs),"replies":sum(len(r["session"]["transcript"]) for r in runs),
                "http_requests":len(calls),"runs":runs,"calls":calls,
                "limitations":["Delay values are presentation assumptions; handlers do not sleep.",
                    "Input consumes sequence position without semantic classification.",
                    "Cases are authored synthetic examples, not clinically approved cases.",
                    "No live LLM, voice, frontend screen, or human-learning outcome is exercised."]}
        if output:
            output.parent.mkdir(parents=True,exist_ok=True)
            output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
        return report
    finally:
        settings.scripted_demo_enabled=previous


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--scenario',type=int,choices=[1,2,3])
    args=parser.parse_args()
    report=run(args.output,args.scenario)
    print(json.dumps({k:report[k] for k in ('execution','cases','replies','http_requests','model_calls','clinical_review','student_assessment')},indent=2))

if __name__=='__main__': main()
