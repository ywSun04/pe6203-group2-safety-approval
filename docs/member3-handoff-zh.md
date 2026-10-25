# 成员三交接说明

本次交付是基础风险策略代码，不是之前Morning Bean的风险治理报告。规则模块位于`approval_gate/policies/basic_risk.py`，由`BasicRiskPolicy().decide(request)`调用。调用示例、Gate接入示例、测试、开发依赖和安装核验脚本均已随代码提交。

我按组长最新消息保留四个必填输入和两个可选输入，输出只有`decision`及`reason`。决定值严格使用`APPROVE`、`DENY`、`ESCALATE`。策略不接触标准答案、攻击标签或完整任务对象，也不消耗审核预算。

这套基础规则只对已检查的低影响本地查询直接批准。发送、分享、付款、删除、账号变更、预订和不明工具都交Reviewer判断。明显的凭据外发和不合法输入直接拒绝。`get_unread_emails`虽然名字像读取，源码会修改已读状态，因此也升级。基础策略没有承诺完整理解用户意图；Reviewer需要进一步检查目标、对象和任务是否一致。

预算为0时，策略仍把高风险调用返回为`ESCALATE`，由Gate最终拒绝；低影响查询仍可批准。策略不自行降级、不扣预算、不自己调用Reviewer。Member 6另交预算感知策略，可复用`assess_request`的固定规则，但需保留独立策略名称并说明是否组合。比较实验应使用相同模型、任务、攻击和k，避免把规则变化与预算机制混为同一因素。

Member 2接入时使用`build_approval_pipeline`，不要使用原始无审批的工具执行器。运行器每任务一次`start_task`，结束时一次`finish_task`。工具未知或嵌套调用由Gate提前拒绝，本策略不重复处理，也不把这类拒绝计作人工介入。FullApprove/FullEscalate继续使用组长原有实现，不重复提交。

Member 4的Reviewer仍负责模型、prompt、超时和token。策略升级后由Gate调用它，Reviewer不能再升级。预算耗尽、超时、格式错误和真实拒绝按原Gate处理，成员三不另开第二套路径。Member 5可以使用既有`policy_name=basic_risk_v1`和`policy_reason`中的R0–R7规则编号，不需要新日志格式；迟到费用仍按原README的`included_in_task_total`处理。

本次70个成员三测试与原仓库测试合计86个通过，离线示例也已实际运行，详情见英文validation记录。所有新测试输入是构造示例，不是拿攻击标准答案调出来的规则。假Reviewer和假工具只证明模块能接通，日志不是正式实验。真实模型、Reviewer及正式实验仍由相应成员接好后再运行，不能填造通过率。

我核对了当前远程main及其README。当前revision为`5eb4f9237ef271ac03daacbfea18199b32fadb50`，尚无群消息提到的`docs/module-intake.md`、What to hand in和Run one task段落。本模块按已存在的contract和pipeline实现，并补齐群消息要求的交付内容。如果组长另有未推送的接收清单，需要在联调时再核对，不声称已经读过不存在的文件。

AgentDojo已经按指定commit安装。包显示0.1.35并不表示装错，安装来源元数据确认为`089ed468cf3ed0322acc66b0211f26d9d90dbf60`。环境脚本会核验该值。没有使用真实模型密钥，测试也不需要密钥。以后正式实验的模型、服务地址、环境变量和攻击配置仍由成员二统一，成员三不擅自补默认值。

中文说明和英文技术文档区分了源码事实、固定规则设计和未验证边界。文档中的公开来源按MLA格式注明。Codex协助了实现和测试准备；规则的实际实验效果尚未知，不把代码测试通过当作安全保证。
