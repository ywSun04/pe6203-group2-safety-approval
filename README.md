# Approval gate

`AgentPipeline.from_config` still builds a plain tool executor. Experiments must call `build_approval_pipeline` in `approval_gate/pipeline.py` so the approval executor is the one that runs.

The tests use a scripted model. They do not call a live model API.

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

A reviewer call stops waiting after 30 seconds. The cutoff does not read the reviewer's shared token counter. If the call finishes later, its cost is appended as `late_reviewer_usage` and added to the open task. A real reviewer must use this same timeout on its model client. `tokens.reviewer` includes failed calls and retries. `reviewer_retry_tokens` is the retry portion already included in that total.

`pipeline.name` includes the model, policy, `k`, and a config id. AgentDojo stores results under that name, so those runs do not reuse one another's cache.
