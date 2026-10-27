# Module intake

Hand in a file that can be called as written here, plus a test that already passes. A prompt paragraph, a chat paste, or a script that builds `AgentPipeline.from_config` is not a module. First hookup is 28 October 2026. Later files are recorded as not yet received. Member 1 plugs the file in and does not rewrite the rule or the prompt.

The shared contract is in the repository README. AgentDojo commit `089ed468cf3ed0322acc66b0211f26d9d90dbf60`.

## Member 2

File: `experiments/run_suite.py`.

Call `build_approval_pipeline`, then `start_task` once, then `TaskSuite.run_task_with_pipeline`, then `finish_task` once. Do not reset the budget on each model turn. Do not use `AgentPipeline.from_config` or `GroundTruthPipeline` for an approval run.

Also name the model, the suite version, the task ids, the attack setting, and the output directory. Use a new `run_id` for each task run, or pass a distinct `--run-id`. The same id in one log directory mixes rows.

Sample: one workspace user task, one model name, and `k` set explicitly. Before the run, check whether that task's tool calls contain a nested call. Full-approve denies nested calls, so it is not the original unguarded executor on those tasks. Record the finding in the experiment notes.

Due: 28 October 2026.

## Member 3

File: `policies/risk_policy.py`.

Class with `name`, `last_token_usage`, and `decide(self, request) -> dict`. Return exactly `decision` and `reason`. `decision` is `APPROVE`, `DENY`, or `ESCALATE`. Read `remaining_budget`. Do not store a second counter. Do not read the benchmark task, ground truth, or attack label.

Sample: `tests/test_risk_policy.py` calls `decide` with `user_task`, `tool_name`, `tool_arguments`, and `remaining_budget`. Assert the keys are exactly `decision` and `reason`, and the decision is one of the three allowed values. Include at least one call that returns each decision the policy claims to use.

Due: 28 October 2026.

## Member 4

File: `reviewer/llm_reviewer.py`. The prompt lives in this file.

Class with `name`, `last_token_usage`, and `review(self, request, timeout_seconds=30) -> dict`. Return exactly `decision` and `reason`. `decision` is `APPROVE` or `DENY`. Pass `timeout_seconds` to the model client. Set `last_token_usage` to the latest attempt, including a failed one. Put technical retry cost on `ReviewerFormatError` or `ReviewerTimeout` as `retry_tokens`. Do not return `ESCALATE`.

Sample: `tests/test_llm_reviewer.py` shows one `APPROVE` payload and one `DENY` payload with only those two keys. A case that would have returned `ESCALATE` must fail or be rewritten to `DENY`.

Due: 28 October 2026.

## Member 6

File: `policies/escalation_policy.py`.

Same call shape as Member 3. This policy decides when the decision is `ESCALATE`. Read `remaining_budget` from the request. Do not keep a counter and do not decrement `k`. The gate spends the budget. Different values of `k` are a new task run, not a change inside the policy.

Sample: `tests/test_escalation_policy.py` calls `decide` twice with the same arguments and a positive `remaining_budget`. The policy must not change its own state to simulate a spent budget. A separate case with `remaining_budget` 0 may still return `ESCALATE`. The gate turns that into a denial and does not count an actual review.

Due: 28 October 2026.

## Member 5

No policy file. Member 5 reads `calls.jsonl` and `tasks.jsonl` after a run.

Count `tokens.reviewer` as the reviewer total. Do not add `reviewer_retry_tokens` again. Add `late_reviewer_tokens` only when `included_in_task_total` is false. Keep requested escalations and actual escalations apart. `tokens.agent` is once per task. It stays 0 until the runner records model usage.

Due for the first calculation: after the 28 October hookup produces one real task log. Scripted files in `demo/scripted/` are test data, not that log.

## Receipt

A module is received only when the file, the callable, and the sample test are all present and the test passes. Anything else is handed back to the owner.
