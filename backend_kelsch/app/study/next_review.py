"""Fresh development review batches; authored encounters are never learner outcomes."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from app.encounter.classifier import keyword_classify
from app.feedback.debrief import build_debrief
from app.schemas.case import Case
from backend_kelsch.app.debrief_probe.evaluation import ROOT, CASES, run_all, scenarios
from backend_kelsch.app.patient_environment.runner import run_script, with_probe_preset
from backend_kelsch.app.study.development_reference import answers, load_reference, normalize_answer, read_source
from backend_kelsch.app.study.development_evaluation import prediction_comparison, reviewed_domain_agreement
from backend_kelsch.app.study.protocol import digest
from backend_kelsch.app.study.workflow import approved_case, private_path, save, write_private, TEMPLATE

CRITICAL = ('safety_netting', 'prescribe_antibiotic', 'start_medication')


def source_lock() -> dict:
    """Pin current code, vocabularies, prompts, rubric and authored inputs, not old reports."""
    paths = list((ROOT / 'backend/app').rglob('*.py'))
    for directory in ('backend/app/prompts', 'backend/app/vocab', 'backend/app/data'):
        paths += [p for p in (ROOT / directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    paths += [ROOT / 'cases' / (cid + '.json') for cid in CASES]
    paths += [ROOT / p for p in (
        'backend_kelsch/app/data/action_annotation_vocab.json',
        'backend_kelsch/app/data/development_action_probes_v1.json',
        'backend_kelsch/app/debrief_probe/evaluation.py',
        'backend_kelsch/app/patient_environment/runner.py',
        'backend_kelsch/app/study/next_review.py',
        'backend_kelsch/app/study/development_reference.py',
        'backend_kelsch/app/study/development_evaluation.py',
        'backend_kelsch/app/study/workflow.py',
        'backend_kelsch/app/study/review.py',
        'backend_kelsch/app/study/reviewer.html',
        'backend_kelsch/scripts/eval_next_review.py')]
    return {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}


def action_prediction(text: str, case: Case) -> tuple[dict, list]:
    """Preserve exact classifier spans; never guess offsets for normalized/ambiguous text."""
    vocab = json.loads((ROOT / 'backend_kelsch/app/data/action_annotation_vocab.json').read_text())['student_skill']
    spans, dropped = {}, []
    for hit in keyword_classify(text, case).actions:
        if hit.id not in vocab:
            dropped.append({'label': hit.id, 'reason': 'outside locked research vocabulary'})
            continue
        if text.count(hit.span) != 1:
            dropped.append({'label': hit.id, 'reason': 'span absent or ambiguous'})
            continue
        start = text.index(hit.span)
        spans.setdefault((start, start + len(hit.span)), set()).add(hit.id)
    annotations = [{'start': a, 'end': b, 'span': text[a:b], 'labels': sorted(labels), 'rubric_mapping': []}
                   for (a, b), labels in sorted(spans.items())]
    if not annotations:
        annotations = [{'start': 0, 'end': len(text), 'span': text, 'labels': ['other'], 'rubric_mapping': []}]
    return {'annotations': annotations}, dropped


def render_tasks(path: Path, tasks: list, manifest: dict, slot: str, pairs: dict | None = None) -> None:
    data = {'manifest': manifest, 'slot': slot, 'tasks': tasks}
    if pairs is not None:
        data['independent_answers'] = pairs
    encoded = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c').replace('&', '\\u0026')
    write_private(path, TEMPLATE.read_text().replace('__DATA__', encoded))


def prepare_next(workspace: Path) -> dict:
    workspace = private_path(workspace)
    if workspace.exists():
        raise ValueError('use a new workspace; never overwrite a frozen review batch')
    sources = source_lock()
    lock = digest({'stage': 'next_review_v1', 'sources': sources})
    rubric = json.loads((ROOT / 'backend/app/data/rubric_shp_v1.json').read_text())
    vocab = json.loads((ROOT / 'backend_kelsch/app/data/action_annotation_vocab.json').read_text())['student_skill']
    cases = {cid: Case.model_validate_json((ROOT / 'cases' / (cid + '.json')).read_text()) for cid in CASES}
    _, records = run_all()
    batches = {k: [] for k in ('action', 'claim', 'domain')}
    predictions = {k: [] for k in batches}
    dropped = []

    def add(kind, key, cid, context, units, answer, model, mapping):
        case_hash = sources['cases/' + cid + '.json']
        pid = digest([lock, kind, key])[:24]
        packet = {'case_id': cid, 'case_sha256': case_hash}
        task = {'packet_id': pid, 'kind': kind, 'protocol_lock': lock, 'case_sha256': case_hash,
                'case_version': cases[cid].version, 'case': approved_case(packet),
                'context': context, 'text_units': units}
        batches[kind].append(task)
        predictions[kind].append({'packet_id': pid, 'answer': answer, 'model_id': model,
                                 'prompt_version': 'not_applicable_rule_based', 'source_mapping': mapping})

    unique = {}
    probes = json.loads((ROOT / 'backend_kelsch/app/data/development_action_probes_v1.json').read_text())
    for p in probes['probes']:
        unique.setdefault((p['case_id'], p['text']), []).append('critical_probe:' + p['id'])
    for r in records:
        for t in r['transcript']:
            unique.setdefault((r['case_id'], t['student_text']), []).append(r['scenario'] + ':' + str(t['idx']))
    for (cid, text), origins in sorted(unique.items()):
        answer, omissions = action_prediction(text, cases[cid])
        dropped += [{'case_id': cid, **o} for o in omissions]
        add('action', [cid, text], cid,
            {'text': text, 'speaker': 'student', 'turn_id': '1', 'namespace': 'student_skill', 'vocabulary': vocab},
            [{'turn': 1, 'speaker': 'student', 'text': text}], answer, 'keyword_baseline', {'origins': origins})
    for r in records:
        cid = r['case_id']
        transcript = [{'turn': t['idx'], 'student': t['student_text'], 'patient': t['reply_text']} for t in r['transcript']]
        units = [{'turn': t['turn'], 'speaker': speaker, 'text': t[speaker]}
                 for t in transcript for speaker in ('student', 'patient')]
        # Notes are separate exact-context units, not student utterances or outcome scores.
        note_units = [{'turn': 0, 'speaker': 'note:' + field, 'text': text} for field, text in r['note'].items()]
        for i, claim in enumerate(r['claims']):
            candidate = {k: claim[k] for k in ('kind', 'label', 'text', 'domain_id', 'evidence') if k in claim}
            add('claim', [cid, r['scenario'], i], cid,
                {'transcript': transcript, 'documentation': r['note'], 'candidate_claim': candidate,
                 'note': 'Judge this emitted claim independently. An exact citation alone does not establish support.'},
                units + note_units, {'expected_supported': True}, 'emitted_claim_support_assumption',
                {'case_id': cid, 'scenario': r['scenario'], 'claim_index': i})
        trace = run_script(cases[cid], scenarios(cid)[r['scenario']])
        raw, calls = build_debrief(cases[cid], cases[cid].visit('v1'), r['transcript'], trace['final_state'], r['note'], False)
        assert not calls
        by_id = {d['id']: d for d in raw['rubric']['domains']}
        for domain in rubric['domains']:
            score = by_id[domain['id']]['score']
            answer = {'score': score}
            if score == 'N/A':
                answer['na_reason'] = 'Rule-based scorer found no applicable reasoning signals.'
            add('domain', [cid, r['scenario'], domain['id']], cid,
                {'transcript': transcript, 'domain': domain, 'domain_id': domain['id'],
                 'student_role': cases[cid].briefing.student_role, 'goal': cases[cid].briefing.goal,
                 'objectives': [o.text for o in cases[cid].objectives]},
                units, answer, 'rule_based_rubric', {'case_id': cid, 'scenario': r['scenario'], 'domain_id': domain['id']})

    workspace.mkdir(parents=True, mode=0o700)
    stage = {'version': 'next_review_v1', 'scope': 'authored engineering encounters; not held-out learner evaluation',
             'protocol_lock': lock, 'source_sha256': sources, 'batches': {},
             'dropped_action_hits': dropped, 'human_decisions': 'PENDING', 'learner_mcpt': 'NOT EVALUABLE'}
    for kind, tasks in batches.items():
        tasks.sort(key=lambda t: t['packet_id'])
        predictions[kind].sort(key=lambda t: t['packet_id'])
        destination = workspace / kind
        destination.mkdir(mode=0o700)
        manifest = {'workflow_version': 1, 'toy': False, 'scope': stage['scope'], 'protocol_lock': lock,
                    'packet_ids': [t['packet_id'] for t in tasks], 'view_sha256': digest(tasks)}
        save(destination / 'review_manifest.json', manifest)
        save(destination / 'blinded_tasks.json', tasks)
        save(destination / 'PRIVATE_predictions.json', predictions[kind])
        for slot in ('a', 'b'):
            render_tasks(destination / ('reviewer_' + slot + '.html'), tasks, manifest, slot)
        stage['batches'][kind] = {'tasks': len(tasks), 'manifest_sha256': sha256((destination / 'review_manifest.json').read_bytes()).hexdigest(),
                                'predictions_sha256': sha256((destination / 'PRIVATE_predictions.json').read_bytes()).hexdigest()}
    save(workspace / 'stage.json', stage)
    write_private(workspace / 'clinical_and_difficulty_decisions.md', decision_sheet(cases, sources, records))
    write_private(workspace / 'README.md', instructions(stage))
    return stage


def decision_sheet(cases: dict, sources: dict, records: list) -> str:
    lines = ['# Clinical and difficulty decisions — pending human review', '',
             'Authored synthetic cases only. Complete decisions with a reviewer pseudonym, role, date, rationale and source. '
             'Editing this worksheet does not approve a case or authorize a learner study.', '',
             'Review `backend_kelsch/docs/clinical_reasoning_review.md`: suicide disclosure and screening, '
             'mania/prescription logic and follow-up timing, pediatric test context, and dietetics role boundaries. '
             'Resolve these explicitly before showcasing affected paths.', '']
    for cid, case in cases.items():
        lines += [f'## {cid} · version {case.version}', '', f"Case SHA-256: `{sources['cases/' + cid + '.json']}`", '',
                  f'Learner role: {case.briefing.student_role}', '',
                  'Clinical facts, disclosure timing, safety, role boundaries: **PENDING**', '',
                  'Full difficulty presets and next-case routing: **PENDING**. The following are threshold probes only.', '']
        for preset in ('straightforward', 'typical', 'difficult'):
            changed = with_probe_preset(case, preset)
            lines += [f'- {preset}: `{json.dumps(changed.trust.thresholds, sort_keys=True)}`']
        lines += ['', 'Authored decision points and next-visit outcomes (review every predicate and outcome):', '',
                  '```json', json.dumps([{'visit_id': v.id, 'decision_points': [d.model_dump(mode='json') for d in v.decision_points],
                                         'branches': [b.model_dump(mode='json') for b in v.branches]} for v in case.visits], indent=2), '```', '',
                  'Observed engineering uncertainty:', '']
        for r in records:
            if r['case_id'] == cid:
                lines += [f"- {r['scenario']}: `{json.dumps(r['branch']['uncertain_predicates'])}`"]
        lines += ['', 'Decision: PENDING', 'Required corrections: PENDING', 'Reviewer / role / date / evidence: PENDING', '']
    return '\n'.join(lines) + '\n'


def instructions(stage: dict) -> str:
    counts = ', '.join(f"{k}: {v['tasks']}" for k, v in stage['batches'].items())
    return f'''# Next human review handoff

Counts: {counts}. All inputs are authored engineering fixtures. No learner observations or independent labels were generated.

Give each independent reviewer only the relevant `reviewer_a.html` or `reviewer_b.html`. They open it in a browser, use the supplied JSON answer examples and citation buttons, enter a pseudonym, and download their answers. No AWS account is required. Keep `PRIVATE_predictions.json`, other submissions and coordinator files away from independent reviewers. Clinical domains need qualified reviewers.

For claim tasks, judge the complete candidate text/label and its citations against the supplied transcript, case facts and documentation. Note citations use turn 0 with speaker `note:<field>`; they are documentation anchors, not student speech. Action tasks use the fixed research vocabulary, which is narrower than the production case-action vocabulary. Review negatives as exact-span `other`.

Use `eval_development configure` separately for action, claim and domain, with workspace set to that batch directory, the A/B paths, actual human pseudonyms and `--a-kind human --b-kind human`. Add `--predictions <batch>/PRIVATE_predictions.json` and create a new config version. Descriptions must state actual qualifications; declared human provenance does not prove authority.

Run `eval_next_review adjudicate --workspace <stage> --kind <kind> --config <config>` to prepare only disagreements after both submissions. If needed, obtain a distinct third review and configure a new version with its actual identity/type. Then run `eval_next_review report` with the same options and `--output <private_report.json>`.

Complete `clinical_and_difficulty_decisions.md` with the qualified reviewer. Apply accepted corrections as new case versions in a later PR, then prepare a new stage; never rehash changed inputs into this batch. Keep this entire directory outside Git. Human scores on these authored encounters test development agreement, not held-out performance or learning efficacy.

The next human stop is independent action/claim/domain review plus clinical and full-preset decisions. Real learner difficulty and learning effects require authorized collection; the existing synthetic Monte Carlo permutation test remains a mechanics demonstration.
'''


def review_stage(workspace: Path, kind: str, config: Path, *, adjudicate: bool = False) -> dict:
    workspace = private_path(workspace)
    stage = json.loads((workspace / 'stage.json').read_text())
    if stage.get('version') != 'next_review_v1' or kind not in stage['batches']:
        raise ValueError('unknown stage or batch')
    if stage['protocol_lock'] != digest({'stage': 'next_review_v1', 'sources': stage['source_sha256']}):
        raise ValueError('stage source lock mismatch')
    if source_lock() != stage['source_sha256']:
        raise ValueError('current sources differ from stage; use the frozen checkout or prepare a new batch')
    ref = load_reference(config)
    spec = stage['batches'][kind]
    _, manifest_raw = read_source(ref['base'], ref['config']['manifest'])
    if ref['summary']['protocol_lock'] != stage['protocol_lock'] or sha256(manifest_raw).hexdigest() != spec['manifest_sha256']:
        raise ValueError('reference differs from frozen stage batch')
    if any(t['kind'] != kind for t in ref['tasks'].values()):
        raise ValueError('mixed or wrong task kind')
    pred = ref['config'].get('predictions')
    if not pred or pred['sha256'] != spec['predictions_sha256']:
        raise ValueError('use the predictions frozen before reviewer handoff')
    _, prediction_raw = read_source(ref['base'], pred)
    predicted = {r['packet_id']: r for r in json.loads(prediction_raw)}
    if adjudicate:
        if any(pid not in ref['submissions'][s] for pid in ref['tasks'] for s in ('a', 'b')):
            raise ValueError('finish both independent submissions before adjudication')
        originals = {}
        for submission in ref['config']['submissions']:
            if submission['slot'] in ('a', 'b'):
                _, raw = read_source(ref['base'], submission)
                rows, _ = answers(raw)
                originals[submission['slot']] = {r['packet_id']: r for r in rows}
        pairs = {pid: [{'slot': s, **{key: originals[s][pid][key] for key in
                                    ('answer', 'evidence', 'rationale')}} for s in ('a', 'b')]
                 for pid in ref['disagreements']}
        path = private_path(config).parent / 'adjudicator.html'
        if path.exists():
            raise ValueError('adjudicator file exists; use a new directory or retain the frozen handoff')
        render_tasks(path, [ref['tasks'][pid] for pid in ref['disagreements']], json.loads(manifest_raw), 'adjudicator', pairs)
    ready = ref['summary']['pending_count'] == 0
    comparison = prediction_comparison(ref) if ready else None
    differences = [{'packet_id': pid, 'reference_answer': row['answer'],
                    'prediction_answer': predicted[pid]['answer'],
                    'source_mapping': predicted[pid]['source_mapping']}
                   for pid, row in ref['resolved'].items()
                   if row['answer'] != normalize_answer(ref['tasks'][pid], predicted[pid]['answer'])]
    critical_support = None
    if kind == 'action':
        critical_support = {label: sum(label in a['labels'] for row in ref['resolved'].values()
                                      for a in row['answer']['annotations']) for label in CRITICAL}
    return {'version': 'next_review_report_v1', 'scope': stage['scope'], 'review_reference': ref['summary'],
            'paired_domain_agreement': reviewed_domain_agreement(ref) if kind == 'domain' else None,
            'prediction_comparison': comparison, 'pending_packet_ids': ref['pending'],
            'diagnostic_answer_differences': differences,
            'critical_positive_span_support': critical_support,
            'review_transport': 'PASS' if ready else 'NOT EVALUABLE', 'human_authority': 'NOT VERIFIED',
            'held_out_action_performance': 'NOT EVALUABLE', 'learner_difficulty': 'NOT EVALUABLE',
            'learner_mcpt': 'NOT EVALUABLE',
            'remaining_input': ['Resolve remaining labels and disagreements', 'Qualified clinical/case/preset decisions',
                                'Independent held-out action corpus with sufficient critical positives',
                                'Authorized genuine learner baseline and follow-up outcomes']}
