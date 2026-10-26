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

Budget-Aware Policy (Member 6)

Overview

The BudgetAwarePolicy implements a budget-aware approval strategy for tool calls. It combines risk assessment with the remaining human-review budget to determine whether a tool call should be approved, escalated for review, or denied.

The implementation follows Approach A by reusing Member 3's "assess_request()" function from "basic_risk.py", avoiding duplicated risk assessment logic.

Implementation

- Policy implementation: "approval_gate/policies/budget_aware.py"
- Risk assessment dependency: "approval_gate/policies/basic_risk.py" (Member 3)
- Unit tests: "tests/test_budget_aware.py"

The policy considers the risk of a requested tool call and the available review budget. Budget exhaustion must not cause unsafe requests to be automatically approved.

Testing

The Member 6 unit tests can be executed from the repository root using:

python -m pytest tests/test_budget_aware.py -v

The tests cover:

- Policy interface compatibility
- Safe and sensitive read operations
- Financial actions and unknown tools
- Explicit user prohibitions
- Budget preservation
- Deterministic decisions

Local test result: 10 passed.

The full repository test suite can be executed using:

python -m pytest tests/ -v

Local full-suite result: 26 passed.

Integration Notes

BudgetAwarePolicy depends on Member 3's risk assessment implementation. Both files must be available when running the policy.

The policy is developed and tested independently on the Member 6 branch before integration into the main project.
