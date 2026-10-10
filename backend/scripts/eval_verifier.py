"""Check the LLM verifier on hand-labeled patient lines (needs Bedrock).

    python -m scripts.eval_verifier [--runs 3]
Each item: a reply, the facts it may use, what the student said, and whether it should
pass. Writes docs/validation/verifier_eval.json. Add a line here whenever a live session
shows a wrong block or a wrong pass.
"""
import argparse
import json
from pathlib import Path

from app.encounter.verifier import judge
from app.schemas.case import Case

ROOT = Path(__file__).resolve().parents[2]
WALTER = Case.model_validate_json((ROOT / "cases" / "walter_greene.json").read_text(encoding="utf-8"))

# (label, reply, facts, student_said, should_pass)
ITEMS = [
    ("restate advice", "I didn't know that stuff about the heart and kidneys. Maybe I should ask the doc.", ["f_ibuprofen"],
     "Ibuprofen can be hard on the heart and kidneys. Could we talk with your doctor about something safer?", True),
    ("correct the student", "It's my back, not my knee. But yeah, I hear you.", ["f_ibuprofen"],
     "Could we talk with your doctor about something safer for your knee?", True),
    ("doubt about advice", "I'm still not sure how eating different is gonna stop me losing weight.", ["f_ibuprofen", "f_weight_loss"],
     "Can you tell me in your own words what we agreed on?", True),
    ("teach-back", "You said the Advil is rough on my heart and kidneys, so I should ask my doctor about something else.", ["f_ibuprofen"],
     "Ibuprofen can be hard on the heart and kidneys. Talk to your doctor about a safer option. What did we agree on?", True),
    ("plain feelings", "Look, I'm just tired of all of it.", [], "How are you feeling about all this?", True),
    ("don't know", "My what? I don't know what that is. Ask my doctor.", [], "What's your potassium level?", True),
    ("changed frequency", "Yeah, I take Advil for my back. Two, three times a week, maybe more.", ["f_ibuprofen"],
     "Do you take anything over the counter?", False),
    ("invented number", "My sugar was 300 last week, so yeah, it's bad.", ["f_ibuprofen"], "How has your sugar been?", False),
    ("invented relative", "My brother had a stroke, so I worry about that.", [], "Does anything run in your family?", False),
    ("invented duration", "My back, not my knee. And I've been taking Advil for years, it's fine.", ["f_ibuprofen"],
     "Could we talk with your doctor about something safer for your knee?", False),
    ("invented duration, other words", "I've had this back pain since my twenties.", ["f_ibuprofen"], "How long has your back hurt?", False),
    ("invented med", "I also take aspirin every morning.", ["f_ibuprofen"], "Any other medicines?", False),
    ("student number repeated", "So you want me under two thousand a day on the salt.", [],
     "Let's aim for under 2000 milligrams of sodium a day.", True),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=1)
    args = ap.parse_args()
    rows, correct, total = [], 0, 0
    for label, reply, facts, said, should_pass in ITEMS:
        for _ in range(args.runs):
            problems, call = judge(WALTER, reply, facts, [], said)
            passed = not problems
            ok = passed == should_pass
            correct += ok
            total += 1
            rows.append({"label": label, "should_pass": should_pass, "passed": passed, "problems": problems, "latency_ms": call.latency_ms})
            print(f"{'ok ' if ok else 'BAD'} {label}: passed={passed} {problems if problems else ''}")
    false_blocks = sum(1 for r in rows if r["should_pass"] and not r["passed"])
    misses = sum(1 for r in rows if not r["should_pass"] and r["passed"])
    summary = {"items": len(ITEMS), "runs": args.runs, "correct": correct, "total": total, "false_blocks": false_blocks, "missed_inventions": misses}
    print(summary)
    out = ROOT / "docs" / "validation" / "verifier_eval.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
