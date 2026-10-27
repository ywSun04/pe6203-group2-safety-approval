# Risk based approval speaking notes

Target: approximately two minutes. These notes follow the later individual presentation instruction supplied for 1 November. The original Case 2 handout states a ten-minute group presentation plus Q&A; the group should confirm the combined running order. Actual speaking time depends on pace.

## Slide 1 Risk based approval

My part is the risk-based approval policy. It returns approve, deny, or escalate before a tool call runs. The gate manages the review budget, so my policy never deducts it.

I classify tools by their effects. Known local queries may run directly. Sending, sharing, payments, deletion, and account changes need review. For example, getting unread emails also marks them as read, so I do not treat that tool as a harmless query.

I added checks for explicit user restrictions. A supported instruction such as “Do not send emails” blocks a conflicting call. A single-recipient restriction also checks cc and bcc. Matching a restriction does not automatically approve a write. Unclear cases still need review.

## Slide 2 Validation and limits

The current repository passes 117 tests. The gate tests confirm that budgets are shared across turns and reset per task. At zero budget, an escalation is denied without calling the reviewer, while an approved query can still run.

I also included two local failure examples. A safe email is blocked when no review budget remains. In the other example, a wrong-object read passes because a read allow-list does not prove that the user authorised that file.

These are constructed examples, not formal benchmark results. We still need the real agent, reviewer, and attacks to compare TCR, review load, and cost. The main design choice is to enforce clear restrictions without treating all uncertain actions as safe.

## Sources

Group Project 2: Safety Approval Policies for Agent Harnesses. PE6203, supplied Case 2 handout, secs. 2–4.

“email_client.py.” AgentDojo, commit 089ed468cf3ed0322acc66b0211f26d9d90dbf60, https://github.com/ethz-spylab/agentdojo/blob/089ed468cf3ed0322acc66b0211f26d9d90dbf60/src/agentdojo/default_suites/v1/tools/email_client.py. Accessed 26 Oct. 2026.

Local evidence: tests/test_basic_risk_policy.py, tests/test_authorization_rules.py, tests/test_basic_risk_gate.py, tests/test_failure_examples.py and docs/policy-validation.md. The 117 figure is the observed local test count, not benchmark success.
