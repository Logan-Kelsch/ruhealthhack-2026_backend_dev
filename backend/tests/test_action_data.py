"""Synthetic fixtures verify mechanics, never model quality."""
import pytest
from app.action_data.preparation import parse_dialogue, grouped_split, validate_annotations, evaluate
from scripts.prepare_action_data import build_report

VOCAB = {'dialogue_act':['question','other'], 'student_skill':['summarize','other']}

def fixture():
    c = parse_dialogue('Summary: hidden fact\nStudent: Tell me more?\n\nPatient: I am unsure.\nStill unsure.', 'synthetic-test', 'c1')
    row = dict(annotation_id='a1',conversation_id='c1',turn_id='c1:0',speaker='student',start=0,end=13,
               span='Tell me more?',namespace='dialogue_act',labels=['question'],rubric_mapping=[],review_status='pending')
    return c,row


def test_parser_preserves_multiline_offsets_and_preamble():
    c,_=fixture()
    assert len(c['turns']) == 2
    assert c['preamble'].startswith('Summary:')
    assert c['turns'][1]['text'].endswith('Still unsure.')
    with pytest.raises(ValueError):
        parse_dialogue('unrecognized format','test','bad')


def test_review_and_span_validation():
    c,r=fixture()
    assert validate_annotations([r],[c],VOCAB) == []
    r['review_status']='approved'
    with pytest.raises(ValueError):
        validate_annotations([r],[c],VOCAB)
    r.update(reviewer_type='human',reviewer_id='reviewer-1',reviewed_at='2026-10-10')
    assert validate_annotations([r],[c],VOCAB) == [r]
    r['span']='invented'
    with pytest.raises(ValueError):
        validate_annotations([r],[c],VOCAB)


def test_namespaces_and_persona_restriction():
    c,r=fixture(); r['rubric_mapping']=[3]
    with pytest.raises(ValueError):
        validate_annotations([r],[c],VOCAB)
    r.update(namespace='student_skill',labels=['summarize'],speaker='patient',turn_id='c1:1',start=0,end=1,span='I')
    with pytest.raises(ValueError):
        validate_annotations([r],[c],VOCAB)


def test_group_links_are_transitive_and_deterministic():
    def c(i,p,f,text):
        return dict(conversation_id=i,patient_id=p,family_id=f,turns=[dict(text=text)])
    cs=[c('a','p1','f1','one'),c('b','p1','f2','two'),c('c','p2','f2','three'),c('d','p3','f3','THREE')]
    split=grouped_split(cs)
    assert len(set(split.values())) == 1
    assert split == grouped_split(cs)


def test_unreviewed_data_cannot_produce_metrics():
    c,r=fixture()
    result=evaluate([r],[c],VOCAB,'dialogue_act')
    assert result['status']=='NOT EVALUABLE'
    assert result['macro_f1'] is None
    assert result['reviewed_count']==0


def test_real_inventory_keeps_model_gate_blocked():
    result=build_report()
    assert result['gates']['prior_structural_gate']=='PASS'
    assert result['external_source']['import_status']=='BLOCKED'
    assert not result['validated_model_ready']


def test_baseline_and_logged_llm_comparison():
    cs=[]; rows=[]
    for i in range(20):
        c=parse_dialogue(f'Student: question unique{i}?\nStudent: statement unique{i}.','synthetic-test',f'c{i}')
        cs.append(c)
        for j,t in enumerate(c['turns']):
            rows.append(dict(annotation_id=f'a{i}:{j}',conversation_id=f'c{i}',turn_id=t['turn_id'],
                speaker='student',start=0,end=len(t['text']),span=t['text'],namespace='dialogue_act',
                labels=['question' if j==0 else 'other'],rubric_mapping=[],review_status='approved',
                reviewer_type='human',reviewer_id='test-only',reviewed_at='2026-10-10'))
    splits=grouped_split(cs)
    predictions={r['annotation_id']:dict(labels=r['labels'],model_id='test-only',prompt_version='test-only')
                 for r in rows if splits[r['conversation_id']]=='test'}
    result=evaluate(rows,cs,VOCAB,'dialogue_act',predictions)
    assert result['macro_f1'] is not None
    assert len(result['confusion_matrix'])==2
    assert result['llm']['macro_f1']==1
    with pytest.raises(ValueError):
        evaluate(rows,cs,VOCAB,'dialogue_act',{})
