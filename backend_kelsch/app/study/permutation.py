"""Learner-unit statistical mechanics; this public path accepts synthetic fixtures only."""
from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
from math import isfinite, isclose
from pathlib import Path
import random
from statistics import mean

from backend_kelsch.app.study.analysis import wilson
from backend_kelsch.app.study.protocol import digest

PLAN = {
    'version': 'development_mcpt_v1',
    'population': 'synthetic fixtures only; observed intake requires the separate authorization workflow',
    'design': 'unstratified parallel assignment; fixed assigned arms feedback and standard',
    'outcome': 'mean followup-minus-baseline change over common scored domains 1–7 per learner',
    'repeated_encounters': 'average each scored domain within phase before common-domain change',
    'missingness': 'retain roster counts, report incomplete learners by arm, do not impute N/A',
    'statistic': 'mean learner change in feedback minus mean learner change in standard',
    'tail': 'absolute statistic at least as extreme as observed; ties included',
    'draws': 4999, 'bootstrap_draws': 1999, 'seed': 42,
    'p_value': '(extreme + 1) / (draws + 1)',
    'effect_interval': 'within-arm learner bootstrap percentile 95%; descriptive on small samples',
    'multiple_testing': 'one primary statistic; secondary outcomes require a separate prespecified correction',
    'method_reference': 'https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html',
}


def learner_changes(roster: list[dict], encounters: list[dict]) -> tuple[dict, dict]:
    """One outcome per assigned learner, with missingness kept in the denominator."""
    assignments = {}
    for row in roster:
        lid, arm = row.get('learner_id'), row.get('arm')
        if not isinstance(lid, str) or not lid or lid in assignments or arm not in {'feedback', 'standard'}:
            raise ValueError('unique learner roster and valid assigned arm required')
        assignments[lid] = arm
    seen = set()
    grouped = defaultdict(lambda: defaultdict(list))
    for row in encounters:
        lid, phase, eid = row.get('learner_id'), row.get('phase'), row.get('encounter_id')
        if lid not in assignments or phase not in {'baseline', 'followup'} or not isinstance(eid, str) or not eid or eid in seen:
            raise ValueError('encounter identity, phase or roster mismatch')
        if row.get('arm', assignments[lid]) != assignments[lid] or not isinstance(row.get('case_id'), str) or not row['case_id']:
            raise ValueError('assigned arm or case identity mismatch')
        scores = row.get('scores')
        if not isinstance(scores, dict) or set(scores) != {str(i) for i in range(1, 8)}:
            raise ValueError('all seven domains required; mark unscored domains N/A')
        if any(v != 'N/A' and (type(v) is not int or v not in range(1, 5)) for v in scores.values()):
            raise ValueError('scores must be 1–4 or N/A')
        seen.add(eid)
        grouped[lid][phase].append(row)
    values = {'feedback': [], 'standard': []}
    missing = {a: Counter() for a in values}
    for lid in sorted(assignments):
        arm = assignments[lid]
        phases = grouped[lid]
        if set(phases) != {'baseline', 'followup'}:
            missing[arm]['missing_phase'] += 1
            continue
        cases = [{r['case_id'] for r in phases[p]} for p in ('baseline', 'followup')]
        if cases[0] & cases[1]:
            raise ValueError('followup case must be held out from learner baseline')
        averages = []
        for phase in ('baseline', 'followup'):
            scored = defaultdict(list)
            for r in phases[phase]:
                for d, value in r['scores'].items():
                    if value != 'N/A':
                        scored[d].append(value)
            averages.append({d: mean(v) for d, v in scored.items()})
        common = sorted(averages[0].keys() & averages[1].keys())
        if not common:
            missing[arm]['no_common_scored_domains'] += 1
            continue
        values[arm].append(mean(averages[1][d] - averages[0][d] for d in common))
    counts = Counter(assignments.values())
    details = {'roster_by_arm': {a: counts[a] for a in values},
               'scored_by_arm': {a: len(v) for a, v in values.items()},
               'missing_by_arm': {a: dict(v) for a, v in missing.items()},
               'encounters': len(encounters), 'analysis_unit': 'learner',
               'missingness_interpretation': 'assigned-arm available-case analysis; no claim of complete intention-to-treat inference'}
    return values, details


def monte_carlo(a: list[float], b: list[float], *, draws: int = 4999,
                bootstrap_draws: int = 1999, seed: int = 42) -> dict:
    if type(draws) is not int or draws < 1 or type(bootstrap_draws) is not int or bootstrap_draws < 2:
        raise ValueError('positive permutation and at least two bootstrap draws required')
    if len(a) < 2 or len(b) < 2 or any(type(v) not in {int, float} or not isfinite(v) for v in a + b):
        raise ValueError('two finite learner outcomes per arm required')
    effect = mean(a) - mean(b)
    combined = a + b
    rng = random.Random(seed)
    extreme = 0
    for _ in range(draws):
        shuffled = rng.sample(combined, len(combined))
        value = mean(shuffled[:len(a)]) - mean(shuffled[len(a):])
        extreme += abs(value) >= abs(effect) or isclose(abs(value), abs(effect), rel_tol=1e-12, abs_tol=1e-12)
    bootstrap = random.Random(seed + 1)
    samples = sorted(mean(bootstrap.choices(a, k=len(a))) - mean(bootstrap.choices(b, k=len(b)))
                     for _ in range(bootstrap_draws))
    return {'effect': effect, 'effect_ci95': [samples[int(.025 * bootstrap_draws)], samples[int(.975 * bootstrap_draws)]],
            'p_value': (extreme + 1) / (draws + 1), 'extreme_draws': extreme, 'draws': draws,
            'monte_carlo_tail_ci95': wilson(extreme, draws), 'bootstrap_draws': bootstrap_draws,
            'seed': seed, 'tail': 'two-sided absolute mean difference', 'analysis_unit': 'learner'}


def evaluate_fixture(data: dict) -> dict:
    # A flag is not authorization: even a fully populated observed envelope is rejected.
    if data.get('source_kind') != 'synthetic_fixture':
        raise PermissionError('observed learner intake requires independently verified authorization; this command accepts synthetic fixtures only')
    if data.get('design') != 'unstratified_parallel' or not data.get('generation_description'):
        raise ValueError('document fixture generation and supported assignment design')
    values, details = learner_changes(data['roster'], data['encounters'])
    report = {'scope': 'SYNTHETIC MECHANICS ONLY', 'student_learning': 'NOT EVALUABLE',
              'implementation_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
              'plan': PLAN, 'plan_sha256': digest(PLAN), 'input_sha256': digest(data), **details}
    if any(len(v) < 2 for v in values.values()):
        return report | {'status': 'NOT EVALUABLE', 'statistics': None, 'reason': 'need two scored learners per arm'}
    return report | {'status': 'EVALUATED', 'statistics': monte_carlo(values['feedback'], values['standard'])}


def demo_fixture() -> dict:
    """Eight invented learners, unequal repeat counts, one N/A; no learner transcripts."""
    roster, encounters = [], []
    for i in range(8):
        lid, arm = f'fixture-{i}', 'feedback' if i < 4 else 'standard'
        roster.append({'learner_id': lid, 'arm': arm})
        for phase in ('baseline', 'followup'):
            for repeat in range(2 if i == 0 else 1):
                score = 2 if phase == 'baseline' else (3 if i < 4 else 2)
                scores = {str(d): score for d in range(1, 8)}
                if i == 1:
                    scores['7'] = 'N/A'
                encounters.append({'learner_id': lid, 'encounter_id': f'{lid}-{phase}-{repeat}',
                    'phase': phase, 'case_id': f'fixture-case-{phase}', 'scores': scores})
    return {'source_kind': 'synthetic_fixture', 'design': 'unstratified_parallel',
            'generation_description': 'Code-authored constant scores: feedback changes by one point; standard by zero. Exercises arithmetic, not learning.',
            'roster': roster, 'encounters': encounters}
