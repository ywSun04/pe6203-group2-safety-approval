# Scripted demo

These logs are test data. A fake reviewer and a local `read_file` tool produced them.
They are not a live-model result and not an official AgentDojo benchmark result.

- `reviewer-approves`: the reviewer returns APPROVE, and the tool runs.
- `reviewer-denies`: the reviewer returns DENY, the tool does not run, and the budget still decreases by one.
- `budget-exhausted`: the first escalation uses the only budget unit. The second escalation is denied and does not call the reviewer.

```json
{
  "reviewer-approves": {
    "executed": [
      "notes.txt"
    ],
    "reviewer_calls": 1
  },
  "reviewer-denies": {
    "executed": [],
    "reviewer_calls": 1
  },
  "budget-exhausted": {
    "executed": [
      "first.txt"
    ],
    "reviewer_calls": 1,
    "requested_escalation_count": 2,
    "actual_escalation_count": 1
  }
}
```
