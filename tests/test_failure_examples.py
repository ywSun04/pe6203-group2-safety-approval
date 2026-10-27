"""Executable local failure evidence; this is not benchmark scoring."""
from examples.policy_failure_cases import run_case


def test_over_conservative_example_is_a_real_blocked_safe_send():
    value=run_case("over_conservative")
    assert value["failure_observed"]
    assert [r["policy_decision"] for r in value["calls"]]==["APPROVE","ESCALATE"]
    assert [r["final_decision"] for r in value["calls"]]==["APPROVE","DENY"]
    assert value["gate_summary"]["actual_escalation_count"]==0
    assert value["gate_summary"]["task_completed"] is None


def test_over_permissive_example_exposes_a_read_scope_limit():
    value=run_case("over_permissive")
    assert value["failure_observed"]
    assert [r["final_decision"] for r in value["calls"]]==["APPROVE","APPROVE"]
    assert value["calls"][-1]["execution_attempted"] is True
    assert value["gate_summary"]["security_passed"] is None
