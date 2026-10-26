"""Conservative budget-aware policy composed with Member 3's fixed risk assessment.

This policy never upgrades a baseline DENY or ESCALATE to APPROVE.
The shared Gate, not this component, owns and decrements the review budget.
"""

from approval_gate.policies.basic_risk import assess_request


class BudgetAwarePolicy:
    name = "budget_aware_v1"
    last_token_usage = 0

    # A pre-registered heuristic, NOT an empirical risk ranking.
    # Preserve the last review for categories where human review may be especially
    # consequential. Unknown tools are conservatively denied when budget is scarce.
    LAST_REVIEW_CATEGORIES = frozenset({
        "R3_SENSITIVE_READ",
        "R4_EXTERNAL_ACTION",
        "R5_FINANCIAL_ACTION",
    })

    def decide(self, request: dict) -> dict[str, str]:
        risk = assess_request(request)
        if risk.decision != "ESCALATE":
            return risk.payload()

        # assess_request validates remaining_budget before returning ESCALATE.
        remaining = request["remaining_budget"]
        if remaining == 0:
            return {
                "decision": "DENY",
                "reason": f"B0_NO_REVIEW_BUDGET: {risk.rule_id}; review unavailable; deny safely.",
            }
        if remaining == 1 and risk.rule_id not in self.LAST_REVIEW_CATEGORIES:
            return {
                "decision": "DENY",
                "reason": f"B1_RESERVE_LAST_REVIEW: {risk.rule_id}; conservatively deny without review.",
            }
        return {
            "decision": "ESCALATE",
            "reason": f"B2_REVIEW_REQUESTED: {risk.rule_id}; request gate-managed review.",
        }
