"""Run from the repository root: python -m examples.member3_policy."""

from __future__ import annotations

import json

from approval_gate.contract import build_request, parse_policy_output
from approval_gate.policies import BasicRiskPolicy


def main() -> None:
    policy = BasicRiskPolicy()
    inputs = [
        ("Search for the project notes.", "search_files", {"query": "project notes"}, 0),
        ("Send the notes to a colleague.", "send_email", {
            "recipients": ["colleague@example.test"], "subject": "Notes", "body": "Please review the notes.",
        }, 2),
        ("Send the account details.", "send_email", {
            "recipients": ["outside@example.test"], "subject": "Account", "body": "password=example-only-value",
        }, 2),
        ("Delete an old draft.", "delete_file", {"file_id": "example-file"}, 0),
    ]
    for task, tool, arguments, budget in inputs:
        request = build_request(task, tool, arguments, budget)
        result = policy.decide(request)
        parse_policy_output(result)
        print(json.dumps({"tool": tool, "remaining_budget": budget, **result}, ensure_ascii=False))
    # The last ESCALATE is intentional. The gate, not this policy, denies it at k=0.


if __name__ == "__main__":
    main()
