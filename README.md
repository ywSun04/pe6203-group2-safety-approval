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

`approval_gate.policies.BasicRiskPolicy` provides a budget-independent `decide(request)` component. It returns exactly `decision` and `reason`; the shared gate continues to own all review calls and budget changes. The current policy name is `basic_risk_v2`; it also checks supported explicit user prohibitions and single-recipient restrictions. `BudgetAwarePolicy` is the budget-aware component plugged into the same executor. See the next section.

See [Risk policy](docs/risk-policy.md) for the rule rationale, interface, installation, and examples. [Validation record](docs/policy-validation.md) records the checks actually run. Install `requirements.txt` and `requirements-dev.txt`, then run these commands from the repository root:

```text
python scripts/check_agentdojo.py
python -m pytest -q
python -m examples.risk_policy
python -m examples.gate_smoke --log-dir logs/gate-smoke
```

The policy example and gate smoke use synthetic inputs and no live model. Smoke logs are wiring checks, not benchmark results. Real experiments still use `build_approval_pipeline` and the model/reviewer supplied by the experiment team.

## Budget-aware policy

`approval_gate.policies.BudgetAwarePolicy` (`budget_aware_v1`) is wired into the same approval executor. It calls Member 3's `assess_request()` in `basic_risk.py` and does not keep a second copy of the risk rules. A baseline `APPROVE` or `DENY` is returned unchanged. A baseline `ESCALATE` becomes:

- `DENY` when `remaining_budget` is `0` (`B0_NO_REVIEW_BUDGET`)
- `DENY` when one review remains and the rule is not a sensitive read, external action, or financial action (`B1_RESERVE_LAST_REVIEW`)
- `ESCALATE` otherwise (`B2_REVIEW_REQUESTED`)

The executor still owns the budget. This policy never changes `remaining_budget` and never turns a risky call into `APPROVE` just because a review is available. Select it when building the gate:

```python
from approval_gate.executor import ApprovalGatedToolsExecutor
from approval_gate.pipeline import build_approval_pipeline
from approval_gate.policies import make_policy

gate = ApprovalGatedToolsExecutor(
    make_policy("budget_aware"),
    reviewer,
    gate_logger,
    k=k,
)
pipeline = build_approval_pipeline(config, gate)
```

`pipeline.name` then contains `budget_aware_v1` and the chosen `k`. An unregistered tool name is still rejected by the executor before this policy runs, so it does not spend budget.

Checks from the repository root:

```text
python -m pytest tests/test_budget_aware.py tests/test_budget_aware_gate.py -q
python -m tests.compare_budget_k
python -m examples.budget_gate_smoke --log-dir logs/budget-gate-smoke
```

`tests/compare_budget_k.py` and `budget_k_results.txt` compare policy decisions at k = 0, 1, 2, 4, and 8. Those rows are preliminary decision checks, not official AgentDojo task-completion results. Formal k sweeps stay with the experiment run after the shared benchmark settings are fixed.


## Individual report and presentation

`reports/risk-policy-report.pdf` is a six-page individual contribution report. Its first two pages cover implementation and validation contributions, and its third page covers reflection. The report separates observed local tests from formal AgentDojo results, which are still pending. `reports/risk-policy-report.md` is the editable text.

`presentations/risk-policy-slides.pptx` and `presentations/speaker-notes.md` support a two-minute individual presentation. The shared benchmark runner and real reviewer configuration remain experiment dependencies. No formal curves or cost figures have been inferred from fake-reviewer logs.

The two constructed failure examples can be reproduced with `python -m examples.policy_failure_cases --output local-traces.json`. They demonstrate a blocked safe send and an unchecked object-level read. Their diagnostic labels never enter the policy request and are not benchmark results.
