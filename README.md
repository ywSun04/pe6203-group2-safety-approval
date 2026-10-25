# Approval gate

`AgentPipeline.from_config` still builds a plain tool executor. Experiments must call `build_approval_pipeline` in `approval_gate/pipeline.py` so the approval executor is the one that runs.

The tests use a scripted model. They do not call a live model API. One test replays the ground-truth calls of workspace `user_task_0` through this gate. That is a connection check, not an official benchmark result.

The group uses AgentDojo commit `089ed468cf3ed0322acc66b0211f26d9d90dbf60` (2026-06-02). Do not install PyPI `agentdojo==0.1.35`. That release is older.

## Layout

- `approval_gate/contract.py`: four required fields, two optional fields, and the allowed decisions
- `approval_gate/executor.py`: the approval executor. Call `start_task` once per task, `query` on each agent turn, then `finish_task`
- `approval_gate/stubs.py`: always-approve and always-escalate baselines. They do not spend the budget
- `approval_gate/reviewer.py`: stand-in reviewer. A timeout or a bad payload becomes a denial
- `approval_gate/records.py`: one row per tool call in `logs/calls.jsonl`, one row per task in `logs/tasks.jsonl`
- `logs/`: created on the first run

The executor owns the budget. It resets to `k` at the start of a task. Every tool call in that task shares the budget. Starting a review spends one, even when the reviewer denies. When the budget is `0`, only `ESCALATE` becomes a denial. A direct `APPROVE` still runs.

Unknown tool names and nested tool calls are rejected before the policy runs, so they do not spend budget. The arguments shown to a policy are the arguments that will be executed. History keeps chat fields only, so a benchmark task object, label, or attack is not attached.

A reviewer call stops waiting after 30 seconds. The cutoff does not read the reviewer's shared token counter. If the call finishes later, its cost is appended as `late_reviewer_usage` with `included_in_task_total`. Add that cost again only when the field is false. A call that is still queued when its deadline passes does not start the model. A real reviewer must use the supplied timeout on its model client. `tokens.reviewer` includes failed calls and retries. `reviewer_retry_tokens` is the retry portion already included in that total.

`pipeline.name` includes the model, policy, `k`, and a config id. AgentDojo stores results under that name, so those runs do not reuse one another's cache.

## Basic risk policy

`approval_gate.policies.BasicRiskPolicy` provides a budget-independent `decide(request)` component. It returns exactly `decision` and `reason`; the shared gate continues to own all review calls and budget changes. The budget-aware strategy remains a separate comparison.

See [Risk policy](docs/risk-policy.md) for the rule rationale, interface, installation, and examples. [Validation record](docs/policy-validation.md) records the checks actually run. Install `requirements.txt` and `requirements-dev.txt`, then run these commands from the repository root:

```text
python scripts/check_agentdojo.py
python -m pytest -q
python -m examples.risk_policy
python -m examples.gate_smoke --log-dir logs/gate-smoke
```

The policy example and gate smoke use synthetic inputs and no live model. Smoke logs are wiring checks, not benchmark results. Real experiments still use `build_approval_pipeline` and the model/reviewer supplied by the experiment team.
