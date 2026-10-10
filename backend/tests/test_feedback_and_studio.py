import pytest

from app.feedback.decisions import TurnView, evaluate_predicate, select_branch
from app.studio import consistency, publish, vhs_import
from app.studio.autofill import autofill_labs, autofill_vitals, formulas, truncated_normal
from app.studio.preview import run_test_student


def _tv(idx, topics=(), actions=(), qtype="closed", disclosed=(), conf="high"):
    return TurnView(idx=idx, student_text=f"t{idx}", topics={t: (t, conf) for t in topics}, actions={a: (a, conf) for a in actions},
                    maneuvers={}, orders={}, question_type=qtype, disclosed=list(disclosed))


def test_before_predicate():
    turns = [_tv(1, qtype="open"), _tv(2, topics=["suicidal_ideation"])]
    ok, _ = evaluate_predicate({"before": [{"open_question": True}, {"topic": "suicidal_ideation"}]}, turns)
    assert ok
    ok, _ = evaluate_predicate({"before": [{"open_question": True}, {"topic": "suicidal_ideation"}]}, [_tv(1, topics=["suicidal_ideation"]), _tv(2, qtype="open")])
    assert not ok


def test_not_predicate_and_low_confidence():
    ok, m = evaluate_predicate({"not": {"action": "prescribe_antibiotic"}}, [_tv(1)])
    assert ok
    ok, m = evaluate_predicate({"action": "summarize"}, [_tv(1, actions=["summarize"], conf="low")])
    assert ok and m.low_confidence


def test_branch_after_prior_path(load_golden):
    case = load_golden("alina_reyes")
    v2 = case.visit("v2")
    results = [{"id": "dp_v2_mania_check", "value": False}]
    taken, _ = select_branch(v2, results, "b_bipolar_managed")
    assert taken.id == "b_v2_stable", "the hospitalization outcome only follows the missed-mania path"
    taken, _ = select_branch(v2, results, "b_ssri_trap")
    assert taken.id == "b_v2_hospitalized"


def test_egfr_formula_and_inverse():
    assert round(formulas.egfr_ckd_epi_2021(1.6, 72, False)) == 45
    cr = formulas.creatinine_for_egfr(45, 72, False)
    assert abs(formulas.egfr_ckd_epi_2021(cr, 72, False) - 45) < 0.01


def test_sampling_is_seeded_and_in_range():
    a = truncated_normal(7, "na", 135, 145)
    assert a == truncated_normal(7, "na", 135, 145)
    assert 135 <= a <= 145


def test_autofill_uses_rules_and_skips_children(load_golden):
    case = vhs_import.import_all()[0]
    case.labs = []
    case.description = "type 2 diabetes"
    labs, _ = autofill_labs(case, ["a1c", "bmp"])
    a1c = next(lab for lab in labs if lab.key == "a1c")
    assert 7.0 <= a1c.value <= 9.5 and a1c.source.kind == "rule"
    assert any(lab.key == "egfr" and lab.source.kind == "computed" for lab in labs)
    child = load_golden("eli_brooks")
    labs, notes = autofill_labs(child, ["bmp"])
    assert labs == [] and notes
    child.vitals = []
    vitals, _ = autofill_vitals(child)
    assert {v.key for v in vitals} >= {"hr", "rr", "temp_c"}


def test_vhs_import_all_eight():
    cases = vhs_import.import_all()
    assert len(cases) == 8
    for c in cases:
        assert all(f.status == "draft" for f in c.facts)
        spo2 = next((v for v in c.vitals if v.key == "spo2"), None)
        assert spo2 is None or 90 <= float(spo2.value) <= 100


def test_walter_import_consistency_findings():
    walter = next(c for c in vhs_import.import_all() if c.case_id == "walter_greene")
    rules = {f.rule for f in consistency.check(walter)}
    assert {"age_mismatch", "lab_text_mismatch", "unknown_drug_name", "weight_contradiction", "nsaid_with_hf_or_ckd"} <= rules


def test_imported_case_cannot_publish():
    case = vhs_import.import_all()[0]
    assert publish.blockers(case)


@pytest.mark.parametrize("case_id", ["walter_greene", "alina_reyes", "eli_brooks"])
def test_golden_cases_publishable_and_grounded(load_golden, case_id):
    case = load_golden(case_id)
    assert publish.blockers(case) == []
    for level in ("novice", "expert", "adversarial"):
        run = run_test_student(case, level)
        assert run["grounding"]["replies_failing_audit"] == 0


def test_expert_beats_novice(load_golden):
    case = load_golden("walter_greene")
    assert run_test_student(case, "expert")["rubric_total_rule_based"] > run_test_student(case, "novice")["rubric_total_rule_based"]
