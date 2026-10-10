"""Offline action-data inventory: python -m scripts.prepare_action_data."""
import argparse
import json
from pathlib import Path
from app.action_data.preparation import evaluate, grouped_split, sha256
ROOT = Path(__file__).resolve().parents[2]


def build_report(root=ROOT, annotations=None, corpus=None):
    audit = json.loads((root / 'docs/validation/dataset_audit.json').read_text())
    if audit['gate'] != 'PASS':
        raise ValueError('Notebook 01 structural gate must pass')
    conversations = []
    for path in sorted((root / 'cases').glob('*.json')):
        case = json.loads(path.read_text())
        lines = case.get('profile', {}).get('personality', {}).get('example_lines', [])
        if lines:
            conversations.append(dict(conversation_id=case['case_id'], family_id=case['case_id'],
                patient_id=case['case_id'], source=str(path.relative_to(root)),
                source_sha256=sha256(path.read_text()), source_kind='authored_persona_example',
                turns=[dict(turn_id=f"{case['case_id']}:{i}", speaker='patient', text=line,
                            source_pointer=f'/profile/personality/example_lines/{i}') for i, line in enumerate(lines)]))
    if corpus is not None:
        data = json.loads(corpus.read_text())
        if not data.get('license_verified') or not data.get('synthetic_provenance_verified') or not data.get('provenance_ref'):
            raise ValueError('Corpus requires reviewed license and synthetic provenance')
        conversations = data['conversations']
        if len({c['conversation_id'] for c in conversations}) != len(conversations):
            raise ValueError('Duplicate conversation IDs')
        if any(not c.get('source') or not c.get('source_sha256') for c in conversations):
            raise ValueError('Missing source provenance')
    vocab = json.loads((root / 'backend/app/data/action_annotation_vocab.json').read_text())
    rows = [] if annotations is None else [json.loads(line) for line in annotations.read_text().splitlines() if line.strip()]
    evaluation = {ns: evaluate(rows, conversations, vocab, ns) for ns in vocab}
    return dict(stage='Notebook 02', gate='NOT EVALUABLE', implementation_ready=True, validated_model_ready=False,
        gates={'prior_structural_gate':'PASS', 'external_license_and_synthetic_provenance':'NOT EVALUABLE',
               'macro_f1_ge_085':evaluation['dialogue_act']['status'], 'critical_recall_ge_095':'NOT EVALUABLE',
               'llm_comparison':'NOT EVALUABLE'},
        advance_to_notebook_03='Controlled simulator may proceed with existing classifier. Trained extraction is blocked.',
        external_source=json.loads((root / 'docs/validation/patient_doctor_access.json').read_text()),
        conversations=conversations, splits=grouped_split(conversations), evaluation=evaluation,
        limitations=['Persona examples are isolated speech, not encounters or student labels.',
                    'Upstream format unverified: no licensed dialogue contents imported.',
                    'Critical labels and targets need reviewer agreement.',
                    'No student learning or efficiency results exist.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--annotations', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/validation/action_data.json')
    args = parser.parse_args()
    report = build_report(annotations=args.annotations, corpus=args.corpus)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print('Model gate:', report['gate'])


if __name__ == '__main__':
    main()
