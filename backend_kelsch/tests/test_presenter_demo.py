"""Keep presentation labels, failed live calls, and original learner weights visible."""
import gzip
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend_kelsch.app.grounding import live
from backend_kelsch.app.study import presenter
from backend_kelsch.app.study.permutation import learner_changes, monte_carlo, PLAN
from backend_kelsch.app.study.protocol import digest
from backend_kelsch.app.study.simulation_inputs import learner_fixture


def test_safe_configuration_never_serializes_credentials(monkeypatch):
    config = SimpleNamespace(aws_region='test-region', bedrock_model_fast='test-fast', bedrock_model_strong='test-strong',
                             aws_access_key_id='unit-test-private-key-marker', aws_secret_access_key='unit-test-private-secret-marker')
    monkeypatch.setattr(presenter, 'get_settings', lambda: config)
    serialized = json.dumps(presenter.safe_configuration())
    assert 'unit-test-private' not in serialized
    assert 'Configured key pair' in serialized


def test_exact_span_html_is_escaped_and_unicode_offsets_preserved():
    text = '🙂 I will order a test. <script>'
    start, end = text.index('I will'), text.index(' <script>')
    marked = presenter.span_markup(text, start, end)
    assert '>I will order a test.</mark>' in marked
    assert '<script>' not in marked and '&lt;script&gt;' in marked
    with pytest.raises(ValueError): presenter.span_markup(text, True, end)


def test_repeated_encounter_table_keeps_one_row_per_learner_and_na():
    pytest.importorskip('pandas')
    scenario = learner_fixture('repeated_encounters')
    table = presenter.learner_table(scenario)
    assert len(table) == 24 and table['Learner'].is_unique
    assert table['Encounter count'].max() == 6
    missing = presenter.learner_table(learner_fixture('missingness'))
    assert missing['Change'].isna().sum() == 5
    assert not missing.loc[~missing['Analyzed'], 'Change'].eq(0).any()


def test_null_histogram_recreates_frozen_draws_and_rejects_tampering():
    import math
    scenario = learner_fixture('beneficial_effect')
    values, _ = learner_changes(scenario['roster'], scenario['encounters'])
    plan = dict(PLAN, seed=2026, draws=199, bootstrap_draws=99)
    stats = monte_carlo(values['feedback'], values['standard'], seed=2026, draws=199, bootstrap_draws=99)
    result = {'input_sha256': digest(scenario), 'plan': plan, 'plan_sha256': digest(plan), 'statistics': stats}
    distribution = presenter.permutation_distribution(scenario, result)
    extreme = sum(abs(v) >= abs(stats['effect']) or math.isclose(abs(v), abs(stats['effect']), rel_tol=1e-12, abs_tol=1e-12) for v in distribution)
    assert (extreme+1)/200 == stats['p_value']
    with pytest.raises(ValueError, match='original frozen'):
        presenter.permutation_distribution(scenario | {'seed': 0}, result)


def _live_files(tmp_path, oks, mode='live'):
    calls = [{'purpose': 'verify', 'ok': ok, 'error': None if ok else 'JSONDecodeError: private raw detail', 'latency_ms': 1} for ok in oks]
    report = {'version': 'mocked_unit_test', 'mode': mode, 'usage_and_cost': {'model_calls': len(calls)},
              'delivered': {'fallback_replies': 1, 'replies': 1}}
    trace = {'version': 'mocked_unit_test', 'mode': mode, 'runs': [{'turns': [{'llm_calls': calls}]}], 'challenges': []}
    rp, tp = tmp_path / 'live_report.json', tmp_path / 'live_trace.json.gz'
    rp.write_text(json.dumps(report)); tp.write_bytes(gzip.compress(json.dumps(trace).encode()))
    return rp, tp


@pytest.mark.parametrize('oks,mode,expected', [([], 'live', 'NOT EVALUABLE'), ([False], 'live', 'FAILED'),
                                            ([True, False], 'live', 'PARTIAL'), ([True], 'live', 'LIVE EXECUTED'),
                                            ([], 'offline', 'NOT EVALUABLE')])
def test_live_summary_does_not_convert_attempted_execution_into_success(tmp_path, oks, mode, expected):
    rp, tp = _live_files(tmp_path, oks, mode)
    _, _, summary = presenter.load_live_files(rp, tp)
    assert summary['Execution'] == expected
    assert summary['Successful model attempts'] == sum(oks)
    assert summary['Failed model attempts'] == len(oks) - sum(oks)
    assert 'private raw detail' not in json.dumps(summary)


def test_live_report_trace_denominators_must_match(tmp_path):
    rp, tp = _live_files(tmp_path, [True])
    data = json.loads(rp.read_text()); data['usage_and_cost']['model_calls'] = 2
    rp.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='denominators'):
        presenter.load_live_files(rp, tp)


def test_live_subprocess_has_isolated_configuration_and_missing_outputs_visible(tmp_path, monkeypatch):
    before = os.environ.get('LLM_ENABLED')
    def fake_run(command, **kwargs):
        assert kwargs['env']['LLM_ENABLED'] == 'true'
        assert kwargs['cwd'] == presenter.ROOT
        assert command[command.index('--report')+1].endswith('live_report.json')
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(presenter.subprocess, 'run', fake_run)
    report, trace, summary = presenter.run_live_probe(tmp_path / 'probe')
    assert not report and not trace and summary['Execution'] == 'NOT EVALUABLE'
    assert os.environ.get('LLM_ENABLED') == before


def test_dotenv_aware_session_used_in_live_preflight(monkeypatch):
    monkeypatch.setattr(live, 'llm_available', lambda: True)
    calls = []
    def session():
        calls.append('application-session')
        return SimpleNamespace(get_credentials=lambda: object())
    monkeypatch.setattr(live, 'aws_session', session)
    assert live.credentials_ready() and calls == ['application-session']
    monkeypatch.setattr(live, 'llm_available', lambda: False)
    assert not live.credentials_ready() and len(calls) == 1


def test_repo_notebook_defaults_offline_and_has_no_saved_outputs():
    notebook = json.loads((presenter.ROOT / 'backend_kelsch/notebooks/10_clinical_presenter_demo.ipynb').read_text())
    cells = [c for c in notebook['cells'] if c['cell_type'] == 'code']
    assert 'RUN_LIVE_BEDROCK = False' in ''.join(cells[0]['source'])
    assert all(c['outputs'] == [] and c['execution_count'] is None for c in cells)
