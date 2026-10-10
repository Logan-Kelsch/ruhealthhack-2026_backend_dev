"""Development comparisons and completion ledger; clinical gates remain separate."""
from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
import gzip
import json
from math import ceil
from statistics import mean, median

from app.encounter.classifier import keyword_classify
from app.schemas.case import Case
from backend_kelsch.app.debrief_probe.evaluation import ROOT, run_all
from backend_kelsch.app.grounding.evaluation import encounter_runs, _case
from backend_kelsch.app.study.analysis import quadratic_kappa, wilson
from backend_kelsch.app.study.development_reference import read_source, normalize_answer
from backend_kelsch.app.study.protocol import digest


def confusion(pairs: list[tuple[bool, bool]]) -> dict:
    counts = Counter('tp' if truth and pred else 'fn' if truth else 'fp' if pred else 'tn' for truth, pred in pairs)
    tp, fp, fn, tn = (counts[k] for k in ('tp', 'fp', 'fn', 'tn'))
    return {'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn, 'denominator': len(pairs),
            'precision': wilson(tp, tp + fp), 'recall': wilson(tp, tp + fn),
            'agreement': wilson(tp + tn, len(pairs)),
            'interval_warning': 'Wilson intervals are descriptive; repeated turns and cases are correlated.'}


def label_metrics(truth: list[set], predicted: list[set], critical: list[str]) -> dict:
    if len(truth) != len(predicted):
        raise ValueError('prediction and reference denominators differ')
    labels = sorted(set().union(*truth, *predicted, set(critical)))
    scores = {label: confusion([(label in a, label in b) for a, b in zip(truth, predicted)]) for label in labels}
    observed = [v for v in scores.values() if v['tp'] + v['fn'] + v['fp']]
    f1 = [2*v['tp']/(2*v['tp'] + v['fp'] + v['fn']) for v in observed]
    return {'units': len(truth), 'macro_f1_over_observed_labels': mean(f1) if f1 else None,
            'per_label': scores, 'critical_recall': {l: {'positive_support': scores[l]['tp'] + scores[l]['fn'],
                'recall': scores[l]['recall'], 'adequacy': 'ENOUGH FIXTURE POSITIVES' if scores[l]['tp'] + scores[l]['fn'] >= 10 else 'NOT EVALUABLE'} for l in critical}}


def prediction_comparison(reference: dict) -> dict | None:
    """Same adapter for release, action, feedback claims, and rubric predictions."""
    if 'predictions' not in reference['config']:
        return None
    _, raw = read_source(reference['base'], reference['config']['predictions'])
    rows = json.loads(raw)
    index = {r['packet_id']: r for r in rows}
    if len(index) != len(rows) or set(index) != set(reference['resolved']):
        raise ValueError('predictions must cover exactly the resolved reference task IDs')
    by_kind = defaultdict(list)
    for pid, row in index.items():
        if not row.get('model_id') or not row.get('prompt_version'):
            raise ValueError('prediction model and prompt provenance required')
        task = reference['tasks'][pid]
        by_kind[task['kind']].append((reference['resolved'][pid]['answer'], normalize_answer(task, row['answer'])))
    metrics = {}
    for kind, pairs in by_kind.items():
        if kind in {'semantic', 'claim'}:
            metrics[kind] = confusion([(a['expected_supported'], b['expected_supported']) for a, b in pairs])
        elif kind == 'release':
            truth, predicted = ([set(a['expected_fact_ids']) for a, _ in pairs], [set(b['expected_fact_ids']) for _, b in pairs])
            metrics[kind] = label_metrics(truth, predicted, [])
        elif kind == 'domain':
            numeric = [(a['score'], b['score']) for a, b in pairs if a['score'] != 'N/A' and b['score'] != 'N/A']
            metrics[kind] = {'total_pairs': len(pairs), 'numeric_pairs': len(numeric),
                'na_mismatches': sum((a['score'] == 'N/A') != (b['score'] == 'N/A') for a, b in pairs),
                'mean_absolute_error': mean(abs(a-b) for a,b in numeric) if numeric else None,
                'quadratic_kappa': quadratic_kappa(numeric), 'confidence_interval': None}
        elif kind == 'action':
            # Score exact span+label tuples. A correct label at a wrong span is a miss.
            def labels(answer):
                return {(a['start'], a['end'], label) for a in answer['annotations'] for label in a['labels']}
            tp = fp = fn = 0
            critical = Counter()
            for a, b in pairs:
                truth, pred = labels(a), labels(b)
                tp += len(truth & pred); fp += len(pred-truth); fn += len(truth-pred)
                for label in ('safety_netting', 'prescribe_antibiotic', 'start_medication'):
                    critical[(label, 'positive')] += sum(x[2] == label for x in truth)
                    critical[(label, 'hit')] += sum(x[2] == label for x in truth & pred)
            metrics[kind] = {'tp': tp, 'fp': fp, 'fn': fn, 'span_unit': 'exact start/end plus action label',
                'critical_recall': {l: wilson(critical[(l, 'hit')], critical[(l, 'positive')]) for l in ('safety_netting', 'prescribe_antibiotic', 'start_medication')}}
    return {'scope': 'replaceable development reference, not faculty validation', 'metrics': metrics,
        'model_ids': sorted({r['model_id'] for r in rows}), 'prompt_versions': sorted({r['prompt_version'] for r in rows}),
        'held_out': False, 'reason': 'Source hash pins predictions but cannot prove they were made without reference access. Use existing grouped action-data training workflow for held-out evaluation.'}


def extraction_probe(trace: dict) -> dict:
    """Compare keyword and logged classifier outputs to authored fixture inputs only."""
    critical = ['safety_netting', 'prescribe_antibiotic', 'start_medication']
    rows = [(run, row) for run in trace['runs'] for row in run['turns']]
    cases = {run['case_id']: _case(run['case_id'])[0] for run in trace['runs']}
    result = {'scope': 'AUTHORED FIXTURE AGREEMENT; no reviewed held-out action data',
              'trained_action_extraction': 'NOT EVALUABLE', 'held_out': False,
              'reason': 'Repeated scripted utterances are regression probes, not independent learner labels.'}
    for namespace in ('topics', 'actions'):
        truth, baseline, logged = [], [], []
        for run, row in rows:
            key = namespace
            truth.append({h['id'] for h in row['authored_fixture_intent'][key]})
            baseline.append({h['id'] for h in keyword_classify(row['utterance'], cases[run['case_id']]).model_dump()[key]})
            logged.append({h['id'] for h in row['classified_intent'][key]})
        result[namespace] = {'keyword': label_metrics(truth, baseline, critical if namespace == 'actions' else []),
                             'logged_classifier': label_metrics(truth, logged, critical if namespace == 'actions' else [])}
    return result


def critical_action_probes() -> dict:
    path = ROOT / 'backend_kelsch/app/data/development_action_probes_v1.json'
    fixture = json.loads(path.read_text())
    truth, predictions, failures = [], [], []
    critical = {'safety_netting', 'prescribe_antibiotic', 'start_medication'}
    for row in fixture['probes']:
        case, _ = _case(row['case_id'])
        expected = set(row['expected_actions'])
        predicted = keyword_classify(row['text'], case).action_ids() & critical
        truth.append(expected); predictions.append(predicted)
        if expected != predicted:
            failures.append({'probe_id': row['id'], 'unexpected': sorted(predicted-expected), 'missed': sorted(expected-predicted)})
    return {'scope': fixture['generation'], 'fixture_sha256': sha256(path.read_bytes()).hexdigest(),
        'vocabulary_sha256': sha256((ROOT / fixture['vocabulary_source']).read_bytes()).hexdigest(),
        'keyword_classifier': label_metrics(truth, predictions, ['safety_netting', 'prescribe_antibiotic', 'start_medication']),
        'failure_examples': failures, 'development_regression': 'FAIL' if failures else 'PASS',
        'trained_or_held_out_accuracy': 'NOT EVALUABLE',
        'followup': 'Explicit negation is covered only by narrow keyword guards. Broader uncertainty and contextual intent still need reviewed held-out data; do not train on these eight probes.'}


def live_comparison(reference: dict) -> dict:
    config, base = reference['config'], reference['base']
    _, raw = read_source(base, config['trace'])
    trace = json.loads(gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw)
    _, raw = read_source(base, config['mapping'])
    mapping = json.loads(raw)
    if len(mapping) != len(reference['tasks']) or {r['packet_id'] for r in mapping} != set(reference['tasks']):
        raise ValueError('live mapping must cover each task exactly once')
    runs = {r['script_id']: r for r in trace['runs']}
    if len(runs) != len(trace['runs']):
        raise ValueError('duplicate trace script')
    challenges = {r['challenge_id']: r for r in trace['challenges']}
    if len(challenges) != len(trace['challenges']):
        raise ValueError('duplicate trace challenge')
    delivered, judged, failures = [], [], []
    mechanically_blocked = unresolved = 0
    for link in mapping:
        pid, key = link['packet_id'], link['private_source_key']
        task = reference['tasks'][pid]
        if task['kind'] != 'semantic':
            raise ValueError('live comparison supports semantic tasks only')
        if key[0] == 'delivered':
            candidates = [t for t in runs[key[1]]['turns'] if t['turn'] == key[2]]
            if len(candidates) != 1:
                raise ValueError('trace turn missing or duplicated')
            row = candidates[0]
            source, text = runs[key[1]]['case_source'], row['delivered_reply']
        elif key[0] == 'candidate':
            row = challenges[key[1]]
            source, text = row['case_source'], row['reply']
        else:
            raise ValueError('unknown live mapping type')
        if source['sha256'] != task['case_sha256'] or text != task['context']['reply']:
            raise ValueError('trace/task case or reply mismatch')
        label = reference['resolved'].get(pid)
        if label is None:
            unresolved += 1
            continue
        supported = label['answer']['expected_supported']
        if key[0] == 'delivered':
            delivered.append(supported)
            if not supported:
                failures.append({'packet_id': pid, 'category': 'delivered_unsupported_against_reference'})
        elif row['deterministic_blocked']:
            mechanically_blocked += 1
        elif row['llm_judge']['status'] == 'EVALUATED':
            predicted = not bool(row['llm_judge']['problems'])
            judged.append((supported, predicted))
            if supported != predicted:
                failures.append({'packet_id': pid, 'category': 'judge_false_reject' if supported else 'judge_false_accept'})
        else:
            unresolved += 1
    turns = [t for r in trace['runs'] for t in r['turns']]
    calls = [c for row in turns + trace['challenges'] for c in row['llm_calls']]
    latency = sorted(t['latency_ms']['total'] for t in turns)
    costs = [c.get('estimated_cost_usd') for c in calls]
    return {'scope': 'DEVELOPMENT REFERENCE; not human accuracy or clinical approval',
        'delivered': {'reviewed': len(delivered), 'supported': sum(delivered), 'unsupported': len(delivered)-sum(delivered),
            'supported_rate': wilson(sum(delivered), len(delivered)),
            'interpretation': 'Support of final delivered wording, including templates; not verifier sensitivity.'},
        'candidate_judge_only': confusion(judged), 'mechanically_blocked_excluded_from_judge_comparison': mechanically_blocked,
        'unresolved_or_unjudged': unresolved, 'failure_examples': failures,
        'operations': {'turns': len(turns), 'fallbacks': sum(t['fallback_used'] for t in turns),
            'model_calls': len(calls), 'failed_calls': sum(not c['ok'] for c in calls),
            'model_ids': sorted({c['model'] for c in calls}),
            'prompt_versions': sorted({f"{c['prompt']}:{c['prompt_version']}" for c in calls}),
            'text_pipeline_latency_ms': {'median': median(latency) if latency else None,
                'p90_nearest_rank': latency[max(0, ceil(.9*len(latency))-1)] if latency else None},
            'voice_commit_to_first_audio': 'NOT EVALUABLE',
            'cost_usd': sum(costs) if costs and all(c is not None for c in costs) else None,
            'cost_status': 'KNOWN' if costs and all(c is not None for c in costs) else 'UNKNOWN'},
        'extraction_fixture_comparison': extraction_probe(trace)}


def reviewed_domain_agreement(reference: dict) -> dict:
    """N/A stays separate; scores are never inferred from semantic labels."""
    pairs = defaultdict(list)
    na = Counter()
    for pid, task in reference['tasks'].items():
        if task['kind'] != 'domain':
            continue
        a, b = [reference['submissions'][s].get(pid) for s in ('a', 'b')]
        if not a or not b:
            continue
        domain = task['context'].get('domain_id') or task['context']['domain']['id']
        scores = (a['answer']['score'], b['answer']['score'])
        if 'N/A' in scores:
            na[str(domain)] += 1
        else:
            pairs[str(domain)].append(scores)
    return {'scope': 'declared reference sources; reviewer authority not verified',
            'domains': {d: {'numeric_pairs': len(v), 'quadratic_kappa': quadratic_kappa(v)} for d, v in pairs.items()},
            'pairs_with_na_by_domain': dict(na), 'confidence_intervals': None,
            'reason': 'No cluster-aware confidence interval or faculty agreement gate from this development adapter.'}


def mechanics() -> dict:
    runs, engine = encounter_runs()
    grouped = defaultdict(dict)
    for run in runs:
        grouped[(run['case_id'], run['level'])][run['preset']] = run['discovery_count']
    ordered = all(v['straightforward'] >= v['typical'] >= v['difficult'] for v in grouped.values())
    immutable = []
    from backend_kelsch.app.patient_environment.runner import with_probe_preset
    for cid in sorted({r['case_id'] for r in runs}):
        case, _ = _case(cid)
        original = case.model_dump()
        for preset in ('straightforward', 'typical', 'difficult'):
            changed = with_probe_preset(case, preset).model_dump()
            immutable.append(all(changed[k] == original[k] for k in original if k not in {'trust', 'difficulty'}))
            immutable.append(all(changed['trust'][k] == original['trust'][k] for k in original['trust'] if k != 'thresholds'))
    debrief, _ = run_all()
    return {'scope': 'AUTHORED MECHANICS ONLY', 'case_source_hashes': {cid: _case(cid)[1]['sha256'] for cid in sorted({r['case_id'] for r in runs})},
        'difficulty': {'runs': len(runs), 'clinical_content_unchanged': all(immutable), 'nonincreasing_discoveries': ordered,
            'straightforward_minus_difficult_mean': mean(v['straightforward']-v['difficult'] for v in grouped.values()),
            'status': 'PASS' if ordered and all(immutable) else 'FAIL',
            'clinical_calibration': 'NOT EVALUABLE', 'learner_effect': 'NOT EVALUABLE',
            'discovery_counts': [{'case_id': cid, 'authored_level': level, **v} for (cid, level), v in grouped.items()]},
        'engine': engine['counts'], 'feedback_and_progression': {'gates': debrief['gates'], 'counts': debrief['counts'], 'na_probe': debrief['na_probe']},
        'status': 'PASS' if ordered and all(immutable) and not engine['violations'] and debrief['gates']['evidence_linkage_and_replay'] == 'PASS' else 'FAIL'}


def completion_report(reference: dict | None = None) -> dict:
    report = {'version': 'development_completion_v1', 'mode': 'development_only',
        'implementation_sha256': {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in (
            'backend_kelsch/app/study/development_reference.py', 'backend_kelsch/app/study/development_evaluation.py',
            'backend_kelsch/app/study/permutation.py', 'backend_kelsch/scripts/eval_development.py',
            'backend/app/encounter/phraser.py', 'backend/app/encounter/classifier.py', 'backend/app/prompts/phraser.md')},
        'review_reference': reference['summary'] if reference else None,
        'mechanics': mechanics(), 'domain_reference_agreement': reviewed_domain_agreement(reference) if reference else None,
        'critical_action_fixture_probes': critical_action_probes(),
        'live_reference_comparison': live_comparison(reference) if reference and 'trace' in reference['config'] else None,
        'prediction_reference_comparison': prediction_comparison(reference) if reference else None,
        'human_gates': {name: 'NOT EVALUABLE' for name in ('semantic_grounding', 'clinical_case_approval',
            'clinical_disclosure_accuracy', 'trained_action_extraction', 'faculty_feedback_accuracy',
            'faculty_rubric_agreement', 'difficulty_calibration', 'approval_and_consent', 'student_learning')},
        'remaining_input': ['Qualified independent reviews and case/disclosure approval',
            'Reviewed action labels on whole-case/family held-out data; sufficient critical positives',
            'Double-rated feedback claims and rubric domains', 'Approved full difficulty presets and actual learner observations',
            'Integrated voice latency and configured pricing', 'Authorized consented learner study and frozen analysis plan']}
    ready = bool(reference and reference['summary']['pending_count'] == 0)
    report['development_gates'] = {'reference_transport': 'PASS' if ready else 'NOT EVALUABLE',
        'mechanical_regression': report['mechanics']['status'],
        'critical_action_fixture_regression': report['critical_action_fixture_probes']['development_regression'],
        'provisional_delivered_support': 'NOT EVALUABLE', 'candidate_judge_comparison': 'NOT EVALUABLE'}
    live = report['live_reference_comparison']
    if ready and live:
        report['development_gates']['provisional_delivered_support'] = 'PASS' if live['delivered']['unsupported'] == 0 else 'FAIL'
        judged = live['candidate_judge_only']
        if judged['denominator']:
            report['development_gates']['candidate_judge_comparison'] = 'PASS' if judged['fp'] == judged['fn'] == 0 else 'FAIL'
    report['report_sha256'] = digest(report)
    return report
