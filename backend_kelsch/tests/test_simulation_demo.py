"""Simulation isolation, leakage controls, reproducibility and learner-unit mechanics."""
from hashlib import sha256
import json

import pytest

from backend_kelsch.app.study.simulation_demo import run_demo, inputs_at, report_html
from backend_kelsch.app.study.simulation_inputs import default_inputs, learner_fixture, action_corpus
from backend_kelsch.app.study.simulation_evaluation import evaluate_actions, statistical_scenarios, progression_recommendation
from backend_kelsch.app.study.permutation import evaluate_fixture
from backend_kelsch.app.study.protocol import digest


@pytest.fixture(scope='module')
def demo(tmp_path_factory):
    directory = tmp_path_factory.mktemp('simulation-parent') / 'demo'
    result = run_demo(directory, draws=199, bootstrap_draws=99)
    return directory, result


def test_actual_http_flow_and_all_simulated_components(demo):
    directory, result = demo
    assert result['demo_readiness'] == 'PASS'
    assert result['api']['mode'] == 'OFFLINE HTTP EXECUTED'
    assert result['api']['studio_created_and_published']
    assert result['api']['new_patient_encounter_and_debrief']
    assert result['api']['authored_followup_visit'] == 'v2'
    assert result['api']['bedrock'] == 'NOT RUN'
    assert result['api']['voice_first_audio_latency_ms'] is None
    assert set(result['evidence_readiness'].values()) == {'NOT EVALUABLE'}
    assert set(result['reviews']['batches']) == {'action', 'claim', 'domain', 'semantic', 'release'}
    assert result['reviews']['independent_human_reviews'] == 0
    assert result['difficulty']['replay_matches'] == 27
    assert result['difficulty']['clinical_content_unchanged']
    routing = result['difficulty']['progression']
    assert routing['status'] == 'PASS'
    assert routing['controls'][0]['recommendation']['case_id'] == 'walter_greene'
    assert not routing['controls'][0]['recommendation']['new_compatible_case_available']
    assert routing['controls'][3]['recommendation']['status'] == 'ABSTAIN'
    assert routing['controls'][4]['recommendation']['status'] == 'REVIEW_REQUIRED'
    assert result['api']['golden_preview_replies_failing_mechanical_audit'] == 0
    assert (directory / 'simulation_api.sqlite').exists()
    assert '<table>' in (directory / 'simulation_report.html').read_text()
    unsigned = dict(result)
    unsigned.pop('report_sha256')
    assert digest(unsigned) == result['report_sha256']
    frozen_plan = json.loads((directory / 'frozen_plan.json').read_text())
    assert all(frozen_plan['scenario_plans'][name] == value['plan'] for name, value in result['mcpt'].items())


def test_simulated_review_metadata_never_human_or_faculty(demo):
    directory, result = demo
    for kind in result['reviews']['batches']:
        config = json.loads((directory / 'review_stage' / kind / 'reference_simulated_v1.json').read_text())
        assert all(s['provenance']['type'] == 'synthetic' for s in config['submissions'])
        for slot in ('a', 'b', 'adjudicator'):
            rows = json.loads((directory / 'review_stage' / kind / f'synthetic_{slot}.json').read_text())
            assert all('reviewer_role' not in r and 'approved' not in r for r in rows)
    comparison = result['reviews']['batches']['domain']['comparison']['metrics']['domain']
    assert comparison['na_mismatches'] > 0
    semantic = result['reviews']['batches']['semantic']['comparison']['metrics']['semantic']
    assert semantic['fp'] > 0  # mechanical checks are not a semantic judge


def test_grouped_action_training_and_frozen_prediction_denominators(demo):
    directory, result = demo
    corpus = json.loads((directory / 'inputs/action_corpus.json').read_text())
    split = json.loads((directory / 'action_split_assignments.json').read_text())
    linked = {}
    for c in corpus['conversations']:
        linked.setdefault(c['family_id'], set()).add(split[c['conversation_id']])
    assert all(len(s) == 1 for s in linked.values())
    assert result['actions']['cross_split_links'] == 0
    assert result['actions']['synthetic_group_held_out'] and not result['actions']['real_learner_held_out']
    predictions = json.loads((directory / 'frozen_action_predictions.json').read_text())
    assert len(predictions) == result['actions']['annotation_counts']['test']
    assert sha256((directory / 'frozen_action_predictions.json').read_bytes()).hexdigest() == result['actions']['prediction_sha256']
    assert all(v['positive_support'] >= 10 for v in result['actions']['trained_sentence_classifier']['critical_recall'].values())


def test_scenario_signs_null_ties_and_one_learner_weight(demo):
    _, result = demo
    null = result['mcpt']['no_effect']['statistics']
    assert null['effect'] == 0 and null['p_value'] == 1
    assert result['mcpt']['beneficial_effect']['statistics']['effect'] > 0
    assert result['mcpt']['adverse_effect']['statistics']['effect'] < 0
    repeated = result['mcpt']['repeated_encounters']
    assert repeated['denominators']['encounters'] > result['mcpt']['beneficial_effect']['denominators']['encounters']
    assert repeated['statistics'] == result['mcpt']['beneficial_effect']['statistics']
    assert repeated['denominators']['scored_by_arm'] == {'feedback': 12, 'standard': 12}
    assert all(v['statistics']['p_value'] >= 1/200 for v in result['mcpt'].values())


def test_missingness_and_na_remain_visible(demo):
    _, result = demo
    missing = result['mcpt']['missingness']['denominators']
    assert missing['roster_by_arm'] == {'feedback': 12, 'standard': 12}
    assert sum(missing['scored_by_arm'].values()) < 24
    assert any(v.get('no_common_scored_domains', 0) for v in missing['missing_by_arm'].values())
    assert all(v['analysis_unit'] == 'learner' for v in (r['statistics'] for r in result['mcpt'].values()))


def test_inputs_reproduce_statistics_and_checks(demo, tmp_path):
    directory, first = demo
    second = run_demo(tmp_path / 'repeat', draws=199, bootstrap_draws=99, supplied_inputs=directory / 'inputs')
    assert first['report_sha256'] == second['report_sha256']
    assert first['mcpt'] == second['mcpt']
    assert first['actions'] == second['actions']
    with pytest.raises(ValueError, match='new output'):
        run_demo(tmp_path / 'repeat', draws=199, bootstrap_draws=99)


@pytest.mark.parametrize('mutation', ['offset', 'speaker', 'label', 'origin'])
def test_invalid_synthetic_annotation_rejected(tmp_path, mutation):
    corpus = action_corpus(5)
    row = corpus['annotations'][0]
    if mutation == 'offset': row['start'] = True
    if mutation == 'speaker': corpus['conversations'][0]['turns'][0]['speaker'] = 'patient'
    if mutation == 'label': row['labels'] = ['invented_action']
    if mutation == 'origin': row['label_origin'] = 'human'
    with pytest.raises(ValueError, match='synthetic exact-span'):
        evaluate_actions(corpus, tmp_path, 2026)


def test_observed_learner_data_remains_blocked_and_no_approval_flag_bypasses():
    observed = learner_fixture('beneficial_effect') | {'source_kind': 'observed', 'consent_and_ethics_verified': True}
    with pytest.raises(PermissionError): evaluate_fixture(observed)
    data = default_inputs()['learner_scenarios.json']
    data['scenarios'][0] = observed
    with pytest.raises(PermissionError): statistical_scenarios(data, 10, 10)


def test_tampered_input_manifest_rejected(demo, tmp_path):
    directory, _ = demo
    supplied = tmp_path / 'inputs'
    supplied.mkdir()
    for p in (directory / 'inputs').glob('*.json'):
        (supplied / p.name).write_bytes(p.read_bytes())
    (supplied / 'review_policy.json').write_text('{}')
    with pytest.raises(ValueError, match='digest mismatch'):
        inputs_at(tmp_path / 'copy', 2026, supplied)


def test_incomplete_scenario_set_rejected():
    data = default_inputs()['learner_scenarios.json']
    data['scenarios'].pop()
    with pytest.raises(ValueError, match='all five'):
        statistical_scenarios(data, 10, 10)


def test_report_escapes_untrusted_markup():
    assert '<script>' not in report_html('# <script>bad</script>')
    assert '&lt;script&gt;' in report_html('# <script>bad</script>')


def test_progression_rejects_invalid_policy_and_zero_imputation():
    policy = default_inputs()['case_preset_decisions.json']['progression_policy']
    with pytest.raises(ValueError, match='score thresholds'):
        progression_recommendation(policy | {'difficult_min_score': 2}, [], 'unused', {})
    with pytest.raises(ValueError, match='seven rubric'):
        progression_recommendation(policy, [], 'unused', {str(d): 0 for d in range(1, 8)})
