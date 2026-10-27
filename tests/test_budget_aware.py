"""Tests for Member 6's conservative budget-aware policy."""

from approval_gate.policies.budget_aware import BudgetAwarePolicy


def make_request(tool_name, budget, user_task="Help me with my task",
                 tool_arguments=None):
    return {
        "user_task": user_task,
        "tool_name": tool_name,
        "tool_arguments": tool_arguments if tool_arguments is not None else {},
        "remaining_budget": budget,
    }


def test_policy_interface():
    policy = BudgetAwarePolicy()
    result = policy.decide(make_request("list_files", 3))

    assert set(result) == {"decision", "reason"}
    assert result["decision"] in {"APPROVE", "DENY", "ESCALATE"}
    assert isinstance(result["reason"], str)


def test_safe_read_with_budget():
    policy = BudgetAwarePolicy()
    result = policy.decide(make_request("list_files", 3))

    assert result["decision"] == "APPROVE"


def test_safe_read_without_budget():
    policy = BudgetAwarePolicy()
    result = policy.decide(make_request("list_files", 0))

    assert result["decision"] == "APPROVE"


def test_sensitive_read_without_budget():
    policy = BudgetAwarePolicy()
    result = policy.decide(make_request("get_balance", 0))

    assert result["decision"] == "DENY"


def test_sensitive_read_with_budget():
    policy = BudgetAwarePolicy()
    result = policy.decide(make_request("get_balance", 3))

    assert result["decision"] in {"ESCALATE", "DENY"}
    assert result["decision"] != "APPROVE"


def test_financial_action_without_budget():
    policy = BudgetAwarePolicy()
    result = policy.decide(
        make_request("send_money", 0, tool_arguments={"amount": 100})
    )

    assert result["decision"] == "DENY"


def test_unknown_tool_without_budget():
    policy = BudgetAwarePolicy()
    result = policy.decide(make_request("unknown_tool", 0))

    assert result["decision"] == "DENY"


def test_explicit_user_prohibition():
    policy = BudgetAwarePolicy()
    result = policy.decide(
        make_request(
            "send_email",
            5,
            user_task="Do not send emails.",
            tool_arguments={
                "recipients": ["test@example.com"],
                "subject": "Hello",
                "body": "Test",
            },
        )
    )

    assert result["decision"] == "DENY"


def test_budget_not_modified():
    policy = BudgetAwarePolicy()
    request = make_request("get_balance", 2)

    policy.decide(request)

    assert request["remaining_budget"] == 2


def test_deterministic_decision():
    policy = BudgetAwarePolicy()
    request = make_request("get_balance", 2)

    first = policy.decide(request)
    second = policy.decide(request)

    assert first == second
