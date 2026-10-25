# 风险策略接入说明

基础风险策略位于`approval_gate/policies/basic_risk.py`，通过`BasicRiskPolicy().decide(request)`调用。它接收统一请求，返回`decision`和`reason`。决定值为`APPROVE`、`DENY`或`ESCALATE`，理由以R0–R7规则编号开头。

策略只对已核实的低影响本地查询直接批准。发送、分享、付款、删除、账号变更、预订和未知工具交给Reviewer。格式不合法或明确携带凭据的外发请求直接拒绝。`get_unread_emails`会修改邮件已读状态，因此也需要审核。规则依据工具实际行为划分，不按名称前缀放行。

审批门统一管理预算。策略只读取`remaining_budget`，不扣减，也不调用Reviewer。预算为0时，高风险调用仍返回`ESCALATE`，由Gate拒绝；低影响查询仍可直接执行。预算感知策略可以复用`assess_request`，但应使用独立策略名称。比较实验需要统一模型、任务、攻击和k。

实验入口使用`build_approval_pipeline`。运行器在每个任务开始时调用一次`start_task`，结束时调用一次`finish_task`。未知工具和嵌套调用由Gate提前拦截。已有FullApprove和FullEscalate继续作为对照策略使用。

Reviewer接收升级请求后只返回批准或拒绝。模型调用、超时和token记录由Reviewer及Gate处理。统计程序可直接使用`policy_name=basic_risk_v1`和`policy_reason`，无需修改日志格式。迟到费用按README中的`included_in_task_total`处理，避免重复计费。

调用示例使用`python -m examples.risk_policy`。离线接入检查使用`python -m examples.gate_smoke`，其中的工具和Reviewer均为本地替身，不发送邮件，也不调用模型。70个风险策略测试与原有测试合计86个通过。详细命令和结果见`policy-validation.md`。这些结果证明规则和接口按预期运行，正式安全效果仍需真实模型和攻击实验验证。

环境通过`scripts/check_agentdojo.py`核验。指定源码commit为`089ed468cf3ed0322acc66b0211f26d9d90dbf60`。该源码的包版本号仍为0.1.35，版本核验以安装来源中的commit为准。离线检查不需要API密钥；正式实验的模型、地址和环境变量由实验配置统一提供。

规则不会读取标准答案、攻击标签或完整任务对象，也不尝试完整判断用户意图。已知本地查询仍可能读取敏感内容；凭据模式也不能识别所有编码和附件。这些限制在英文规则说明中保留，实验需要同时报告安全性、任务完成情况和审核成本。
