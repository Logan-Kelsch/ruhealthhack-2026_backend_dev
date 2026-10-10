"""One reproducible, offline development demonstration through learner-unit MCPT."""
from __future__ import annotations

import argparse
from hashlib import sha256
import html
import importlib.metadata
import json
from pathlib import Path
import re

from backend_kelsch.app.debrief_probe.evaluation import ROOT
from backend_kelsch.app.study.next_review import source_lock
from backend_kelsch.app.study.protocol import digest
from backend_kelsch.app.study.simulation_inputs import VERSION, default_inputs
from backend_kelsch.app.study.simulation_evaluation import evaluate_actions, difficulty_checks, synthetic_reviews, statistical_scenarios
from backend_kelsch.app.study.simulation_api import api_rehearsal
from backend_kelsch.app.study.permutation import PLAN
from backend_kelsch.app.study.workflow import private_path, save, write_private

FILES = ('action_corpus.json', 'review_policy.json', 'case_preset_decisions.json', 'learner_scenarios.json')
REPLACEMENTS = [
    {'component': 'action spans', 'simulation_input': 'inputs/action_corpus.json',
     'human_adapter': 'backend_kelsch.scripts.prepare_action_data --corpus --annotations; reviewed grouped corpus',
     'remaining': 'Independent exact-span labels, critical positives and genuinely held-out case/family language'},
    {'component': 'semantic/disclosure/feedback/rubric reviews', 'simulation_input': 'inputs/review_policy.json; review_stage/<kind>/synthetic_*.json',
     'human_adapter': 'eval_development configure/evaluate with actual submissions; eval_next_review report for action/claim/domain',
     'remaining': 'Independent qualified answers and disagreement decisions; do not rename simulated sources human'},
    {'component': 'clinical cases, full presets and progression', 'simulation_input': 'inputs/case_preset_decisions.json',
     'human_adapter': 'Qualified decisions, versioned case corrections and a fresh frozen review batch',
     'remaining': 'Clinical facts/disclosure/safety, full presets, next-case routing and actual learner difficulty'},
    {'component': 'protocol, authorization and consent', 'simulation_input': 'frozen_plan.json (proposed synthetic analysis only)',
     'human_adapter': 'Existing backend_kelsch.app.integration.quality trusted authorization workflow',
     'remaining': 'Faculty/ethics decision, consent and externally verified authority; real intake remains blocked'},
    {'component': 'learner outcomes', 'simulation_input': 'inputs/learner_scenarios.json',
     'human_adapter': 'Authorized roster and genuine blinded baseline/follow-up scores under a frozen supported analysis plan',
     'remaining': 'Real baseline/follow-up encounters, valid transfer cases and blinded independent scoring'},
]


def inputs_at(directory: Path, seed: int, supplied: Path | None) -> tuple[dict, dict]:
    if supplied:
        base = private_path(supplied)
        manifest = json.loads((base / 'manifest.json').read_text())
        if manifest.get('version') != VERSION or set(manifest['files']) != set(FILES):
            raise ValueError('complete versioned simulation input manifest required')
        data = {}
        for name in FILES:
            raw = (base / name).read_bytes()
            if sha256(raw).hexdigest() != manifest['files'][name]:
                raise ValueError('simulation input digest mismatch')
            data[name] = json.loads(raw)
    else:
        data = default_inputs(seed)
        data['case_preset_decisions.json']['case_sha256'] = {cid: sha256((ROOT / 'cases' / (cid + '.json')).read_bytes()).hexdigest()
                                                          for cid in ('walter_greene', 'alina_reyes', 'eli_brooks')}
    for name, value in data.items():
        if value.get('version') != VERSION or value.get('source_kind') != 'synthetic_fixture' or not value.get('generation_description'):
            raise PermissionError('simulation mode accepts documented synthetic inputs only; use separate human/authorized workflows')
        save(directory / name, value)
    case_hashes = {cid: sha256((ROOT / 'cases' / (cid + '.json')).read_bytes()).hexdigest()
                   for cid in ('walter_greene', 'alina_reyes', 'eli_brooks')}
    if data['case_preset_decisions.json'].get('case_sha256') != case_hashes or data['case_preset_decisions.json'].get('decision') != 'ASSUMED_FOR_SIMULATION':
        raise ValueError('synthetic case decision source/version mismatch')
    receipt = {'version': VERSION, 'files': {name: sha256((directory / name).read_bytes()).hexdigest() for name in FILES}}
    save(directory / 'manifest.json', receipt)
    return data, receipt


def render_report(report: dict) -> str:
    lines = ['# [Product name]: simulation demonstration through MCPT', '',
             '**SIMULATION ONLY — authored references and assumed learner effects. No clinical approval or learning-effect evidence.**', '',
             f"Demo readiness: **{report['demo_readiness']}**. Human evidence readiness: **NOT EVALUABLE**.", '',
             '## Executed backend and evaluation', '', '| Component | Execution/result |', '|---|---|',
             f"| Studio → new patient → debrief → follow-up | {report['api']['mode']}; {report['api']['status']} |",
             f"| HTTP requests | {report['api'].get('requests', 0)} |",
             f"| Difficulty/replay | {report['difficulty']['runs']} runs, {report['difficulty']['replay_matches']} matching replays |",
             f"| Provisional progression | {report['difficulty']['progression']['status']}; five score/N/A/safety controls; simulation adapter only |",
             f"| Synthetic action corpus | {report['actions']['patients']} synthetic patient groups; {report['actions']['annotation_counts']} spans by split |",
             f"| Trained whole-sentence action macro-F1 | {report['actions']['trained_sentence_classifier']['macro_f1_over_observed_labels']:.4f}; synthetic template labels |",
             f"| Keyword action macro-F1 | {report['actions']['keyword_sentence_classifier']['macro_f1_over_observed_labels']:.4f}; synthetic template labels |", '',
             'These action scores measure template generalization, not real learner performance or arbitrary span extraction. '
             'Predictions were frozen before comparison; training used training labels only. Validation groups remain unused.', '',
             '## Simulated review transport', '', '| Kind | Tasks | A/B agreements | Disagreements | Baseline differences |', '|---|---:|---:|---:|---:|']
    for kind, value in report['reviews']['batches'].items():
        lines.append(f"| {kind} | {value['tasks']} | {value['paired_agreement']} | {value['disagreements']} | {value['diagnostic_differences']} |")
    lines += ['', 'References are seeded correlated simulations. Disclosure labels echo engine output. '
              'Action/claim/domain references perturb baseline outputs; their agreement is partly constructed. '
              'Constructor-known semantic probes are not a live Bedrock evaluation.', '',
              '## Monte Carlo permutation testing (MCPT)', '',
              '| Synthetic scenario | Scored feedback / standard | Effect | 95% learner-bootstrap interval | p-value |',
              '|---|---:|---:|---|---:|']
    for name, result in report['mcpt'].items():
        counts, stats = result['denominators']['scored_by_arm'], result['statistics']
        if stats:
            interval = ' to '.join(f'{v:.4f}' for v in stats['effect_ci95'])
            lines.append(f"| {name} | {counts['feedback']} / {counts['standard']} | {stats['effect']:.4f} | {interval} | {stats['p_value']:.4f} |")
        else:
            lines.append(f"| {name} | {counts['feedback']} / {counts['standard']} | N/A | N/A | N/A |")
    lines += ['', '| Scenario | Assigned feedback / standard | Encounters | Excluded learners by arm | Seed | Permutations / bootstraps | Monte Carlo tail 95% interval |',
              '|---|---:|---:|---|---:|---:|---|']
    for name, result in report['mcpt'].items():
        counts, stats = result['denominators'], result['statistics']
        assigned = counts['roster_by_arm']
        excluded = {arm: assigned[arm] - counts['scored_by_arm'][arm] for arm in assigned}
        interval = ' to '.join(f"{stats['monte_carlo_tail_ci95'][bound]:.4f}" for bound in ('lower', 'upper')) if stats else 'N/A'
        plan = result['plan']
        lines.append(f"| {name} | {assigned['feedback']} / {assigned['standard']} | {counts['encounters']} | {excluded} | {plan['seed']} | {plan['draws']} / {plan['bootstrap_draws']} | {interval} |")
    lines += ['', 'One outcome per learner; repeats are averaged within each phase/domain. N/A is not imputed. '
              'Assigned-arm missingness remains in roster counts. These p-values describe invented mathematical outcomes. '
              'The exact null is a test control, not an estimated false-positive rate. '
              'Each JSON result includes seeds, draw counts, input/plan hashes, bootstrap and Monte Carlo tail uncertainty.', '',
              '## Human replacement map', '', '| Component | Replace this simulation | Human route |', '|---|---|---|']
    for row in report['replacement_map']:
        lines.append(f"| {row['component']} | `{row['simulation_input']}` | {row['human_adapter']} |")
    lines += ['', '## Operational limits', '']
    for limitation in report['operational_blockers']:
        lines.append('- ' + limitation)
    lines += ['', 'Source/input receipts: `source_manifest.json`, `inputs/manifest.json`, `frozen_plan.json`, '
              '`frozen_action_predictions.json`, per-batch `PRIVATE_predictions.json` and `reference_simulated_v1.json`. '
              'Raw API interactions and the disposable SQLite database are local artifacts; no real patient or learner data.', '']
    return '\n'.join(lines)


def report_html(markdown: str) -> str:
    """Render the small report subset without adding a Markdown runtime dependency."""
    def inline(text):
        text = html.escape(text)
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
        return re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    blocks, table = [], False
    for line in markdown.splitlines():
        if line.startswith('|'):
            if set(line.replace('|', '').strip()) <= set('-: '):
                continue
            if not table:
                blocks.append('<div class="table"><table>')
                table = True
                tag = 'th'
            else:
                tag = 'td'
            blocks.append('<tr>' + ''.join(f'<{tag}>{inline(c.strip())}</{tag}>' for c in line.strip('|').split('|')) + '</tr>')
            continue
        if table:
            blocks.append('</table></div>')
            table = False
        if not line:
            continue
        if line.startswith('#'):
            level = min(3, len(line) - len(line.lstrip('#')))
            blocks.append(f'<h{level}>' + inline(line.lstrip('#').strip()) + f'</h{level}>')
        elif line.startswith('- '):
            blocks.append('<p class="bullet">• ' + inline(line[2:]) + '</p>')
        else:
            blocks.append('<p>' + inline(line) + '</p>')
    if table:
        blocks.append('</table></div>')
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Simulation report</title><style>body{font:16px system-ui;max-width:1150px;margin:30px auto;padding:24px;background:#101827;color:#e5edff;line-height:1.5}h1{color:#d5e8ff}h2{color:#93c5fd;margin-top:36px}strong{color:#fde68a}.table{overflow-x:auto}table{width:100%;border-collapse:collapse;background:#192338}th,td{padding:12px;text-align:left;border-bottom:1px solid #35445c}th{color:#93c5fd}code{color:#c4b5fd;overflow-wrap:anywhere}.bullet{margin:8px 0}</style>' + ''.join(blocks) + '</html>'


def run_demo(output: Path, *, seed: int = 2026, draws: int = 4999, bootstrap_draws: int = 1999,
             supplied_inputs: Path | None = None) -> dict:
    if type(seed) is not int or type(draws) is not int or draws < 1 or type(bootstrap_draws) is not int or bootstrap_draws < 2:
        raise ValueError('integer seed, positive permutations and at least two bootstraps required')
    output = private_path(output)
    if output.exists():
        raise ValueError('use a new output directory; never overwrite frozen inputs or predictions')
    output.mkdir(parents=True, mode=0o700)
    paths = source_lock()
    for source in (ROOT / 'backend_kelsch/app').rglob('*.py'):
        paths[str(source.relative_to(ROOT))] = sha256(source.read_bytes()).hexdigest()
    for source in (ROOT / 'backend_kelsch/app/data').rglob('*'):
        if source.is_file() and '__pycache__' not in source.parts:
            paths[str(source.relative_to(ROOT))] = sha256(source.read_bytes()).hexdigest()
    source = ROOT / 'backend/scripts/run_simulation_demo.py'
    paths[str(source.relative_to(ROOT))] = sha256(source.read_bytes()).hexdigest()
    versions = {name: importlib.metadata.version(name) for name in ('fastapi', 'pydantic', 'sqlalchemy', 'scikit-learn')}
    save(output / 'source_manifest.json', {'version': VERSION, 'source_sha256': paths, 'dependencies': versions})
    inputs, receipts = inputs_at(output / 'inputs', seed, supplied_inputs)
    # Freeze all scenario plans before outcomes are compared or hypotheses inspected.
    plan = {'version': VERSION, 'scope': 'synthetic demonstration only; no authorization', 'seed': seed,
            'draws': draws, 'bootstrap_draws': bootstrap_draws, 'primary_statistic': 'learner mean change difference',
            'scenario_input_sha256': digest(inputs['learner_scenarios.json']),
            'scenarios': [s['scenario'] for s in inputs['learner_scenarios.json']['scenarios']],
            'scenario_plans': {s['scenario']: dict(PLAN, draws=draws, bootstrap_draws=bootstrap_draws, seed=s['seed'])
                               for s in inputs['learner_scenarios.json']['scenarios']},
            'multiplicity': 'separate mathematical test controls, not five prespecified clinical endpoints'}
    save(output / 'frozen_plan.json', plan)
    actions = evaluate_actions(inputs['action_corpus.json'], output, seed)
    difficulty, runs = difficulty_checks(inputs['case_preset_decisions.json'])
    reviews = synthetic_reviews(output, inputs['review_policy.json'], runs)
    try:
        api = api_rehearsal(output)
    except Exception as exc:
        # Failed integration remains visible; no template metric substitutes for HTTP execution.
        api = {'mode': 'UNEVALUABLE OR FAILED HTTP', 'status': 'FAIL', 'error_type': type(exc).__name__,
               'reason': str(exc), 'bedrock': 'NOT RUN', 'voice': 'NOT RUN'}
    mcpt = statistical_scenarios(inputs['learner_scenarios.json'], draws, bootstrap_draws)
    success = api['status'] == difficulty['status'] == 'PASS' and all(v['transport'] == 'PASS' for v in reviews['batches'].values()) and all(v['statistics'] for v in mcpt.values())
    report = {'version': VERSION, 'mode': 'SIMULATION_ONLY', 'demo_readiness': 'PASS' if success else 'INCOMPLETE',
        'evidence_readiness': {key: 'NOT EVALUABLE' for key in ('clinical_approval', 'independent_human_labels', 'real_learner_action_performance',
            'faculty_rubric_agreement', 'full_difficulty_calibration', 'authorization_and_consent', 'learning_effect')},
        'source_manifest_sha256': sha256((output / 'source_manifest.json').read_bytes()).hexdigest(), 'input_receipts': receipts, 'frozen_plan_sha256': digest(plan),
        'dependencies': versions, 'actions': actions, 'difficulty': difficulty, 'reviews': reviews, 'api': api, 'mcpt': mcpt,
        'case_preset_assumptions': inputs['case_preset_decisions.json'], 'replacement_map': REPLACEMENTS,
        'operational_blockers': ['Live Bedrock access and current-model evaluation were not executed in this offline command.',
            'Microphone, speech recognition, playback, echo/barge-in and voice first-audio latency need the integrated frontend rehearsal.',
            'Postgres/cloud deployment and full service costs are unevaluated; no guessed latency or cost numbers are presented.',
            'Case content, safety/disclosure, full presets and next-case routing still need qualified decisions.',
            'Independent labels and authorized genuine learner outcomes must replace simulations before a learning-effect claim.']}
    report['report_sha256'] = digest(report)
    save(output / 'simulation_report.json', report)
    markdown = render_report(report)
    write_private(output / 'simulation_report.md', markdown)
    # A static, shareable report, never a student-facing input or fabricated product screen.
    write_private(output / 'simulation_report.html', report_html(markdown))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['simulation'], default='simulation')
    parser.add_argument('--output', type=Path, required=True, help='New private directory outside Git')
    parser.add_argument('--inputs-dir', type=Path, help='Pinned versioned synthetic inputs for repeat/replacement runs')
    parser.add_argument('--seed', type=int, default=2026)
    parser.add_argument('--draws', type=int, default=4999)
    parser.add_argument('--bootstrap-draws', type=int, default=1999)
    args = parser.parse_args()
    report = run_demo(args.output, seed=args.seed, draws=args.draws, bootstrap_draws=args.bootstrap_draws, supplied_inputs=args.inputs_dir)
    print(json.dumps({'mode': report['mode'], 'demo_readiness': report['demo_readiness'],
                      'evidence_readiness': report['evidence_readiness'], 'reports': str(args.output)}, indent=2))
    if report['demo_readiness'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
