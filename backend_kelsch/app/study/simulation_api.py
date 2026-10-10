"""Run actual HTTP contracts in a disposable local database, without external services."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from app import db as dbmod, services
from app.db import Base
from app.schemas.case import Case
from app.settings import get_settings
from backend_kelsch.app.debrief_probe.evaluation import ROOT
from backend_kelsch.app.study.workflow import save


def api_rehearsal(directory: Path) -> dict:
    settings = {'LLM_ENABLED': 'false', 'NLM_LOOKUP_ENABLED': 'false', 'ELEVENLABS_API_KEY': ''}
    before = {k: os.environ.get(k) for k in settings}
    old_engine, old_session = dbmod._engine, dbmod._SessionLocal
    engine = None
    interactions = []
    try:
        os.environ.update(settings)
        get_settings.cache_clear()
        engine = dbmod.init_engine('sqlite:///' + str(directory / 'simulation_api.sqlite'))
        Base.metadata.create_all(engine)
        cases = {cid: Case.model_validate_json((ROOT / 'cases' / (cid + '.json')).read_text())
                 for cid in ('walter_greene', 'alina_reyes', 'eli_brooks')}
        with next(dbmod.get_session()) as session:
            for case in cases.values():
                services.upsert_golden(session, case)
        from app.main import create_app
        with TestClient(create_app()) as client:
            def request(method, path, *, expected=200, body=None):
                response = client.request(method, path, json=body)
                interactions.append({'method': method, 'path': path, 'status': response.status_code})
                if response.status_code != expected:
                    raise RuntimeError(f'HTTP rehearsal failed: {method} {path} returned {response.status_code}, expected {expected}')
                return response.json() if response.content else None
            request('GET', '/api/health')
            cfg = request('GET', '/api/config')
            if cfg['llm'] or cfg['tts']:
                raise RuntimeError('simulation rehearsal must disable paid integrations')
            authored = cases['walter_greene']
            draft = request('POST', '/api/studio/drafts', expected=201,
                body={'description': f'A {authored.profile.age}-year-old man in a synthetic simulation-only nutrition encounter.'})
            cid = draft['case']['case_id']
            request('POST', f'/api/studio/cases/{cid}/publish', expected=409)
            chief = next(f for f in authored.facts if f.tier == 'initial')
            for gap, text in [('name', 'Simulation patient'), ('student_role', authored.briefing.student_role),
                ('reason_for_visit', authored.briefing.reason_for_visit), ('goal', authored.briefing.goal),
                ('chief_complaint', chief.say or chief.text), ('objectives', authored.objectives[0].text)]:
                draft = request('POST', f'/api/studio/cases/{cid}/intake', body={'gap_id': gap, 'text': text})
            draft = request('POST', f'/api/studio/cases/{cid}/autofill', body={'panels': ['bmp'], 'vitals': True})
            doc = draft['case']
            # The existing authoring schema says faculty by default. Replace that source
            # in this disposable simulation before publication; no person is impersonated.
            doc['created_by'] = 'simulation_fixture'
            doc['description'] += ' Intake was supplied by code from cases/walter_greene.json; no human approval.'
            for fact in doc['facts']:
                fact['source'] = {'kind': 'rule', 'ref': 'simulation_fixture:copied_authored_walter_content'}
            request('PUT', f'/api/studio/cases/{cid}', body=doc)
            for group in ('facts', 'vitals', 'labs', 'objectives'):
                request('POST', f'/api/studio/cases/{cid}/approve', body={'group': group})
            published = request('POST', f'/api/studio/cases/{cid}/publish')
            new_enc = request('POST', '/api/encounters', expected=201, body={'case_id': cid, 'student_name': 'Synthetic student'})
            eid = new_enc['encounter_id']
            reply = request('POST', f'/api/encounters/{eid}/utterances', body={'text': 'What brings you in today?'})
            request('POST', f'/api/encounters/{eid}/end')
            feedback = request('POST', f'/api/encounters/{eid}/documentation', body={'fields': {'subjective': chief.say or chief.text}})
            hero = request('POST', '/api/encounters', expected=201, body={'case_id': 'walter_greene', 'student_name': 'Synthetic student'})
            hero_id = hero['encounter_id']
            request('POST', f'/api/encounters/{hero_id}/utterances', body={'text': 'Do you take anything over the counter for pain?'})
            request('POST', f'/api/encounters/{hero_id}/end')
            request('POST', f'/api/encounters/{hero_id}/utterances', expected=409, body={'text': 'hello'})
            hero_feedback = request('POST', f'/api/encounters/{hero_id}/documentation', body={'fields': {'subjective': 'Simulation note.'}})
            followup = request('POST', '/api/encounters', expected=201, body={'case_id': 'walter_greene', 'previous_encounter_id': hero_id})
            request('POST', '/api/tts', expected=204, body={'text': 'Simulation only.'})
            preview = request('POST', '/api/studio/cases/walter_greene/preview', body={'level': 'expert'})
            save(directory / 'api_interactions.json', interactions)
            if published['status'] != 'published' or not reply['reply_text'] or not feedback['transcript'] or not hero_feedback['decision_path']['taken'] or followup['visit_id'] != 'v2' or preview['grounding']['replies_failing_audit']:
                raise RuntimeError('incomplete Studio/encounter/debrief/followup rehearsal')
            return {'mode': 'OFFLINE HTTP EXECUTED', 'database': 'isolated SQLite', 'status': 'PASS',
                    'requests': len(interactions), 'studio_created_and_published': True,
                    'new_patient_encounter_and_debrief': True, 'authored_followup_visit': followup['visit_id'],
                    'golden_preview_replies_failing_mechanical_audit': preview['grounding']['replies_failing_audit'],
                    'authoring_approval_interpretation': 'Code set schema authoring statuses inside disposable simulation; no clinical approval.',
                    'bedrock': 'NOT RUN', 'voice': 'MOCKED/UNAVAILABLE: text entry and 204 TTS fallback only',
                    'voice_first_audio_latency_ms': None, 'cloud_database': 'NOT RUN', 'cost_usd': None}
    finally:
        if engine is not None:
            engine.dispose()
        dbmod._engine, dbmod._SessionLocal = old_engine, old_session
        for key, value in before.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()
