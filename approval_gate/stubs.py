"""Constant baselines. The gate, not these functions, enforces the budget."""

from __future__ import annotations


class FullApprove:
    name = "full_approve"
    last_token_usage = 0

    def decide(self, request: dict) -> dict:
        return {"decision": "APPROVE", "reason": "Full-approve baseline"}


class FullEscalate:
    name = "full_escalate"
    last_token_usage = 0

    def decide(self, request: dict) -> dict:
        return {"decision": "ESCALATE", "reason": "Full-escalate baseline"}
