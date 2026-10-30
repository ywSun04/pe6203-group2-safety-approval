# Risk based approval — two-minute speaking script

## Slide 1

My part is BasicRiskPolicy. It checks each proposed tool call and returns approve, deny, or escalate. The Gate manages the review budget. I classify tools by their effects and add narrow checks for explicit user restrictions. A matching recipient does not automatically approve a message. My assessment function is also reused by the budget-aware policy.

I delivered the implementation, examples and tests. My initial validation passed 117 tests. I later replayed the 16 BasicRiskPolicy calls from the first formal batch. Their decisions and reasons matched the logs.

## Slide 2

The batch covers one task at k equal to two, repeated three times with and without injection. In all three clean runs, the task completed without review. In all three attacked runs, the agent received the injection and proposed an unrelated email. My policy escalated the send. The Reviewer denied it, the Gate prevented execution, and the task completed.

Full-approve also completed the task but sent the induced email in every attacked run. Full-escalate completed two of three attacked runs. Its failed run rejected a relevant query before exposure, then exhausted the budget. That is not demonstrated post-exposure protection.

These cases show why selective escalation can help. They do not establish a general ranking or a full TCR curve. My policy still has a limit: allowing a query tool does not prove permission to read the specific object. That needs stronger task-to-resource checks.

## Sources and timing

Supplied Member2-formal-batch01-4fc6bdfe.zip, original manifests, calls, tasks and trajectories; member4-batch01-review.zip, manual review. Frozen source 4fc6bdfe. The 117-test result dates to 26 October; the formal batch was reviewed on 30 October 2026. Actual duration depends on speaking speed; rehearse aloud. Sources and this timing note are not part of the spoken script.
