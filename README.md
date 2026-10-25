# Member 1 第一步：审批门

这一步只有代码，还没有测试，也还没有换进 AgentDojo 的默认 pipeline。

全组锁定的 AgentDojo commit：`089ed468cf3ed0322acc66b0211f26d9d90dbf60`（2026-06-02）。不要用 PyPI 上的 `0.1.35`，那个版本更旧。

## 目录

- `approval_gate/contract.py`：四个必填字段、两个可选字段，以及允许的决定
- `approval_gate/executor.py`：审批执行器。每个任务先 `start_task`，每轮 Agent 回复调用 `query`，任务结束调用 `finish_task`
- `approval_gate/stubs.py`：永远批准、永远升级。预算不在这里扣
- `approval_gate/reviewer.py`：假审核员。超时或格式错误由门记成拒绝
- `approval_gate/records.py`：`logs/calls.jsonl` 每次调用一条，`logs/tasks.jsonl` 每个任务一条
- `logs/`：第一次运行时才生成

预算规则在执行器里：任务开始重置为 `k`；同一任务的调用共用预算；发起审核就扣 1，审核员拒绝也扣；预算为 0 时只有 `ESCALATE` 变成拒绝，直接 `APPROVE` 仍会执行。
