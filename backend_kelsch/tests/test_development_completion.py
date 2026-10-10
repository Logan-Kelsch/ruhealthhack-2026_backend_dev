"""Completion checks must not promote authored or model labels to clinical evidence."""
from app.encounter.phraser import phrase, template_reply
from app.schemas.encounter import EngineResult
from backend_kelsch.app.study.development_evaluation import completion_report
import pytest


@pytest.mark.parametrize('text,expected', [
    ('I will not prescribe an antibiotic.', set()),
    ("I won't prescribe an antibiotic.", set()),
    ('I will not start you on a new medication.', set()),
    ('I have not explained any warning signs yet.', set()),
    ('I will prescribe an antibiotic.', {'prescribe_antibiotic', 'start_medication'}),
    ('I will not prescribe an antibiotic, but I will start you on a new medication.', {'start_medication'}),
    ('I will not prescribe an antibiotic. I will prescribe an antibiotic later.', {'prescribe_antibiotic', 'start_medication'}),
    ('You are not allergic to this, and I will prescribe an antibiotic.', {'prescribe_antibiotic', 'start_medication'}),
])
def test_keyword_critical_negation_preserves_affirmative_clauses(load_golden, text, expected):
    from app.encounter.classifier import keyword_classify
    actual = keyword_classify(text, load_golden('eli_brooks')).action_ids()
    assert actual & {'prescribe_antibiotic', 'start_medication', 'safety_netting'} == expected


def test_repeat_template_does_not_assert_unspoken_fact_history(load_golden):
    case = load_golden('walter_greene')
    result = EngineResult(is_repeat=True, repeat_fact_ids=['f_complains_pills'])
    reply, cited = template_reply(case, result, set())
    assert reply == case.fact('f_complains_pills').say
    assert cited == ['f_complains_pills'] and 'already told' not in reply.lower()


def test_repeat_without_matching_fact_uses_uncertainty(load_golden):
    reply, cited = template_reply(load_golden('walter_greene'), EngineResult(is_repeat=True), set())
    assert 'already told' not in reply.lower() and cited == []


def test_phrase_uses_availability_not_spoken_history(monkeypatch, load_golden):
    from app.integrations.bedrock import LLMCall
    captured = {}
    def fake(*, user, **kwargs):
        captured['user'] = user
        return {'reply_text': 'Hi.', 'cited_fact_ids': []}, LLMCall(purpose='phrase', model='fixture', prompt='phraser', prompt_version='3', latency_ms=0, ok=True)
    monkeypatch.setattr('app.encounter.phraser.complete_json', fake)
    phrase(load_golden('walter_greene'), EngineResult(is_repeat=True), 'What about my pills?', [], ['f_complains_pills'])
    assert 'availability does not prove they were spoken' in captured['user']
    assert 'recent patient dialogue explicitly contains it' in captured['user']


def test_mechanical_report_preserves_all_human_gates():
    report = completion_report()
    assert report['development_gates']['mechanical_regression'] == 'PASS'
    assert report['mechanics']['difficulty']['runs'] == 27
    assert report['mechanics']['difficulty']['clinical_content_unchanged']
    assert report['development_gates']['critical_action_fixture_regression'] == 'PASS'
    assert set(report['human_gates'].values()) == {'NOT EVALUABLE'}
