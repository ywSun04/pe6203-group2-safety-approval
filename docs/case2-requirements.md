# Case 2 requirements and current evidence

## Source and scope

This review uses the supplied English Case 2 handout, the bilingual copy of the same brief, the current repository, and the group lead's interface messages. The screenshot assigns the risk-based policy role responsibility for rules, authorisation judgement, implementation, tests, and reporting. It is a division-of-work proposal rather than a replacement for the course requirements.

The existing uploaded code belongs to the approval-policy project. No Morning Bean design content is part of this repository. The revision keeps the same public interface and shared gate, and adds supported explicit authorisation checks to the risk rules. The policy remains separate from the budget-aware strategy.

## Implemented component

BasicRiskPolicy exposes the four required fields and two optional fields through the existing request contract. It returns exactly decision and reason, with APPROVE, DENY, or ESCALATE. It does not spend the review budget, call the reviewer, receive benchmark labels, or access task/evaluator objects. The gate remains responsible for each tool call, shared task budget, invalid reviewer output, timeout handling, and final logs.

The current policy name is basic_risk_v2. R8 blocks supported direct prohibitions in the user's task, and R9 checks an explicit single-recipient restriction across all applicable destinations. These are narrow English-language checks, not complete semantic authorisation. Conditional or indirect instructions are not interpreted as a grant. Matched scope still does not auto-approve a write. The query allow-list does not prove permission for a particular file.

## Verified local evidence

The revised checkout passes 117 tests: 101 policy-related checks plus 16 pre-existing shared tests. The callable example, fake-tool gate example, source-commit checker and dependency check were executed. The two constructed failure traces are reproducible with examples.policy_failure_cases. They show a blocked safe send at k=0 and an allowed wrong-object read. Their labels are external diagnostics and never enter the policy request. Shared task utility/security remain null in these local traces.

This is evidence for implementation and integration. It does not replace a live AgentDojo evaluation or establish the quality of a real reviewer. The current main branch still provides only the fake reviewer and scripted connection tests. The model, real reviewer configuration, and formal run results were not supplied or assumed.

## Formal evaluation still required

The report requires TCR@k curves against both FullApprove and FullEscalate over an agreed range of k. TCR counts the joint event of completion and no unauthorised execution, not unit-test pass rate. The selected tasks, attacks, model, reviewer and seeds must be fixed and recorded for fair comparisons.

HITL counts actual reviewer invocations. Exhausted escalation requests do not count. The handout describes completed-task load in section 3.1 and asks for suite-wide totals in section 4.2. The analysis should report both with clear denominators. Agent, policy and reviewer tokens/cost must remain separate. Retry and late usage follow the existing gate's inclusion flags.

The final experimental report also needs real over-conservative and over-permissive trajectories, together with escalation-value analysis. The constructed examples help debugging but must not be relabelled as benchmark trajectories. The deterministic component has zero policy LLM tokens; the live agent and reviewer cost are unknown until those components run.

## Integration boundary

The experiment runner uses build_approval_pipeline and one start_task/finish_task pair per task. The current shared gate pre-rejects nested calls even under FullApprove. If selected tasks need nested calls, the baseline description must distinguish this common gate restriction from fully unguarded AgentDojo. This policy revision does not alter the gate to remove that distinction.
