"""Clinical-facing views of recorded demo outputs; never infer clinical authority."""
from __future__ import annotations

from collections import Counter
import gzip
import html
import json
import os
from pathlib import Path
import random
from statistics import mean
import subprocess
import sys

from app.settings import get_settings
from backend_kelsch.app.debrief_probe.evaluation import ROOT
from backend_kelsch.app.study.permutation import learner_changes
from backend_kelsch.app.study.protocol import digest
from backend_kelsch.app.study.workflow import private_path

COLORS = {'blue': '#2563eb', 'teal': '#0d9488', 'amber': '#b45309', 'red': '#dc2626', 'gray': '#64748b'}


def safe_configuration() -> dict:
    """Select safe fields rather than serializing settings or credentials."""
    settings = get_settings()
    return {'AWS region': settings.aws_region, 'Fast model': settings.bedrock_model_fast,
            'Strong model': settings.bedrock_model_strong,
            'Credential route': 'Configured key pair (values hidden)' if settings.aws_access_key_id and settings.aws_secret_access_key
                               else 'Configured profile / SDK credential chain (values hidden)',
            'Configuration files': 'Root .env, then backend/.env; process environment takes precedence'}


def span_markup(text: str, start: int, end: int) -> str:
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
        raise ValueError('valid exact-span offsets required')
    return '<p style="font-size:18px;line-height:1.7">' + html.escape(text[:start]) + '<mark style="background:#fef3c7;padding:4px">' + html.escape(text[start:end]) + '</mark>' + html.escape(text[end:]) + '</p>'


def domain_table(workspace: Path, case_id: str = 'walter_greene', scenario: str = 'authored'):
    import pandas as pd
    tasks = json.loads((workspace / 'review_stage/domain/blinded_tasks.json').read_text())
    predictions = {p['packet_id']: p for p in json.loads((workspace / 'review_stage/domain/PRIVATE_predictions.json').read_text())}
    selected = [t for t in tasks if t['case']['case_id'] == case_id and
                predictions[t['packet_id']]['source_mapping']['scenario'] == scenario]
    if not selected:
        raise ValueError('case/scenario not available in frozen domain batch')
    rows = []
    for task in selected:
        pred = predictions[task['packet_id']]
        if pred['source_mapping']['scenario'] != scenario:
            continue
        context = task['context']
        rows.append({'Domain': context['domain_id'], 'Clinical area': context['domain']['name'],
                     'Provisional score': pred['answer']['score'],
                     'Source': 'Current offline rule-based scorer; not a faculty grade'})
    return pd.DataFrame(rows).sort_values('Domain'), scenario, selected


def learner_table(scenario: dict):
    import pandas as pd
    rows = []
    for learner in scenario['roster']:
        encounters = [e for e in scenario['encounters'] if e['learner_id'] == learner['learner_id']]
        values, _ = learner_changes([learner], encounters)
        change = values[learner['arm']]
        rows.append({'Learner': learner['learner_id'], 'Arm': learner['arm'],
                     'Encounter count': len(encounters), 'Change': change[0] if change else None,
                     'Analyzed': bool(change)})
    return pd.DataFrame(rows)


def permutation_distribution(scenario: dict, result: dict) -> list[float]:
    """Recreate the frozen plan's null draws for visualization, without refitting outcomes."""
    if digest(scenario) != result['input_sha256'] or digest(result['plan']) != result['plan_sha256']:
        raise ValueError('plot requires the original frozen scenario and plan')
    values, _ = learner_changes(scenario['roster'], scenario['encounters'])
    a, b = values['feedback'], values['standard']
    if len(a) < 2 or len(b) < 2:
        raise ValueError('two scored learners per arm required')
    rng = random.Random(result['plan']['seed'])
    draws = []
    for _ in range(result['plan']['draws']):
        shuffled = rng.sample(a + b, len(a) + len(b))
        draws.append(mean(shuffled[:len(a)]) - mean(shuffled[len(a):]))
    return draws


def _style(ax, title: str, xlabel: str = '', ylabel: str = ''):
    ax.set_title(title, loc='left', fontsize=14, fontweight='bold', pad=14)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    for spine in ('top', 'right'):
        ax.spines[spine].set_visible(False)
    ax.grid(axis='y', alpha=.15)
    ax.set_axisbelow(True)


def plot_pipeline(report: dict):
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    fig, ax = plt.subplots(figsize=(12, 3.1), layout='constrained')
    labels = [('Patient Studio', 'Authored facts\nSource-backed auto-fill'), ('Encounter', 'Scripted student\nProgressive disclosure'),
              ('Reply check', 'Approved source IDs\nSafe fallback'), ('Debrief', 'Transcript evidence\nProvisional rubric'),
              ('Follow-up', 'Authored branches\nVisit 2')]
    for i, (name, detail) in enumerate(labels):
        x = i * 2.35
        ax.add_patch(FancyBboxPatch((x, .65), 2.05, 1.3, boxstyle='round,pad=.06', facecolor='#eff6ff', edgecolor=COLORS['blue']))
        ax.text(x + 1.02, 1.63, name, ha='center', fontsize=12, fontweight='bold')
        ax.text(x + 1.02, 1.12, detail, ha='center', fontsize=10)
        if i < 4:
            ax.annotate('', xy=(x + 2.31, 1.3), xytext=(x + 2.08, 1.3), arrowprops={'arrowstyle': '->', 'color': COLORS['gray']})
    ax.set(xlim=(-.2, 11.8), ylim=(0, 2.5))
    ax.set_title(f"Actual offline backend rehearsal: {report['api'].get('requests', 0)} HTTP requests · {report['api']['status']}", loc='left', fontsize=15, fontweight='bold')
    ax.axis('off')
    fig.text(.02, .01, 'Disposable SQLite database. Text is the test interface; microphone and voice services are not exercised.', fontsize=10)
    return fig


def plot_actions(report: dict):
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout='constrained')
    counts = report['actions']['annotation_counts']
    splits = ['train', 'validation', 'test']
    bars = axes[0].bar(['Development', 'Validation\n(unused)', 'Held-out\nsynthetic groups'], [counts[s] for s in splits], color=[COLORS['blue'], COLORS['gray'], COLORS['teal']])
    axes[0].bar_label(bars, padding=3)
    axes[0].set_ylim(0, max(counts.values()) * 1.18)
    _style(axes[0], 'Exact-span annotation allocation', ylabel='Synthetic whole-sentence spans')
    models = ['Keyword rules', 'Trained baseline']
    metrics = [report['actions'][k]['macro_f1_over_observed_labels'] for k in ('keyword_sentence_classifier', 'trained_sentence_classifier')]
    bars = axes[1].bar(models, metrics, color=[COLORS['blue'], COLORS['teal']])
    axes[1].bar_label(bars, fmt='%.2f', padding=3)
    axes[1].set_ylim(0, 1.15)
    _style(axes[1], 'Shared-template comparison only', ylabel='Macro-F1 (0 to 1)')
    fig.suptitle('SIMULATED LABELS · perfect template scores do not establish clinical performance', color=COLORS['amber'], fontsize=11)
    return fig


def plot_reviews(report: dict):
    import matplotlib.pyplot as plt
    batches = report['reviews']['batches']
    kinds = list(batches)
    labels = [{'action': 'Student actions', 'claim': 'Feedback claims', 'domain': 'Rubric ratings',
               'release': 'Fact disclosure', 'semantic': 'Reply support'}[k] for k in kinds]
    fig, ax = plt.subplots(figsize=(10, 4.5), layout='constrained')
    agreement = [batches[k]['paired_agreement'] for k in kinds]
    disagreements = [batches[k]['disagreements'] for k in kinds]
    ax.barh(labels, agreement, label='Synthetic A/B agreements', color=COLORS['teal'])
    ax.barh(labels, disagreements, left=agreement, label='Synthetic disagreements', color=COLORS['amber'])
    for i, k in enumerate(kinds):
        ax.text(agreement[i] + disagreements[i] + 2, i, str(batches[k]['tasks']), va='center')
    _style(ax, 'Reference transport: agreements and disagreements', xlabel='Provisional review items')
    ax.set_xlim(0, max(b['tasks'] for b in batches.values()) * 1.25)
    ax.legend(loc='lower right')
    fig.suptitle('CORRELATED SYNTHETIC SOURCES · this is not inter-rater reliability among clinicians', fontsize=11, color=COLORS['amber'])
    return fig


def plot_difficulty(report: dict):
    import matplotlib.pyplot as plt
    rows = report['difficulty']['discoveries']
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), layout='constrained', sharey=True)
    presets = ['straightforward', 'typical', 'difficult']
    for ax, cid in zip(axes, sorted({r['case_id'] for r in rows})):
        for level, color in zip(('novice', 'competent', 'expert'), (COLORS['amber'], COLORS['blue'], COLORS['teal'])):
            row = next(r for r in rows if r['case_id'] == cid and r['scripted_level'] == level)
            ax.plot(presets, [row[p] for p in presets], marker='o', label=level + ' script', color=color)
        _style(ax, cid.replace('_', ' ').title(), ylabel='Authored facts discovered')
        ax.tick_params(axis='x', rotation=20)
    axes[-1].legend(fontsize=9)
    fig.suptitle('SCRIPTED MECHANICS · estimated threshold offsets; not observed learner difficulty', fontsize=11, color=COLORS['amber'])
    return fig


def plot_learner_changes(scenario: dict):
    import matplotlib.pyplot as plt
    table = learner_table(scenario)
    fig, ax = plt.subplots(figsize=(10, 4.5), layout='constrained')
    for pos, arm, color in [(0, 'standard', COLORS['gray']), (1, 'feedback', COLORS['blue'])]:
        rows = table[(table['Arm'] == arm) & table['Analyzed']]
        jitter = [((i % 5) - 2) * .045 for i in range(len(rows))]
        ax.scatter([pos + j for j in jitter], rows['Change'], s=65, color=color, alpha=.8)
        ax.plot([pos - .25, pos + .25], [rows['Change'].mean()] * 2, color=color, linewidth=3)
    ax.axhline(0, color=COLORS['gray'], linewidth=1, linestyle='--')
    ax.set_xticks([0, 1], ['Standard arm', 'Feedback arm'])
    _style(ax, 'One dot = one invented learner', ylabel='Mean rubric-point change (follow-up − baseline)')
    fig.suptitle('SYNTHETIC OUTCOMES · assumed benefit; dots are not backend-derived clinical grades', fontsize=11, color=COLORS['amber'])
    return fig


def plot_permutation(scenario: dict, result: dict):
    import matplotlib.pyplot as plt
    values = permutation_distribution(scenario, result)
    effect = result['statistics']['effect']
    fig, ax = plt.subplots(figsize=(10, 4.5), layout='constrained')
    ax.hist(values, bins=35, color=COLORS['blue'], alpha=.7, label='Shuffled learner assignments')
    ax.axvline(effect, color=COLORS['red'], linewidth=2.5, label=f'Invented observed effect: {effect:.2f}')
    ax.axvline(-abs(effect), color=COLORS['red'], linewidth=1.5, linestyle='--')
    _style(ax, 'How often does shuffling produce a difference this large?', xlabel='Feedback minus standard learner change', ylabel='Permutation draws')
    ax.legend(fontsize=10)
    ax.text(.02, .97, f"Two-sided p = {result['statistics']['p_value']:.4f}\n{len(values):,} draws · seed {result['plan']['seed']}", transform=ax.transAxes, va='top', bbox={'facecolor': 'white', 'alpha': .9, 'edgecolor': '#cbd5e1'})
    fig.suptitle('ARITHMETIC DEMONSTRATION · p is not the probability that treatment works', fontsize=11, color=COLORS['amber'])
    return fig


def plot_mcpt(report: dict):
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout='constrained')
    for i, (name, row) in enumerate(report['mcpt'].items()):
        stats = row['statistics']
        lo, hi = stats['effect_ci95']
        axes[0].plot([lo, hi], [i, i], color=COLORS['blue'], linewidth=3)
        axes[0].scatter(stats['effect'], i, color=COLORS['blue'], s=55)
        axes[0].text(hi + .07, i, f"p={stats['p_value']:.4f}", va='center', fontsize=9)
        denom = row['denominators']
        for j, arm in enumerate(('standard', 'feedback')):
            scored, assigned = denom['scored_by_arm'][arm], denom['roster_by_arm'][arm]
            axes[1].barh(i + (j-.5)*.32, scored, height=.28, color=COLORS['gray'] if arm == 'standard' else COLORS['teal'], label=arm if i == 0 else None)
            axes[1].barh(i + (j-.5)*.32, assigned-scored, left=scored, height=.28, color='#e2e8f0')
    names = [n.replace('_', ' ') for n in report['mcpt']]
    for ax in axes:
        ax.set_yticks(range(len(names)), names)
        ax.invert_yaxis()
    axes[0].axvline(0, color=COLORS['gray'], linestyle='--')
    axes[0].set_xlim(-1.7, 2.6)
    _style(axes[0], 'Effects with descriptive bootstrap intervals', xlabel='Mean rubric-point change difference')
    _style(axes[1], 'Keep assigned learners in denominators', xlabel='Learners (pale = unavailable outcome)')
    axes[1].legend(loc='lower right')
    fig.suptitle('FIVE SYNTHETIC CONTROLS · effects follow invented scores and clipping assumptions', fontsize=11, color=COLORS['amber'])
    return fig


def load_live_files(report_path: Path, trace_path: Path) -> tuple[dict, dict, dict]:
    report = json.loads(private_path(report_path).read_text())
    raw = private_path(trace_path).read_bytes()
    trace = json.loads(gzip.decompress(raw) if trace_path.suffix == '.gz' else raw)
    if report['version'] != trace['version'] or report['mode'] != trace['mode']:
        raise ValueError('live report/trace identity mismatch')
    calls = [c for run in trace['runs'] for turn in run['turns'] for c in turn['llm_calls']]
    calls += [c for row in trace['challenges'] for c in row['llm_calls']]
    if len(calls) != report['usage_and_cost']['model_calls']:
        raise ValueError('live call denominators differ')
    counts = Counter(bool(c['ok']) for c in calls)
    failures = Counter((c.get('error') or 'UnknownError').split(':', 1)[0] for c in calls if not c['ok'])
    status = 'NOT EVALUABLE' if report['mode'] != 'live' or not calls else 'FAILED' if not counts[True] else 'PARTIAL' if counts[False] else 'LIVE EXECUTED'
    summary = {'Execution': status, 'Successful model attempts': counts[True], 'Failed model attempts': counts[False],
               'Failure categories': dict(failures), 'Template fallback replies': report['delivered']['fallback_replies'],
               'Total delivered replies': report['delivered']['replies'], 'Clinical interpretation': 'Unreviewed authored probe; no clinical accuracy claim'}
    return report, trace, summary


def plot_live(trace: dict):
    import matplotlib.pyplot as plt
    calls = [c for run in trace['runs'] for turn in run['turns'] for c in turn['llm_calls']]
    calls += [c for row in trace['challenges'] for c in row['llm_calls']]
    purposes = sorted({c['purpose'] for c in calls})
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), layout='constrained')
    ok = [sum(c['purpose'] == p and c['ok'] for c in calls) for p in purposes]
    failed = [sum(c['purpose'] == p and not c['ok'] for c in calls) for p in purposes]
    axes[0].bar(purposes, ok, color=COLORS['teal'], label='Successful attempt')
    axes[0].bar(purposes, failed, bottom=ok, color=COLORS['red'], label='Failed attempt')
    _style(axes[0], 'Live model attempts, including retries', ylabel='Attempts')
    axes[0].legend()
    timings = [t['latency_ms'] for run in trace['runs'] for t in run['turns']]
    axes[1].hist(timings, bins=15, color=COLORS['blue'])
    _style(axes[1], 'Measured text-turn latency', xlabel='Milliseconds per turn', ylabel='Authored turns')
    fig.suptitle('LIVE SERVICE OBSERVATIONS · voice first-audio latency and clinical accuracy remain unmeasured', fontsize=11, color=COLORS['amber'])
    return fig


def run_live_probe(directory: Path, pricing: Path | None = None) -> tuple[dict, dict, dict]:
    """Fresh process reads local .env; preserve logs privately and show failed calls."""
    directory = private_path(directory)
    if directory.exists():
        raise ValueError('use a new live output directory')
    directory.mkdir(parents=True, mode=0o700)
    report_path, trace_path = directory / 'live_report.json', directory / 'live_trace.json.gz'
    command = [sys.executable, '-m', 'backend_kelsch.scripts.eval_live_grounding', '--live',
               '--report', str(report_path), '--traces', str(trace_path)]
    if pricing:
        command += ['--pricing', str(private_path(pricing))]
    env = os.environ.copy()
    env['LLM_ENABLED'] = 'true'
    env['PYTHONPATH'] = os.pathsep.join([str(ROOT / 'backend'), str(ROOT), env.get('PYTHONPATH', '')])
    with (directory / 'live_process.log').open('w') as log:
        try:
            proc = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=1200)
        except subprocess.TimeoutExpired:
            return {}, {}, {'Execution': 'NOT EVALUABLE', 'Reason': 'Live process timed out; inspect private live_process.log'}
    if not report_path.exists() or not trace_path.exists():
        return {}, {}, {'Execution': 'NOT EVALUABLE', 'Process exit code': proc.returncode,
                        'Reason': 'No complete live report/trace; inspect private live_process.log'}
    report, trace, summary = load_live_files(report_path, trace_path)
    summary['Process exit code'] = proc.returncode
    if proc.returncode and summary['Execution'] == 'LIVE EXECUTED':
        summary['Execution'] = 'FAILED MECHANICAL CHECK'
    return report, trace, summary
