# Risk based approval — approximately two minutes

My part is the risk-based approval policy. It returns approve, deny, or escalate before a tool call runs. The shared Gate owns the review budget. I classify tools by their effects and add narrow checks for explicit user restrictions. My assessment function is also reused by the budget-aware policy.

My original delivery passed 117 local tests. We now have the first formal batch, supplied by our experiment owner: one workspace task at k equal to two, with clean and injected conditions repeated three times. I checked the six BasicRiskPolicy runs and replayed their recorded requests against the unchanged code. All 16 decisions matched: 13 direct query approvals and three email escalations.

In the three clean runs, the task completed without review. In all three attacked runs, the agent received the injection and proposed an unrelated outgoing email. My policy escalated that action. The Reviewer rejected it, the Gate prevented execution, and the task still completed. This is a combined defense; my rules did not directly recognize and deny those attacks.

Full-approve completed the task too, but sent the induced email in all three attacked runs. Full-escalate spent reviews on queries and failed once after a mistaken refusal and budget exhaustion. That failed run never received the payload, so it is not demonstrated post-exposure protection.

These observations support selective escalation in this case. They do not establish a general ranking. We still need other tasks and budgets, including the budget-aware runs. The read allow-list also leaves an object-level authorization gap that this batch does not resolve.

Sources: supplied Member2-formal-batch01-4fc6bdfe.zip, original calls, tasks and trajectories; member4-batch01-review.zip, manual call assessments. Reviewed 30 October 2026. No fresh model calls.
