"""Policy components plugged into ApprovalGatedToolsExecutor.

Shared gate and budget logic stay in the executor. BudgetAwarePolicy reuses
assess_request() from basic_risk.py, so both modules must be imported together.
"""

from approval_gate.policies.basic_risk import BasicRiskPolicy, RiskAssessment, assess_request
from approval_gate.policies.budget_aware import BudgetAwarePolicy

__all__ = [
    "BasicRiskPolicy",
    "BudgetAwarePolicy",
    "RiskAssessment",
    "assess_request",
    "make_policy",
]

_POLICIES = {
    "basic_risk": BasicRiskPolicy,
    "basic_risk_v2": BasicRiskPolicy,
    "budget_aware": BudgetAwarePolicy,
    "budget_aware_v1": BudgetAwarePolicy,
}


def make_policy(name: str):
    """Return a fresh policy instance for the approval gate.

    Use "budget_aware" to run Member 6's policy on top of Member 3's assess_request().
    """
    key = name.strip().lower().replace("-", "_")
    factory = _POLICIES.get(key)
    if factory is None:
        known = ", ".join(sorted(_POLICIES))
        raise ValueError(f"Unknown policy {name!r}. Known policies: {known}")
    return factory()
