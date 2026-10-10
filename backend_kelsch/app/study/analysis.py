"""Reviewed denominators and conservative, source-locked Notebook 06 gates."""
from __future__ import annotations

from collections import Counter, defaultdict
import json
from math import sqrt
from pathlib import Path
import random
from statistics import NormalDist, mean, variance

from backend_kelsch.app.action_data.preparation import evaluate as evaluate_extraction
from backend_kelsch.app.study.protocol import PROTOCOL, VOCAB, load_previous, split_audit
from backend_kelsch.app.study.review import action_annotations


def wilson(success: int, total: int, *, z: float = 1.959963984540054) -> dict | None:
    if total <= 0 or not 0 <= success <= total:
        return None
    p = success / total
    denom = 1 + z*z/total
    center = (p + z*z/(2*total)) / denom
    radius = z * sqrt(p*(1-p)/total + z*z/(4*total*total)) / denom
    return {"estimate": p, "lower": max(0.0, center-radius), "upper": min(1.0, center+radius),
            "success": success, "denominator": total, "method": "Wilson 95%; descriptive, treats units as independent"}


def planning_n_per_arm(effect: float = .5, loss: float = .15) -> dict:
    z = NormalDist().inv_cdf(.975) + NormalDist().inv_cdf(.8)
    raw = 2*z*z/(effect*effect)
    from math import ceil
    return {"raw_rounded_up": ceil(raw), "with_loss_rounded_up": ceil(raw/(1-loss)),
            "assumed_standardized_effect": effect, "loss_fraction": loss,
            "interpretation": "Normal approximation for a future two-arm study, not current power"}


def quadratic_kappa(pairs: list[tuple[int, int]]) -> float | None:
    """Quadratic weighted Cohen kappa for score categories 1–4."""
    if not pairs:
        return None
    n = len(pairs)
    left, right = Counter(x for x, _ in pairs), Counter(y for _, y in pairs)
    observed = sum((a-b)**2 for a, b in pairs) / (9*n)
    expected = sum((a-b)**2 * left[a] * right[b] for a in range(1,5) for b in range(1,5)) / (9*n*n)
    return None if expected == 0 else 1-observed/expected


def cluster_bootstrap_kappa(grouped: dict[str, list[tuple[int, int]]], *, draws: int = 500) -> dict | None:
    """Resample encounter clusters; N/A and degenerate replicates excluded."""
    if len(grouped) < 20:
        return None
    pairs = [pair for values in grouped.values() for pair in values]
    estimate = quadratic_kappa(pairs)
    if estimate is None:
        return None
    rng = random.Random(42)
    keys = sorted(grouped)
    samples = []
    for _ in range(draws):
        draw = [pair for _ in keys for pair in grouped[rng.choice(keys)]]
        value = quadratic_kappa(draw)
        if value is not None:
            samples.append(value)
    if len(samples) < draws * .8:
        return {"estimate": estimate, "ci95": None, "reason": "too many degenerate bootstrap replicates"}
    samples.sort()
    return {"estimate": estimate, "ci95": [samples[int(.025 * len(samples))],
            samples[min(len(samples)-1, int(.975 * len(samples)))]],
            "method": "encounter-cluster bootstrap, 500 draws, seed 42", "pairs": len(pairs),
            "encounters": len(keys)}


def reviewed_metrics(packets: list[dict], mapping: dict, review: dict,
                     conversations: list[dict], *, llm_predictions: dict | None = None,
                     judge_predictions: dict | None = None) -> dict:
    """All gates stay N/E on partial coverage. No fixture training or imputed labels."""
    protocol = json.loads(PROTOCOL.read_text())
    targets = protocol["proposed_engineering_targets_not_approved"]
    packet_by_id = {p["packet_id"]: p for p in packets}
    by_kind = defaultdict(list)
    for p in packets:
        by_kind[p["kind"]].append(p)
    complete = review["complete_by_kind"]
    resolved = review["resolved"]
    grounding, _ = load_previous()
    results = {"release": None, "semantic": None, "claim": None, "domain": None,
               "action": None, "pilot": None}
    gates = {"protocol_and_import_workflow": "PASS", "trained_action_extraction": "NOT EVALUABLE",
        "prompted_extraction_comparison": "NOT EVALUABLE",
        "clinical_disclosure_accuracy": "NOT EVALUABLE", "semantic_grounding": "NOT EVALUABLE",
        "faculty_feedback_accuracy": "NOT EVALUABLE", "faculty_rubric_agreement": "NOT EVALUABLE",
        "difficulty_calibration": "NOT EVALUABLE", "student_learning": "NOT EVALUABLE"}
    if complete.get("release"):
        expected = {mapping[p["packet_id"]]["key"]: resolved[p["packet_id"]]["expected_fact_ids"] for p in by_kind["release"]}
        tp = fp = fn = 0
        failures = []
        for run in grounding["runs"]:
            for turn in run["turns"]:
                key = f"{run['script_id']}:{turn['turn']}"
                actual, gold = set(turn["allowed_fact_ids"]), set(expected[key])
                tp += len(actual & gold); fp += len(actual-gold); fn += len(gold-actual)
                if actual != gold:
                    failures.append({"unit": key, "unexpected": sorted(actual-gold), "missed": sorted(gold-actual)})
        results["release"] = {"reviewed_turns": len(by_kind["release"]), "tp": tp, "fp": fp, "fn": fn,
            "precision": wilson(tp,tp+fp), "recall": wilson(tp,tp+fn), "failure_examples": failures[:10],
            "cluster_warning": "Facts within turns and turns within case are correlated; Wilson intervals are descriptive only."}
        gates["clinical_disclosure_accuracy"] = "PASS" if fp == fn == 0 else "FAIL"
    if complete.get("semantic"):
        eligible = {p["packet_id"] for p in by_kind["semantic"]}
        permitted = {p["packet_id"] for p in by_kind["semantic"] if not next(c for c in grounding["challenges"] if c["challenge_id"] == mapping[p["packet_id"]]["key"])["deterministic_blocked"]}
        if judge_predictions is not None:
            if set(judge_predictions) != permitted:
                raise ValueError("judge predictions must cover exactly every mechanically permitted reply")
            for row in judge_predictions.values():
                if not isinstance(row.get("predicted_supported"), bool) or not row.get("model_id") or not row.get("prompt_version"):
                    raise ValueError("judge verdict needs model ID, prompt version and boolean")
            confusion = Counter()
            failures = []
            for p in by_kind["semantic"]:
                pid = p["packet_id"]
                gold = resolved[pid]["expected_supported"]
                predicted = judge_predictions[pid]["predicted_supported"] if pid in permitted else False
                key = ("tp" if gold and predicted else "fn" if gold else "fp" if predicted else "tn")
                confusion[key] += 1
                if key in {"fp", "fn"}:
                    failures.append({"packet_id": pid, "type": key})
            tp, fp, fn = (confusion[k] for k in ("tp","fp","fn"))
            results["semantic"] = {"reviewed_candidates": len(eligible), "judged_permitted": len(permitted),
                **dict(confusion), "precision": wilson(tp,tp+fp), "recall": wilson(tp,tp+fn),
                "failure_examples": failures[:10], "judge_model_ids": sorted({x["model_id"] for x in judge_predictions.values()}),
                "prompt_versions": sorted({x["prompt_version"] for x in judge_predictions.values()})}
            gates["semantic_grounding"] = "PASS" if fp == 0 else "FAIL"
    if complete.get("claim"):
        support = sum(resolved[p["packet_id"]]["expected_supported"] for p in by_kind["claim"])
        results["claim"] = {"reviewed_claims": len(by_kind["claim"]), "supported": support,
            "support_rate": wilson(support,len(by_kind["claim"])),
            "failure_examples": [p["packet_id"] for p in by_kind["claim"] if not resolved[p["packet_id"]]["expected_supported"]][:10]}
        gates["faculty_feedback_accuracy"] = "PASS" if support == len(by_kind["claim"]) else "FAIL"
    domain_pairs = defaultdict(dict)
    for p in by_kind["domain"]:
        pid = p["packet_id"]
        if pid not in review["raw_pairs"]:
            continue
        a, b = (v["score"] for v in review["raw_pairs"][pid])
        if type(a) is int and type(b) is int:
            domain_pairs[p["context"]["domain_id"]][mapping[pid]["key"].rsplit(":",1)[0]] = [(a,b)]
    if domain_pairs:
        overall = defaultdict(list)
        for pairs in domain_pairs.values():
            for encounter, values in pairs.items():
                overall[encounter].extend(values)
        results["domain"] = {"double_rated_by_domain": {str(d): len(pairs) for d,pairs in domain_pairs.items()},
            "kappa_by_domain": {str(d): cluster_bootstrap_kappa(pairs) for d,pairs in domain_pairs.items()},
            "overall_kappa": cluster_bootstrap_kappa(overall),
            "na_excluded_by_domain": {str(d): sum(1 for p in by_kind["domain"] if p["context"]["domain_id"] == d and p["packet_id"] in review["raw_pairs"] and any(v["score"] == "N/A" for v in review["raw_pairs"][p["packet_id"]])) for d in range(1,8)}}
        if complete.get("domain") and all(results["domain"]["kappa_by_domain"].get(str(d)) is not None for d in range(1,8)):
            # Agreement has no preregistered numeric pass threshold yet.
            gates["faculty_rubric_agreement"] = "PASS"
    if conversations:
        split = split_audit(conversations)
        results["action"] = {"reviewed_action_turns": review["resolved_by_kind"].get("action",0),
            "total_action_turns": len(by_kind["action"]), "patients": split["patients"],
            "split_counts": dict(Counter(split["assignments"].values())),
            "cross_split_links": split["cross_split_links"], "model": None}
        if complete.get("action"):
            rows = action_annotations(packets,mapping,review,conversations)
            vocab = json.loads(VOCAB.read_text())
            model = evaluate_extraction(rows,conversations,vocab,"student_skill",predictions=llm_predictions)
            results["action"]["model"] = model
            if model["status"] != "NOT EVALUABLE":
                if model.get("llm",{}).get("status") == "EVALUATED":
                    gates["prompted_extraction_comparison"] = "PASS"
                per = model["per_class"]
                critical = targets["critical_actions"]
                if all(per[k]["support"] >= targets["min_test_positives_per_critical_action"] for k in critical):
                    gates["trained_action_extraction"] = ("PASS" if model["macro_f1"] >= targets["trained_macro_f1"]
                        and all(per[k]["recall"] >= targets["critical_action_recall"] for k in critical) else "FAIL")
        results["pilot"] = pilot_summary(conversations, packets, mapping, review, targets)
        # A future approved protocol and adequate randomized sample are needed
        # before the two-arm outcome is interpreted as learning efficacy.
    return {"results": results, "gates": gates}


def pilot_summary(conversations: list[dict], packets: list[dict], mapping: dict,
                  review: dict, targets: dict) -> dict:
    cohort = defaultdict(dict)
    for c in conversations:
        if c["phase"] in cohort[c["learner_id"]]:
            raise ValueError("one baseline and one follow-up per learner")
        cohort[c["learner_id"]][c["phase"]] = c
    arm_counts = Counter(next(iter(phases.values()))["arm"] for phases in cohort.values())
    missing = Counter()
    changes = defaultdict(list)
    resolved = review["resolved"]
    by_conversation = defaultdict(dict)
    for p in packets:
        if p["kind"] != "domain" or not mapping[p["packet_id"]]["key"].startswith("observed:"):
            continue
        conv_id = mapping[p["packet_id"]]["key"].split(":")[1]
        by_conversation[conv_id][p["context"]["domain_id"]] = resolved.get(p["packet_id"])
    for learner, phases in cohort.items():
        if set(phases) != {"baseline", "followup"}:
            missing["missing_visit"] += 1
            continue
        pre, post = phases["baseline"], phases["followup"]
        if pre["case_id"] == post["case_id"]:
            raise ValueError("follow-up outcome case must be held out from that learner's baseline")
        scores = (by_conversation[pre["conversation_id"]], by_conversation[post["conversation_id"]])
        if any(len(s) != 7 or any(v is None for v in s.values()) for s in scores):
            missing["unreviewed_domains"] += 1
            continue
        common = [d for d in range(1,8) if all(type(s[d]["score"]) is int for s in scores)]
        if not common:
            missing["no_common_domains"] += 1
            continue
        changes[pre["arm"]].append(mean(scores[1][d]["score"]-scores[0][d]["score"] for d in common))
    difference = None
    if len(changes["feedback"]) >= 2 and len(changes["standard"]) >= 2:
        a, b = changes["feedback"], changes["standard"]
        effect = mean(a)-mean(b)
        se = sqrt(variance(a)/len(a)+variance(b)/len(b))
        difference = {"estimate": effect, "ci95_normal": [effect-1.959963984540054*se,
            effect+1.959963984540054*se], "method": "exploratory unadjusted arm mean difference; learner is unit"}
    return {"learners": len(cohort), "by_arm": dict(arm_counts), "paired_scored_by_arm": {a: len(v) for a,v in changes.items()},
        "missing": dict(missing), "mean_change_by_arm": {a: mean(v) for a,v in changes.items()},
        "between_arm_difference": difference,
        "status": "NOT EVALUABLE", "reason": "Protocol/faculty ethics approval and adequate randomized sample required; authored fixtures excluded",
        "planning_n_per_arm": planning_n_per_arm()}
