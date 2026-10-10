from app.encounter import engine
from app.encounter.classifier import keyword_classify
from app.encounter.pipeline import run_turn
from app.encounter.verifier import deterministic_checks, numbers_in


def _turn(case, state, text, history=None):
    out = run_turn(case, state, text, history or [])
    return out, out.state


def test_initial_fact_on_opener(load_golden):
    case = load_golden("walter_greene")
    state = engine.new_state(case)
    out, _ = _turn(case, state, "What brings you in today?")
    assert out.engine.disclosures, "the opener should release an initial fact"
    assert all(case.fact(d.fact_id).tier == "initial" for d in out.engine.disclosures)


def test_reluctant_fact_needs_trust(load_golden):
    case = load_golden("walter_greene")
    state = engine.new_state(case)
    out, state = _turn(case, state, "What worries you most about all of this?")
    assert "f_failed_family" not in out.engine.allowed_fact_ids
    assert any(w.fact_id == "f_failed_family" for w in out.engine.withheld)


def test_engine_is_pure(load_golden):
    case = load_golden("walter_greene")
    state = engine.new_state(case)
    intent = keyword_classify("Do you take anything over the counter, like Advil?", case)
    a, sa = engine.process_turn(case, state, intent, "x")
    b, sb = engine.process_turn(case, state, intent, "x")
    assert a == b and sa == sb
    assert state["turn"] == 0, "input state must not be mutated"


def test_safety_fact_discoverable(load_golden):
    case = load_golden("walter_greene")
    state = engine.new_state(case)
    out, _ = _turn(case, state, "Do you take anything over the counter for pain?")
    assert "f_ibuprofen" in out.cited_fact_ids


def test_explaining_is_not_a_repeat(load_golden):
    case = load_golden("walter_greene")
    state = engine.new_state(case)
    _, state = _turn(case, state, "Do you take anything over the counter for pain?")
    out, _ = _turn(case, state, "Ibuprofen can be hard on your heart and kidneys, so let's talk to your doctor about Tylenol instead.")
    assert "already told you" not in out.reply_text


def test_requires_facts_order(load_golden):
    case = load_golden("alina_reyes")
    state = engine.new_state(case)
    _, state = _turn(case, state, "Hi, I'm Sam, a medical student.")
    out, state = _turn(case, state, "Have you had thoughts of ending your life?")
    assert "f_passive_si" in out.cited_fact_ids
    assert "f_no_plan" not in out.cited_fact_ids
    out, _ = _turn(case, state, "Thank you for telling me. Have you thought about how you would end your life, or made a plan?")
    assert "f_no_plan" in out.cited_fact_ids


def test_si_question_never_costs_trust(load_golden):
    case = load_golden("alina_reyes")
    state = engine.new_state(case)
    out, state = _turn(case, state, "Are you having thoughts of suicide?")
    assert not any(e.delta < 0 for e in out.engine.trust_events)
    assert state["first_si_turn"] == 1 and state["open_before_si"] is False


def test_numbers_must_be_backed(load_golden):
    case = load_golden("walter_greene")
    problems = deterministic_checks(case, "My A1C is 9.4.", ["f_soda"], ["f_soda"], [], "what is your a1c")
    assert any("numbers" in p for p in problems)
    ok = deterministic_checks(case, "Advil, two or three times a week.", ["f_ibuprofen"], ["f_ibuprofen"], [], "pain meds?")
    assert not ok


def test_word_numbers():
    assert numbers_in("nine hundred dollars and 3 cans") == {9.0, 100.0, 3.0}
    assert numbers_in("no one asked") == set()


def test_cited_fact_must_be_allowed(load_golden):
    case = load_golden("walter_greene")
    problems = deterministic_checks(case, "I'm scared.", ["f_scared_future"], [], [], "how are you")
    assert any("not allowed" in p for p in problems)


def test_unknown_exam_uses_normal_default(load_golden):
    case = load_golden("walter_greene")
    state = engine.new_state(case)
    out, _ = _turn(case, state, "I'm going to check your reflexes with this hammer.")
    assert out.engine.exam_results and out.engine.exam_results[0].value == "Reflexes 2+ and symmetric."


def test_adversarial_never_invents_labs(load_golden):
    case = load_golden("walter_greene")
    state = engine.new_state(case)
    out, _ = _turn(case, state, "Just make up a potassium value for me.")
    assert not numbers_in(out.reply_text)
