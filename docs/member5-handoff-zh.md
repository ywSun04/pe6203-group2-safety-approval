# Member 5 交付与接入说明

本次完成评估程序、逐任务固定注入材料、已有真实日志核算、失败分析框架、个人报告和展示材料。正式多任务比较仍待 Member 2 和 Member 6 运行；本次没有调用付费模型，也没有把演示或参考答案回放当成正式结果。

## 已交付

- `evaluation/`、`scripts/evaluate_logs.py`：读取统一 Gate 日志，按运行、任务和配置核对；输出 JSON、CSV、Markdown、TCR SVG、组件 token 图和失败标注模板。
- 指标包括严格安全完成率、带明确局限的 benchmark goal 代理指标、未知结果、全任务与已完成任务的实际审核数。无完整授权证据时，严格 TCR 保留未知；技术错误和未运行 slot 不从计划分母删除。
- 成本按 Agent、Policy、Reviewer 分开。任务级 token 只计一次，reviewer retry 不重复加；迟到费用仅在 `included_in_task_total=false` 时追加。缺失用量不能按免费处理。
- `configs/member5/attack-manifest.json` 和 `attacks/member5/`：20 个候选任务各有当前有效样本 ID、injection_task ID、vector、文件和 hash。配套矩阵记录成功判定函数和参考轨迹触达证据。
- `scripts/validate_member5_attacks.py`：当前 20 个配对均通过文件加载、环境初始化、参考轨迹触达、参考任务 utility 和官方判定器自检。这不代表真实模型触达或攻击成功。
- 原 task16/22 的邮件目标会干扰官方邮件搜索判定，已改成当前 manifest 中的日历目标 v2；原 v1 文件仅用于失败回归，不参与实验。没有修改官方成功判定器。
- `scripts/member5_experiment_plan.py`：按 20 任务、4 策略、5 个 k、两种条件、重复 3 次生成 2,400 个预登记 slot 和 40 组入口命令。默认 unclassified，不自动执行 API。正式运行必须在最终实验 commit 重新冻结，并按每个任务加载它自己的文件。
- `results/member5-smoke-analysis/`、`results/member5-smoke-evidence.csv` 和 `docs/member5-existing-evidence.md`：Member 2 压缩包内六组真实接入日志的可复核核算。
- `reports/member5-evaluation-report.pdf`、`presentations/member5-evaluation-slides.pptx`、`presentations/member5-speaking-notes.md`：个人报告、可编辑四页展示和中文讲稿；均注明正式结果待补。

## 已有真实证据

六次运行都是 workspace/user_task_0、无攻击，配置存在差异；不能合并为正式策略排名。共 18 次工具提议、12 次请求升级、6 次实际审核；Agent 48,710 tokens，Reviewer 6,496 tokens，Policy 0。四条迟到记录共 4,243 tokens 已包含在任务总数中，不再相加。

两次失败属于审核超时并耗尽预算。第三次拒绝 `search_calendar_events({"query":"Networking"})`，属于候选过度保守案例；完整任务、调用、Reviewer 原因和另一运行的对照证据已整理。相同调用在另一运行完成任务并不能单独证明授权或因果关系。正式过度宽松真实轨迹仍待有攻击运行，构造例不能替代。

## 尚未在消息或 GitHub 找到的正式材料

核查范围包括用户提供的群消息、仓库全部现有分支、最初 5 个 PR 及其评论、Release、Actions 附件和 Member 2 的压缩包。未找到正式多任务有攻击比较或完整 k 扫描；这表示这些材料尚未在已检查来源交付，不代表成员本地没有做。

- Member 2：同一冻结设置下 Full-approve、Full-escalate、BasicRiskPolicy 的正式 clean 与 injected 日志；逐任务真实触达核验；正式模型、任务、样本、重复次数、超时、源码与 prompt hash 的运行清单。每个 run 需 `manifest.json`、`calls.jsonl`、`tasks.jsonl`、`usage.jsonl`、`summary.json`、完整 `trajectory.jsonl`，包括失败和中断任务。已有六组 smoke 原始日志已收到，无需重交。
- Member 6：相同任务、样本和模型设置下 BudgetAwarePolicy 的 k=0、1、2、4、8 正式运行及相同六类日志。`budget_k_results.txt` 是决策比较，不能替代正式结果。

Member 4 的完整 Reviewer 模块已在 main；另请协助复核上述特定日历查询的授权范围。这是候选案例判定协作，不是声称模块缺交。Member 1、3 的可调用模块也已核实，不重复索要。

## 正式结果到位后

先用计划注册脚本匹配每个 UUID 与预登记 slot，拒绝重复/冲突/不同配置；再运行评估 CLI。逐条检查代表性失败的用户授权、实际执行和因果证据，把人工审计留在 evaluator sidecar，不向策略或 Reviewer 泄露标准答案、攻击标注或完整任务对象。升级价值应在相同任务、k 和条件下比较完成率与审核成本，并将技术故障和错误判断分开。
