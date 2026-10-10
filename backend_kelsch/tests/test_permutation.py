"""Statistical mechanics preserve learner clusters, N/A, and assignment."""
import copy

import pytest

from backend_kelsch.app.study.permutation import demo_fixture, evaluate_fixture, learner_changes, monte_carlo


def test_repeat_encounters_do_not_increase_learner_weight():
    data = demo_fixture()
    values, details = learner_changes(data['roster'], data['encounters'])
    assert values == {'feedback': [1, 1, 1, 1], 'standard': [0, 0, 0, 0]}
    assert details['scored_by_arm'] == {'feedback': 4, 'standard': 4}
    data['encounters'] = [r for r in data['encounters'] if not r['encounter_id'].endswith('-1')]
    assert learner_changes(data['roster'], data['encounters'])[0] == values


def test_mcpt_matches_small_known_randomization_probability():
    # Of six equal-size assignments for [1,1,0,0], two have absolute difference one.
    result = monte_carlo([1, 1], [0, 0], draws=9999, bootstrap_draws=100, seed=7)
    assert abs(result['p_value'] - 1/3) < .025
    assert result['effect'] == 1 and result['effect_ci95'] == [1, 1]
    assert result == monte_carlo([1, 1], [0, 0], draws=9999, bootstrap_draws=100, seed=7)


def test_null_ties_count_and_p_values_never_zero():
    assert monte_carlo([0, 0], [0, 0], draws=20, bootstrap_draws=20)['p_value'] == 1
    result = monte_carlo([1]*10, [0]*10, draws=20, bootstrap_draws=20)
    assert result['p_value'] >= 1/21


def test_na_and_missingness_retained_by_assigned_arm():
    data = demo_fixture()
    data['encounters'] = [r for r in data['encounters'] if r['learner_id'] != 'fixture-0']
    for row in data['encounters']:
        if row['learner_id'] == 'fixture-4': row['scores'] = {str(d): 'N/A' for d in range(1, 8)}
    values, details = learner_changes(data['roster'], data['encounters'])
    assert details['roster_by_arm'] == {'feedback': 4, 'standard': 4}
    assert details['missing_by_arm'] == {'feedback': {'missing_phase': 1}, 'standard': {'no_common_scored_domains': 1}}
    assert len(values['feedback']) == len(values['standard']) == 3


@pytest.mark.parametrize('mutation', ['arm', 'case', 'duplicate', 'score', 'domain', 'roster'])
def test_invalid_learner_units_rejected(mutation):
    data = demo_fixture()
    row = data['encounters'][0]
    if mutation == 'arm': row['arm'] = 'standard'
    if mutation == 'case':
        for r in data['encounters']: r['case_id'] = 'same-case'
    if mutation == 'duplicate': data['encounters'].append(copy.deepcopy(row))
    if mutation == 'score': row['scores']['1'] = True
    if mutation == 'domain': del row['scores']['7']
    if mutation == 'roster': row['learner_id'] = 'unknown'
    with pytest.raises(ValueError): evaluate_fixture(data)


def test_observed_data_rejected_even_with_self_attested_approval():
    data = demo_fixture() | {'source_kind': 'observed', 'consent_and_ethics_verified': True}
    with pytest.raises(PermissionError): evaluate_fixture(data)


def test_fixture_never_establishes_learning():
    result = evaluate_fixture(demo_fixture())
    assert result['student_learning'] == 'NOT EVALUABLE'
    assert result['scope'] == 'SYNTHETIC MECHANICS ONLY'
