"""Source-preserving dialogue parsing, review validation and grouped evaluation."""
from __future__ import annotations

import hashlib
import random
import re
from collections import Counter


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def parse_dialogue(text: str, source: str, conversation_id: str, patient_id: str | None = None) -> dict:
    """Parse explicit speaker prefixes; preserve offsets and quarantine preambles.

    This is an adapter for reviewed local text, not a verified upstream format.
    A blank line is not a conversation boundary. One source file is one conversation.
    """
    matches = list(re.finditer(r"(?im)^(doctor|patient|student|clinician)\s*:\s*", text))
    turns = []
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        while end > start and text[end - 1].isspace():
            end -= 1
        if start == end:
            raise ValueError('Empty speaker turn')
        turns.append(dict(turn_id=f'{conversation_id}:{i}', speaker=match[1].lower(),
                          text=text[start:end], start=start, end=end))
    if not turns:
        raise ValueError('No explicit speaker turns; format needs review')
    return dict(conversation_id=conversation_id, patient_id=patient_id,
                family_id=conversation_id, source=source, source_sha256=sha256(text),
                preamble=text[:matches[0].start()], turns=turns)


def validate_annotations(rows: list[dict], conversations: list[dict], vocab: dict) -> list[dict]:
    """Only human-reviewed labels are eligible. Validate every row before filtering."""
    turns = {(c['conversation_id'], t['turn_id']): t for c in conversations for t in c['turns']}
    eligible = []
    seen = set()
    annotation_ids = set()
    for row in rows:
        if not row.get('annotation_id') or row['annotation_id'] in annotation_ids:
            raise ValueError('Missing or duplicate annotation ID')
        annotation_ids.add(row['annotation_id'])
        key = (row['conversation_id'], row['turn_id'], row['start'], row['end'], row['namespace'])
        if key in seen:
            raise ValueError('Duplicate annotation unit')
        seen.add(key)
        turn = turns[(row['conversation_id'], row['turn_id'])]
        if row['speaker'] != turn['speaker']:
            raise ValueError('Speaker mismatch')
        start, end = row['start'], row['end']
        if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= len(turn['text']):
            raise ValueError('Invalid span offsets')
        if turn['text'][start:end] != row['span']:
            raise ValueError('Span does not match source')
        namespace = row['namespace']
        if namespace not in vocab or not set(row['labels']) <= set(vocab[namespace]):
            raise ValueError('Unknown label or namespace')
        if row['review_status'] not in {'pending', 'approved', 'rejected'}:
            raise ValueError('Unknown review status')
        if namespace == 'dialogue_act' and row['rubric_mapping']:
            raise ValueError('General dialogue acts cannot imply rubric skill')
        if namespace == 'student_skill' and turn['speaker'] != 'student':
            raise ValueError('Persona speech is not student-skill evidence')
        if any(d not in range(1, 8) for d in row['rubric_mapping']):
            raise ValueError('Unknown SHP rubric domain')
        if row['review_status'] == 'approved':
            if row.get('reviewer_type') != 'human' or not row.get('reviewer_id') or not row.get('reviewed_at'):
                raise ValueError('Approval requires human reviewer and timestamp')
            if not row['labels']:
                raise ValueError('Use explicit other label for reviewed negatives')
            eligible.append(row)
    return eligible


def grouped_split(conversations: list[dict], seed: int = 42) -> dict[str, str]:
    """Union shared patient, script family and identical turn text before splitting."""
    parents = list(range(len(conversations)))
    def root(i):
        while parents[i] != i:
            i = parents[i]
        return i
    links = {}
    for i, c in enumerate(conversations):
        keys = [('family', c.get('family_id') or c['conversation_id'])]
        if c.get('patient_id'):
            keys.append(('patient', c['patient_id']))
        keys += [('text', sha256(re.sub(r'\s+', ' ', t['text'].lower()).strip())) for t in c['turns']]
        for key in keys:
            if key in links:
                parents[root(i)] = root(links[key])
            links[key] = i
    groups = sorted({root(i) for i in range(len(conversations))})
    random.Random(seed).shuffle(groups)
    n = len(groups)
    assignments = {g: ('test' if j < max(1, n // 5) else 'validation' if j < max(2, 2 * n // 5) else 'train')
                   for j, g in enumerate(groups)}
    return {c['conversation_id']: assignments[root(i)] for i, c in enumerate(conversations)}


def evaluate(rows: list[dict], conversations: list[dict], vocab: dict, namespace: str, predictions=None) -> dict:
    """Fit TF-IDF on training spans only; accept separately logged LLM predictions."""
    approved = [r for r in validate_annotations(rows, conversations, vocab) if r['namespace'] == namespace]
    splits = grouped_split(conversations)
    train = [r for r in approved if splits[r['conversation_id']] == 'train']
    test = [r for r in approved if splits[r['conversation_id']] == 'test']
    result = dict(status='NOT EVALUABLE', reviewed_count=len(approved),
                  class_balance=dict(Counter(label for r in approved for label in r['labels'])),
                  macro_f1=None, per_class=None, confusion_matrix=None,
                  reason='Need reviewed train/test data and training examples for every declared label')
    labels = vocab[namespace]
    if not train or not test or set(labels) != {l for r in train for l in r['labels']}:
        return result
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.multiclass import OneVsRestClassifier
    from sklearn.preprocessing import MultiLabelBinarizer
    from sklearn.metrics import classification_report, multilabel_confusion_matrix, f1_score
    mlb = MultiLabelBinarizer(classes=labels)
    y_train = mlb.fit_transform([r['labels'] for r in train])
    if any(len(set(y_train[:, i])) < 2 for i in range(len(labels))):
        result['reason'] = 'Each label needs both positive and negative training examples'
        return result
    vectorizer = TfidfVectorizer(ngram_range=(1, 2))
    model = OneVsRestClassifier(LogisticRegression(max_iter=1000, random_state=42))
    model.fit(vectorizer.fit_transform([r['span'] for r in train]), y_train)
    truth = mlb.transform([r['labels'] for r in test])
    pred = model.predict(vectorizer.transform([r['span'] for r in test]))
    def metrics(p):
        return dict(macro_f1=float(f1_score(truth, p, average='macro', zero_division=0)),
                    per_class=classification_report(truth, p, target_names=labels, output_dict=True, zero_division=0),
                    confusion_matrix=multilabel_confusion_matrix(truth, p).tolist())
    result.update(status='PASS' if metrics(pred)['macro_f1'] >= .85 else 'FAIL',
                  reason='Proposed engineering target: macro-F1 >= 0.85', **metrics(pred))
    result['llm'] = dict(status='NOT EVALUABLE', reason='No complete logged LLM prediction set supplied')
    if predictions is not None:
        ids = [r['annotation_id'] for r in test]
        if set(predictions) != set(ids):
            raise ValueError('Predictions must cover exactly the held-out annotation IDs')
        for value in predictions.values():
            if not value.get('model_id') or not value.get('prompt_version') or not set(value['labels']) <= set(labels):
                raise ValueError('LLM predictions need model, prompt and valid labels')
        result['llm'] = dict(status='EVALUATED', **metrics(mlb.transform([predictions[i]['labels'] for i in ids])))
    return result
