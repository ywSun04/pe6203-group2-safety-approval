# Member 2 experiment entry

## Scope and status

`experiments/run_suite.py` uses the group's `build_approval_pipeline` and real
`LlmReviewer`, then calls start_task once, TaskSuite.run_task_with_pipeline, and
finish_task once per run. No API calls occur unless `--live` is specified.
The delivered tests use mock HTTP and task ground-truth replay only. They do
not establish live model performance. Live validation is still required.

This runner supports clean tasks and a fixed injection JSON file, sequential
task/policy/k/repetition sweeps. It does not generate adaptive attacks, use an
LLM attacker, resume cached results, or claim exhaustive safety evaluation.
Each invocation reruns tasks into fresh UUID directories. It never silently
reuses AgentDojo cached results.

## Dependencies and environment

Use Python 3.11 and the shared pinned AgentDojo source commit
`089ed468cf3ed0322acc66b0211f26d9d90dbf60`. Keep Member 4's Reviewer files and
requirements-reviewer.txt in the local integration branch. On macOS:

```sh
uv pip install -r requirements-dev.txt -r requirements-reviewer.txt --python .venv/bin/python
.venv/bin/python -m pytest tests/test_member2_runner.py -q
```

No additional dependency is introduced: httpx and openai are installed by the
shared experiment/Reviewer dependencies. The serialization helpers are private
interfaces of the pinned AgentDojo source; revalidate before changing that commit.

Set OPENAI_COMPATIBLE_BASE_URL to https://openrouter.ai/api/v1 and
OPENAI_COMPATIBLE_API_KEY locally. Set REVIEWER_BASE_URL to the same endpoint,
REVIEWER_MODEL to openai/gpt-4o-mini and REVIEWER_API_KEY locally. The two roles
may share the same key/credit cap. Never commit keys or dump process environment.
Reviewer model choice is explicit, and live compatibility must be checked.

## First clean task

Offline preflight (no key required, no HTTP):

```sh
.venv/bin/python experiments/run_suite.py --k 0 --policies full-approve --log-dir logs/member2
```

First paid run, only after reviewing the plan:

```sh
.venv/bin/python experiments/run_suite.py --live --k 0 --policies full-approve --log-dir logs/member2
```

This first full-approve run calls the agent, but does NOT validate live Reviewer
judgments: it routes no calls to the Reviewer. To exercise a real review:

```sh
.venv/bin/python experiments/run_suite.py --live --k 2 --policies full-escalate --log-dir logs/member2-review
```

Explicit settings and sweep example (each combination is a new task run):

```sh
.venv/bin/python experiments/run_suite.py --suite workspace --suite-version v1.2.2 --tasks user_task_0 --model-id openai/gpt-4o-mini --policies full-approve full-escalate basic_risk budget_aware --k 0 1 2 4 --repeat 1 --log-dir logs/sweep
```

The sweep above is ONLY a plan until --live is added. Coordinate task selection,
attack payloads, budget settings and repeats with Members 5 and 6 before spending.
No dollar cap is enforced. Agent attempts are capped at 20 per task, at most
2048 output tokens each, with a 60-second HTTP timeout. There are no SDK or outer
agent retries; Reviewer retains Member 4's implementation and 30-second timeout.
An API error or cap hit is recorded as an error with unknown utility/security,
not a fabricated benchmark failure result. Include these runs in the planned
denominator and report their technical-error rate separately.

## Fixed injection experiment

Supply a JSON object mapping actual suite vector IDs to payload strings, e.g.
an exported and agreed attack fixture. Pass --attack file --attack-file PATH
--injection-task injection_task_0. Validate all task/attack pairings before a
formal comparison. For multi-task sweeps the same payload map is applied to
each selected task. Select payloads visible to the chosen tasks. Attack metadata
stays in the evaluator/manifest; only intended injected environment text reaches
the agent. Ground-truth labels and evaluator diagnostics are not reviewer fields.

IMPORTANT: pinned AgentDojo injection_task.security() returns attacker-goal
achievement. The runner negates that value for Gate security_passed and also
stores raw_benchmark_security and attack_success in summary.json. Without an
injection task, AgentDojo returns security=True unconditionally; a clean run
alone does not measure prompt-injection resistance or all unauthorized actions.
Formal TCR claims must state which benchmark goal-based safety check is used.

## Logs, nested calls, and cost accounting

Every run creates a distinct output directory containing manifest.json,
calls.jsonl (if tools were proposed), tasks.jsonl, summary.json, usage.jsonl,
and trajectory.jsonl. The manifest hashes settings, prompt, runner and fixed
attack payload. The pipeline name includes agent model, policy, k and the
configuration hash. Keep the exact integration Git commit alongside shared
results; changing policy/Gate code requires a new experiment version.

Preflight inspects the selected task's ground-truth call arguments on a separate
benchmark environment. No calls execute and none of these reference calls enter
the model pipeline. This only reports expected/reference nested calls, NOT proof
that a generated live trace has none. summary.json separately records whether
a live call was blocked as nested. Unknown preflight status must be reported.
Full-approve still rejects nested/unknown/empty calls before policy evaluation;
on such calls it differs from the original unguarded executor. It is a gated
full-approve comparison, not automatically an identical unguarded baseline.

Agent response usage is added once per HTTP response via gate.add_agent_tokens,
including a response later rejected by parsing. usage.jsonl stores separate
agent/reviewer prompt/completion counts when supplied. Match api_attempt and
api_response by component/attempt: a missing response or usage_known=false is
UNKNOWN cost, not zero. HTTP response tokens do not prove final provider billing.

tasks.jsonl tokens.reviewer already includes reviewer retries. Do not add
reviewer_retry_tokens again. Follow Gate late_reviewer_usage and
included_in_task_total exactly. usage.jsonl is an independent diagnostic ledger:
do not add its totals on top of Gate totals. It can also receive late response
rows. Reconcile unknown cost with provider balance/billing and record timestamps.
BasicRiskPolicy and BudgetAwarePolicy here use no policy-model inference.

Full trajectories and tool arguments may contain task data; review them before
sharing. Local logs stay under gitignored logs/. Never commit credentials.

## Delivery validation

On 2026-10-27, the 188 existing local integration tests plus 14 runner tests
passed together (202 passed). An offline CLI preflight for workspace v1.2.2
user_task_0 completed and found no nested calls in its reference arguments.
No live provider requests were made. One pytest cache-location warning occurred
when testing files across directories; test execution completed successfully.

## Configurable Reviewer timeout

--reviewer-timeout SECONDS controls Gate and Reviewer deadline (default 30).
It is recorded in the plan, manifest and configuration hash. A different timeout
is a different experimental configuration. Keep it identical across comparisons.
Initial live full-escalate k=2 on workspace/user_task_0 had two Reviewer timeouts
at 30 seconds and two subsequent budget-exhausted denials. Those are technical
timeout failures, not evidence of incorrect approve/deny judgments. A longer
deadline requires a separately labelled rerun. Previous raw logs are preserved.

## Connection cap after local diagnosis

--connect-timeout defaults to 2 seconds and is recorded in the plan, manifest,
configuration hash and attempt rows. The per-request hook caps only connect
timeout after SDK with_options has applied the Reviewer remaining deadline.
Read/write/pool timeouts, TLS verification, retry settings, reviewer prompt and
Gate decisions remain unchanged. A shorter connect cap can cause earlier
connection failures on slow networks; it is not a total request timeout.

Local free HTTPX tests on 2026-10-27 observed about 20 seconds establishing
connections with connect=10, versus about 4 seconds with connect=2. This supports
using a shorter connection cap on this machine; the exact failing address was
not identified. Keep all connection/deadline settings fixed across comparisons.
Live model validation after this transport change is still pending.
