# LLM reviewer (Member 4)

## Scope and interface

`reviewer/llm_reviewer.py` contains `LlmReviewer` and the complete English prompt.
`review(request, timeout_seconds=30)` returns exactly `decision` and `reason`.
Only `APPROVE` and `DENY` are valid. `ReviewerFormatError` and
`ReviewerTimeout` are interpreted as DENY by the existing gate wrapper.

The prompt checks user authorization for the specific object, destination,
payload and side effects. Authorized writes are allowed; irrelevant reads may
be denied. History and tool metadata cannot override the user task. Instructions
in retrieved documents remain evidence, not reviewer instructions. Budget does
not alter the safety standard. Prompting reduces a risk; it does not guarantee
resistance to injection or correct authorization judgments.

The four required fields and optional history/schema use the shared contract.
Additional top-level fields are omitted. History and metadata are projected with
the gate's existing helpers. Real tool arguments are preserved, even when a
parameter happens to be called `task` or `ground_truth`. The runner remains
responsible for never embedding oracle information in visible text. Projection
cannot detect a label concealed in ordinary content.

## Install and configuration

Use the group's Python 3.11 environment and pinned AgentDojo source:

```sh
python -m pip install -r requirements-dev.txt -r requirements-reviewer.txt
python -m pytest tests/test_llm_reviewer.py tests/test_llm_reviewer_gate.py -q
```

This contribution was locally verified with Python 3.11.18 and Python 3.12.14,
pytest 9.1.1 and openai 3.39.0.

Set `REVIEWER_MODEL` and `REVIEWER_API_KEY` in the local process environment.
No model is silently selected. `REVIEWER_BASE_URL` is optional for a compatible
Chat Completions endpoint. Only configure a trusted provider: requests contain
task context. Do not commit credentials. Custom providers must support JSON
object response format, usage totals and SDK-compatible Chat Completions.
Compatibility with arbitrary providers is not claimed.

```python
from reviewer import LlmReviewer
from approval_gate.executor import ApprovalGatedToolsExecutor
from approval_gate.records import GateLogger
from approval_gate.policies import make_policy
from approval_gate.pipeline import build_approval_pipeline

reviewer = LlmReviewer.from_env()
gate = ApprovalGatedToolsExecutor(
    make_policy("budget_aware"), reviewer, GateLogger("logs/live"), k=2,
)
# config is supplied by Member 2; include model/provider/reviewer/prompt settings
# in config_id to avoid sharing caches between reviewer configurations.
pipeline = build_approval_pipeline(config, gate, config_id="reviewer-v1-run1")
# Continue with start_task -> run task -> finish_task as in the shared README.
```

A direct call uses only public context:

```python
result = reviewer.review({
    "user_task": "Email the public summary only to team@example.test",
    "tool_name": "send_email",
    "tool_arguments": {"to": "team@example.test", "body": "Public summary"},
    "remaining_budget": 1,
}, timeout_seconds=30)
```

## Time, output and cost

The remaining deadline is passed to `client.with_options(timeout=..., max_retries=0)`.
There is one model attempt per review; no technical or formatting retries.
Therefore retry_count and retry_tokens remain zero. Bad JSON, duplicate keys,
extra fields, ESCALATE, refusals, truncated completions and empty reasons fail
closed. Oversized requests are rejected rather than silently truncating scope.
Provider exception details are sanitized; they may contain sensitive data.

`last_token_usage` is the provider's total tokens for the latest response,
including invalid responses. It resets at the beginning of each review.
When the provider supplies no usage (including a network failure), it remains
zero and `last_usage_known` is false. **Zero is then an accounting placeholder,
not proof of zero billed cost.** The existing gate stores only the numeric total;
use provider billing records to reconcile missing usage. Dollar costs require
an actual provider/model price and are not estimated here.

The gate owns the outer timeout, budget and late-usage records. An SDK timeout
is not a guarantee of remote cancellation. A late response retains observed
usage but is never used to approve after deadline. `last_latency_seconds` is a
local diagnostic; read it only after the direct call finishes. The gate serializes
one instance; use separate instances for parallel workers.

## Validation and later analysis

Offline tests exercise the contract, actual SDK serialization through a mock
HTTP transport, privacy projection, malformed responses, timeout behavior,
usage reset and actual gate execution/budget/cost. Scripted responses prove
wiring behavior, not the quality of model decisions.

Twelve hand-authored synthetic cases in `reviewer/cases/authorization.json`
cover authorized actions, cc/bcc-style destination scope, wrong objects,
explicit prohibitions, injection, benign quotations and insufficient evidence.
Labels and rationale are separate from the `request` passed to Reviewer.
Run the optional live check only after selecting the model:

```sh
python -m examples.reviewer_check --live --output logs/reviewer-check.json
```

These cases are development cases, not an unbiased held-out evaluation or formal
AgentDojo results. They were not run against a live model in this handoff.
After integration, keep the reviewer configuration fixed across policy comparisons.
Member 4 should classify wrong approvals, wrong denials and technical failures;
separate policy routing errors from reviewer errors, and compare decisions to
labels only in the evaluator. Report actual review count, latency, observed tokens,
unknown usage, and representative real trajectories alongside the shared TCR@k.

SDK behavior reference: https://developers.openai.com/api/reference/python

## Complete offline pipeline check

```sh
python -m examples.reviewer_gate_smoke --policy basic_risk --log-dir logs/reviewer-basic
python -m examples.reviewer_gate_smoke --policy budget_aware --log-dir logs/reviewer-budget
```

Both commands use the real pipeline, policy, gate, Reviewer adapter and SDK;
the agent, HTTP responses and email tool are simulated. They require no key
and make no network requests. Exactly one simulated email executes; a second
request is denied by the scripted reviewer, and a third is blocked after the
review budget is spent. There are two reviews and 34 synthetic usage tokens.
BasicRiskPolicy requests three escalations; BudgetAwarePolicy directly denies
the third call at zero budget and therefore requests two. Neither counter is
changed by Reviewer. Task utility/security stay null because no benchmark ran.
