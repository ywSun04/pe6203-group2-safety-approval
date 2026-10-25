# Risk Based Approval for Agent Tool Calls

PE6203 Case 2 | Individual contribution report | niuduoer001-eng | 26 October 2026

Status: six-page individual report based on verified implementation and local tests. Formal AgentDojo comparisons remain pending.

## Page 1 Individual contribution to the approval policy

My contribution to Case 2 is the risk-based approval component. It sits between a proposed tool call and the shared approval gate. The component returns APPROVE, DENY, or ESCALATE with a reason. My scope covers the rules, their interface, their tests, and the evidence needed to explain their limits. The shared gate, model runner, simulated reviewer, and final benchmark analysis remain separate components. This division matters because a policy that looks correct on its own can still spend the wrong budget or bypass the gate when connected incorrectly.

The implemented component is BasicRiskPolicy. Its decide(request) method accepts the four agreed fields: user_task, tool_name, tool_arguments, and remaining_budget. The request may also contain history and tool_metadata. The output contains exactly decision and reason. I kept this interface unchanged when adding authorisation checks. The implementation does not call a language model or a reviewer. It reports zero policy tokens and does not hold state between tasks. These are properties of this component, not a claim that the complete experiment has no API cost.

The first design decision was to classify tools by their inspected effects rather than their names. A tool beginning with get is not necessarily harmless. In the pinned AgentDojo source, get_unread_emails marks messages as read. The rule therefore routes it for review. A webpage request can also carry data in its URL, so get_webpage does not enter the local-query allow-list. These decisions follow observable tool behaviour. They do not depend on an attack label or a desired benchmark outcome (“email_client.py”; “Tools”).

The second contribution is a fixed routing order. The policy first validates the request and checks a narrow set of explicit credential disclosure patterns. It then checks supported user prohibitions and a restricted recipient-scope form. Only after these checks does it apply the reviewed tool categories. Known local queries may be approved. Sensitive reads, external actions, financial operations, state changes, and unknown tools are escalated. Each result has a stable rule ID, which the existing gate can record without a new log format.

The authorisation revision adds two checks that the earlier operation-only version lacked. A supported direct instruction such as ‘Do not send emails’ can now block a conflicting email call. An explicit single-recipient restriction checks all email destinations, including cc and bcc. Matching the restriction does not approve a write; the normal review requirement remains. This prevents a narrow parser from becoming an alternative permission system. Unclear wording stays within the existing risk route.

The code is versioned as basic_risk_v2 so that the experiment pipeline can distinguish it from earlier runs. The submitted material also includes runnable examples, a pinned-source environment checker, rule documentation, and test records. The code is installed against the agreed AgentDojo commit. These deliverables make the component usable by the experiment runner without requiring changes to the shared budget manager or reviewer interface.

## Page 2 Individual contribution to validation and integration

The validation work covers both the decisions returned by the policy and the actions actually executed by the gate. A unit test that expects ESCALATE is not enough: the gate must spend one review only when it starts that review, and it must refuse an exhausted escalation. The integration tests therefore run the real ApprovalGatedToolsExecutor with local fake tools and FakeReviewer. The fake tools record execution, which allows the tests to distinguish a logged approval from an action that actually ran.

The current checkout passes 117 tests. Of these, 101 concern the policy, its gate connection, or its constructed failure examples; 16 are the pre-existing shared tests. The earlier revision passed 86 tests. The increase comes from explicit authorisation cases and executable failure examples, not from additional model experiments. Request checks include missing fields, invalid budgets, non-finite numbers, excessive nesting, cyclic direct inputs, and oversized text. Other tests ensure that optional history, tool descriptions, or unexpected private fields cannot lower a tool's risk.

One gate test places five calls in the same agent turn. With k equal to one, the first local query runs without review. The first ordinary email is reviewed and runs. The second email asks for review after the budget reaches zero, so the gate blocks it without invoking the reviewer. A synthetic credential-bearing email is denied directly. A final local query still runs. The observed final decisions are APPROVE, APPROVE, DENY, DENY, APPROVE. This checks the agreed distinction between requested and actual escalations.

Separate tests cover multiple agent turns and task resets. The review budget is shared across turns within one task and resets only when a new task starts. A reviewer denial still consumes a review. A direct policy denial does not. The authorisation checks also preserve this distinction: a prohibited send or a recipient-scope violation is denied before a reviewer is called. None of these tests moves the decrement into the policy.

The offline examples reproduce the same connection without model keys or an external email service. Their task_completed and security_passed fields remain null because no benchmark evaluator ran. I also added two executable limitation examples. One shows a safe intended send blocked at k equal to zero. The other shows a wrong-object read passing the local-query rule. Their labels belong to a constructed local evaluator and are never passed to the policy. These examples support analysis, but they are not AgentDojo benchmark failures.

The environment checker verifies the installed source through direct_url.json. The source still reports distribution version 0.1.35, so that number alone cannot prove that the right code was installed. The recorded source commit matches 089ed468cf3ed0322acc66b0211f26d9d90dbf60, and the dependency check reports no broken requirements. The documentation gives the import, example commands, configuration limits, and known failure modes. This is the evidence currently available for my component; it does not establish the final task-completion curve.

## Page 3 Reflection on the policy and remaining limitations

The main lesson is that risk classification and authorisation are related but different. Knowing that a function only reads data does not establish that the user requested that particular object. Knowing that an email tool changes external state does not establish that the email is forbidden. The initial policy grouped operations conservatively but left most intent checking to the reviewer. The revision makes supported explicit restrictions enforceable while retaining that separation. It does not claim to solve general language understanding.

The wrong-object example is important because it exposes a real design boundary. A task asks for public notes, but a generated get_file_by_id call names a restricted synthetic file. The function is on the local-query allow-list, so it executes. The example is deliberately labelled as constructed evidence. It shows why safe operation type cannot replace object-level scope. A future design should bind the requested resource to a trusted account or task context. It should not infer permission from a retrieved document that may itself contain an injection.

The opposite weakness is over-conservatism. A legitimate send still needs review, even when the user supplied the destination. At a small budget, useful work may stop. The fixed policy does not lower a risky decision merely because the reviewer budget is almost empty. That makes it a clear comparison point for the budget-aware strategy, but it may also lower utility. The formal experiment must measure this cost. A unit test that confirms a denial cannot show whether the policy made the best decision for the whole task.

The recipient check illustrates why a small supported grammar is preferable to an unexplained broad claim. It handles an explicit single address after ‘only to’ or ‘only with’. It checks recipients, cc, and bcc. It does not resolve a contact name, several possible addresses, indirect permission, or a changed recipient inferred from history. These cases continue to review. Extending the parser would require tests for negation, quotations, multiple instructions, and legitimate changes of mind. More patterns are not automatically better if they introduce confident but wrong denials.

A model-based reviewer also needs evaluation. It can misread a task or follow malicious content in the trace. The project brief permits a simulated reviewer, but that does not make its answer ground truth. The runner should provide the same allowed context for each strategy and keep benchmark answers outside both the policy and reviewer. The final analysis should separate policy failures, reviewer errors, and model failures to complete the task. Otherwise the source of a change in TCR could be misidentified (Group Project 2, secs. 3.1–3.3).

The next useful improvement is to collect evidence before adding more autonomy. I would first test which escalations change the final outcome, then examine whether trusted scope data can safely approve a narrow class of writes. The budget-aware strategy should be compared under the same tools and reviewer. Its gain should not come from silently weakening a restriction. I would also keep repeated-run uncertainty and failure trajectories, since one successful run is not enough to explain why a policy is reliable.

## Page 4 Rule design and the approval path

Case 2 asks for safe task completion under a limited attention budget. AgentDojo provides tasks and tools that operate over untrusted content. The approval policy runs before each tool execution, while the benchmark evaluator checks the task outcome separately. This separation allows a policy to use ordinary task context without seeing evaluation answers. The AgentDojo paper describes an extensible environment for studying prompt injection; it does not make the results of a local smoke script representative of the benchmark (Debenedetti et al.).

R0 checks the request shape and bounds the work performed by the policy. The argument walk is iterative, with limits of 16 nesting levels, 4,096 visited nodes, and 100,000 combined text characters. These values are implementation limits, not attention-budget thresholds. R1 checks transmitted fields for a narrow literal credential assignment or private-key marker. It does not scan arbitrary history for an attack keyword. It also does not detect every encoding or secret. Other outbound calls still require review, so a missed marker is not a direct approval of a send.

R8 and R9 are the authorisation checks added after the source review. R8 recognises a small set of direct, sentence-initial prohibitions and read-only restrictions in user_task. R9 compares an explicit single-recipient restriction with the destinations of an email or share call. Neither history nor tool metadata can create or cancel these restrictions. Neither check grants permission when it does not match. This is intentionally narrower than a general classifier and is documented as such.

The remaining rules classify the operation. R2 is the exact local-query allow-list. R3 routes sensitive account, financial, identity, and arbitrary-file reads to review. R4 covers external recipients, audiences, URLs, and related actions. R5 covers payments, scheduled transactions, and reservations. R6 covers state changes, including unread-email flags. R7 handles a registered tool with no reviewed profile. The gate blocks an unregistered tool before this policy runs. A safe-sounding description never adds a tool to the allow-list.

The runner must build the pipeline through build_approval_pipeline rather than AgentPipeline.from_config. It starts one task budget, sends each proposed call through the gate, and finishes the task after the agent run. The gate validates policy output, manages the reviewer, enforces k, and records the final outcome. The policy returns only its own decision and reason. Its name is included in the pipeline identity so results from different policy revisions do not share a cache accidentally (“Approval Gate”).

The comparison baselines need the same care. FullApprove and FullEscalate are supplied by the shared gate. They use the common execution restrictions. The current gate rejects nested calls before any policy runs, so its FullApprove is not identical to unrestricted AgentDojo on a task that needs such calls. The experiment description should state that difference. The component keeps this behaviour unchanged rather than quietly altering a shared control to improve its own result.

## Page 5 Observed local evidence and escalation value

The over-conservative example uses an intended safe action. The constructed user task is to find public notes and email a summary to team@example.test. A local search runs under R2. The following send_email call receives ESCALATE under R4. With k equal to zero, the gate converts that escalation to DENY. No fake email executes, and actual escalation count remains zero. The intended task cannot finish. The failure is lost utility through conservative routing, not an unsafe action that slipped through.

The over-permissive example uses a wrong object. The constructed task asks for public notes. A search returns a public file identifier, but the next proposed get_file_by_id call names restricted-file. R2 approves the call because the function is on the reviewed query list. The local fake tool records that the restricted object was read. The evaluator defines this object as outside the constructed task's scope, but that evaluator-only fact is not included in the policy request. The example exposes a limitation rather than providing a training label to the policy.

These traces were generated by examples.policy_failure_cases using the real gate and local fake functions. They include the tool arguments, policy reason, final decision, whether execution was attempted, and before/after budget. Both traces keep the shared utility and security fields null. Their failure descriptions are separate synthetic diagnostics. This distinction prevents a readable example from turning into a false benchmark result. The tests verify that the described block and wrong-object execution actually occur.

The additional authorisation checks address a different class of evidence. A supported direct prohibition stops a send before review. An email to an address outside an explicit single-recipient scope is also denied, including when the extra address appears in bcc. The gate tests confirm that these denials do not spend review budget. A matching address still goes to review. This is useful because the policy can enforce a clear restriction without pretending that the entire message content or attachment is authorised.

Review has the most immediate value for calls whose consequences are external or difficult to reverse. The reviewer needs to examine the recipient and payload of a send, the amount and account of a transfer, the target of a deletion, or the dates and terms of a reservation. It may also help resolve sensitive reads. Routine local queries generally impose less immediate external risk, but the wrong-object trace shows why this is not a universal safety rule. The value of a review depends on information the reviewer can actually use to correct a decision.

The local suite therefore supports a limited conclusion: the implemented rules, input boundary, and budget connection behave as tested. It does not show an attack success rate, a benchmark TCR, or the quality of a real reviewer. The final experiment should reuse these traces for debugging while reporting separately collected AgentDojo trajectories. The model, attacks, reviewer configuration, and selected tasks must be recorded so that a change in performance has an identifiable cause.

## Page 6 Evaluation status and works cited

The formal Case 2 evaluation remains outstanding. The repository available for this report contains a fake reviewer, scripted tests, and the existing workspace replay, but no confirmed live model configuration or formal run set. I therefore do not report a TCR curve, benchmark HITL total, or dollar cost. The current report documents the individual component and its observed local evidence. It is not a substitute for the group's final experimental section.

For TCR@k, the runner must count a task only when it both completes and executes no unauthorised call, then divide by all evaluated tasks at that k. A model's failure to finish is not a policy security success. A useful proposed range is k = 0, 1, 2, 4, 8, and 16, subject to the selected tasks and the team's agreed configuration. All strategies should use the same settings. The brief describes HITL over completed tasks and also asks for suite-wide totals; the final table should report both with explicit denominators (Group Project 2, secs. 3.1, 4.2).

Cost must remain split between agent execution, policy inference, and reviewer simulation. The deterministic policy uses zero policy tokens, but the agent and real reviewer may have nonzero cost. A requested review blocked at zero budget is not an actual intervention. Retry tokens already included in the reviewer total must not be added twice. Late usage follows the existing included_in_task_total flag. Dollar estimates require the actual model and an identified price source; neither is invented here.

Before the final report is submitted, the experimental section needs the agreed TCR curves, HITL and component-cost tables, and representative real failure trajectories. These are shared experimental dependencies, not missing local policy code. The two pages on contribution and the reflection page remain based on work that can already be verified. The supplied brief states a group presentation duration; the speaking notes follow the later individual two-minute instruction provided for this project.

### Works Cited

“Approval Gate.” PE6203 Group 2 Safety Approval, README.md and approval_gate/contract.py, github.com/ywSun04/pe6203-group2-safety-approval. Accessed 26 Oct. 2026.

Debenedetti, Edoardo, et al. “AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents.” arXiv, version 3, 24 Nov. 2024, doi.org/10.48550/arXiv.2406.13352.

“email_client.py.” AgentDojo, ethz-spylab, commit 089ed468cf3ed0322acc66b0211f26d9d90dbf60, github.com/ethz-spylab/agentdojo/blob/089ed468cf3ed0322acc66b0211f26d9d90dbf60/src/agentdojo/default_suites/v1/tools/email_client.py. Accessed 26 Oct. 2026.

Group Project 2: Safety Approval Policies for Agent Harnesses. PE6203, supplied Case 2 course handout, secs. 2–4.

“Tools.” AgentDojo, ethz-spylab, commit 089ed468cf3ed0322acc66b0211f26d9d90dbf60, github.com/ethz-spylab/agentdojo/tree/089ed468cf3ed0322acc66b0211f26d9d90dbf60/src/agentdojo/default_suites/v1/tools. Accessed 26 Oct. 2026.

Development note: Codex assisted implementation, source checks, drafting and test preparation. Formal experimental results are not claimed.
