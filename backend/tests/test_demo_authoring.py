"""Review edits must reach playback without losing citations or replacing other cases."""
import json
import os
import subprocess
import sys

import pytest

from app.demo.authoring import FIXTURE, REVIEW_DIR, export_scripts, import_scripts
from app.demo import service
from app.schemas.demo import ScriptFixture


@pytest.fixture
def files(tmp_path):
    fixture = tmp_path / "runtime.json"
    fixture.write_bytes(FIXTURE.read_bytes())
    reviews = export_scripts(tmp_path / "review", fixture)
    return fixture, reviews


def edit(path, mutate):
    data = json.loads(path.read_text())
    mutate(data)
    path.write_text(json.dumps(data))


def test_checked_in_reviews_are_lossless_and_noop(files):
    fixture, reviews = files
    for path in reviews:
        assert path.read_bytes() == (REVIEW_DIR / path.name).read_bytes()
    before = fixture.read_bytes()
    report = import_scripts(reviews, fixture)
    assert report["changed_scenarios"] == [] and not report["written"]
    assert fixture.read_bytes() == before


def test_edit_regenerates_sources_delays_version_and_reaches_playback(files, monkeypatch):
    fixture, reviews = files
    previous = json.loads(fixture.read_text())
    response = "I am worried and would like you to listen."
    edit(reviews[1], lambda d: d["dialogue"][0].update(patient=response))
    original = fixture.read_bytes()
    check = import_scripts([reviews[1]], fixture, check=True)
    assert check["changed_scenarios"] == [2] and not check["written"]
    assert fixture.read_bytes() == original
    assert import_scripts([reviews[1]], fixture)["written"]
    monkeypatch.setattr(service, "FIXTURE", fixture)
    cases = service.scenarios()
    assert cases[0] == previous["cases"][0] and cases[2] == previous["cases"][2]
    case = cases[1]
    assert case["fixture_version"] == previous["cases"][1]["fixture_version"] + 1
    assert case["turns"][0]["patient_text"] == response
    assert case["facts"]["2.reply.1"]["text"] == response
    assert case["turns"][0]["simulated_delay_ms"] == min(2400, 850 + 32 * len(response.split()))
    assert not import_scripts([reviews[1]], fixture)["written"]


def test_moving_findings_and_adding_turn_updates_release_and_sources(files):
    fixture, reviews = files
    def modify(data):
        data["dialogue"][3]["chart"] = data["dialogue"][2]["chart"]
        data["dialogue"][2]["chart"] = []
        data["dialogue"].append({"student": "Anything else?", "patient": "Thank you.", "chart": []})
        data["debrief"][0]["evidence_turn"] = 9
    edit(reviews[2], modify)
    import_scripts([reviews[2]], fixture)
    case = ScriptFixture.model_validate_json(fixture.read_text()).cases[2]
    assert len(case.turns) == 9
    assert case.turns[2].release_chart_ids == []
    assert case.turns[3].release_chart_ids == ["cardiac.vitals", "cardiac.ecg"]
    assert all(c.release_step == 4 for c in case.chart)
    assert case.facts["3.reply.9"].text == "Thank you."
    assert case.debrief[0].anchor_step == 9


@pytest.mark.parametrize("mutation", [
    lambda d: d.update(typo="silently dropped?"),
    lambda d: d["debrief"][0].update(evidence_turn=999),
    lambda d: d.update(debrief_delivery="during_encounter"),
    lambda d: d["debrief"][0].update(rubric_domain="Invented grading"),
    lambda d: d["dialogue"][0].update(patient="   "),
    lambda d: d["dialogue"][0].update(student="x" * 2001),
    lambda d: d["dialogue"][2]["chart"][0].update(urgent="false"),
    lambda d: d["dialogue"][2]["chart"][1].update(id="cardiac.vitals"),
])
def test_invalid_batch_never_partially_writes(files, mutation):
    fixture, reviews = files
    before = fixture.read_bytes()
    edit(reviews[0], lambda d: d.update(title="A valid edit"))
    edit(reviews[2], mutation)
    with pytest.raises(ValueError):
        import_scripts(reviews, fixture)
    assert fixture.read_bytes() == before


def test_duplicate_scenario_and_duplicate_keys_rejected(files):
    fixture, reviews = files
    before = fixture.read_bytes()
    with pytest.raises(ValueError, match="more than once"):
        import_scripts([reviews[0], reviews[0]], fixture)
    reviews[0].write_text('{"scenario_id":1,"scenario_id":2}')
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        import_scripts([reviews[0]], fixture)
    assert fixture.read_bytes() == before


def test_cli_validation_and_error_exit(files):
    _, reviews = files
    env = {**os.environ, "PYTHONPATH": str(FIXTURE.parents[2])}
    args = [sys.executable, "-m", "scripts.update_scripted_clinical_demo", "--check"]
    valid = subprocess.run([*args, *map(str, reviews)], env=env, capture_output=True, text=True)
    assert valid.returncode == 0 and json.loads(valid.stdout)["mode"] == "check"
    reviews[0].write_text("invalid JSON")
    invalid = subprocess.run([*args, str(reviews[0])], env=env, capture_output=True, text=True)
    assert invalid.returncode == 2 and str(reviews[0]) in invalid.stderr


def test_failed_atomic_replace_preserves_runtime_and_cleans_temp(files, monkeypatch):
    fixture, reviews = files
    before = fixture.read_bytes()
    edit(reviews[0], lambda d: d.update(title="Edited title"))
    def fail(*args):
        raise OSError("Simulated replacement failure")
    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError):
        import_scripts([reviews[0]], fixture)
    assert fixture.read_bytes() == before
    assert list(fixture.parent.glob(".runtime.json.*")) == []


def test_legacy_review_files_still_import_and_export_as_post_encounter(files, tmp_path):
    fixture, reviews = files
    for path in reviews:
        data = json.loads(path.read_text())
        data['format'] = 'clinical_script_review_v1'
        del data['debrief_delivery']
        for question in data['debrief']:
            question['after_turn'] = question.pop('evidence_turn')
        path.write_text(json.dumps(data))
    assert not import_scripts(reviews, fixture)['written']
    exported = export_scripts(tmp_path / 'fresh', fixture)
    for path in exported:
        data = json.loads(path.read_text())
        assert data['format'] == 'clinical_script_review_v2'
        assert data['debrief_delivery'] == 'after_encounter'
        assert all('evidence_turn' in q and 'after_turn' not in q for q in data['debrief'])


def test_both_evidence_field_names_are_rejected_without_writing(files):
    fixture, reviews = files
    before = fixture.read_bytes()
    edit(reviews[0], lambda d: d['debrief'][0].update(after_turn=2))
    with pytest.raises(ValueError):
        import_scripts([reviews[0]], fixture)
    assert fixture.read_bytes() == before
