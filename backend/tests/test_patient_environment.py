"""Contract probes cover state transitions, visibility and repeatability."""
from copy import deepcopy

import pytest

from app.encounter.engine import new_state
from app.patient_environment.runner import (
    fact_for_role, fingerprint, replay, run_script, tagged_turn, with_probe_preset,
)
from scripts.eval_patient_environment import evaluate, scenario


def test_authored_gates():
    report = evaluate()
    assert report["gates"]["controlled_environment"] == "PASS", report["checks"]
    assert report["passed"] == report["total"] == 10
    assert report["gates"]["trained_action_extraction"] == "NOT EVALUABLE"


def test_replay_and_no_input_mutation(load_golden):
    case = load_golden("walter_greene")
    original = deepcopy(case)
    altered = with_probe_preset(case, "difficult")
    trace = run_script(altered, scenario())
    assert fingerprint(trace) == fingerprint(replay(trace, altered))
    assert case == original
    assert altered.trust.thresholds["hidden"] > case.trust.thresholds["hidden"]
    with pytest.raises(ValueError, match="case identity"):
        replay(trace, load_golden("alina_reyes"))


def test_visibility_denies_hidden_and_draft(load_golden):
    case = load_golden("walter_greene")
    state = new_state(case)
    with pytest.raises(PermissionError, match="not disclosed"):
        fact_for_role(case, state, "f_scared_future", "student")
    assert fact_for_role(case, state, "f_scared_future", "faculty").source.kind
    with pytest.raises(PermissionError, match="unknown role"):
        fact_for_role(case, state, "f_scared_future", "guest")
    state["disclosed"]["f_scared_future"] = 1
    assert fact_for_role(case, state, "f_scared_future", "student").id == "f_scared_future"
    draft = case.model_copy(deep=True)
    draft.fact("f_scared_future").status = "draft"
    with pytest.raises(PermissionError, match="unavailable"):
        fact_for_role(draft, state, "f_scared_future", "faculty")


def test_dependent_fact_and_memory(load_golden):
    alina = load_golden("alina_reyes")
    turns = [tagged_turn("Are you thinking about suicide?", topics=("suicidal_ideation",)),
             tagged_turn("Hi, I'm Sam, a medical student.", introduction=True),
             tagged_turn("Are you thinking about suicide?", topics=("suicidal_ideation",)),
             tagged_turn("Have you made a plan?", topics=("suicidal_ideation",))]
    trace = run_script(alina, turns)["turns"]
    assert trace[0]["trust_after"] == 0
    assert "f_passive_si" not in trace[0]["allowed_fact_ids"]
    assert "f_passive_si" in trace[2]["allowed_fact_ids"]
    assert "f_no_plan" in trace[3]["allowed_fact_ids"]
    assert all(e["span"] in row["utterance"] for row in trace for e in row["trust_events"])


def test_presets_are_explicit_and_reject_unknown(load_golden):
    case = load_golden("walter_greene")
    with pytest.raises(ValueError, match="unsupported"):
        with_probe_preset(case, "custom")
    counts = {p: len(run_script(with_probe_preset(case, p), scenario())["final_state"]["disclosed"])
              for p in ("straightforward", "typical", "difficult")}
    assert counts["straightforward"] > counts["typical"] > counts["difficult"]
