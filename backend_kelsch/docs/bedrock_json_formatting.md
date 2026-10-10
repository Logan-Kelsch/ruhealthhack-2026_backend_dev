# Bedrock encounter JSON formatting (E-06, E-14, V-01)

Some model responses contain a JSON object followed by prose, a bare verifier
list, or separate phraser objects. These are format errors, not usable verdicts.
The parser remains strict: it does not discard trailing prose, combine objects,
or turn a bare list into approval.

The phraser and verifier prompts now show complete supported and unsupported
examples. The client validates the expected fields and allows one fresh request
after a JSON parse or response-shape failure. It repeats the original input with
an explicit output-contract reminder; it does not ask the model to change its
factual verdict. An access, network, or service failure does not trigger this
formatting retry. A correctly formatted unsupported verdict is still blocked
by the verifier and handled by the existing encounter retry/fallback path.

If both format attempts fail, the encounter still uses its source-linked template.
Malformed citations, empty replies, and incomplete unsupported-claim entries are
rejected. This change does not alter disclosure rules, patient facts, model
routing, clinical review requirements, or learner gates.

Each attempt retains its own model, prompt version, success/error, latency and
token usage. Encounter traces and challenge evaluation include both attempts in
usage and cost totals. The `llm_judge.call` field remains the final attempt;
`llm_judge.calls` includes all attempts. No raw response or request is logged by
default. Keep private diagnostic captures and credentials outside Git.

Run the offline regression suite from the repository root:

```bash
LLM_ENABLED=false PYTHONPATH=backend python -m pytest -q backend/tests backend_kelsch/tests
```

After pulling this change, rerun the existing private live-evaluation command
with the same model configuration and separate output paths. Compare format
errors, fallback rate and total calls/tokens against the previous run. The
additional request can increase latency and cost; the tests establish retry and
accounting behavior, not an improvement in live model accuracy. A template or
model judge pass remains unreviewed, and clinical/student gates stay NOT EVALUABLE
without the required independent evidence.
