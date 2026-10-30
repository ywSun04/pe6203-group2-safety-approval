"""Saved-data reconciliation must not turn missing billing evidence into zero."""
from copy import deepcopy
import json

from evaluation.reconcile_usage import reconcile_run_usage


def sample(agent=10, reviewer=0, k=0, completed=True):
    manifest = {"run_id": "r1", "task_id": "user_task_0", "repetition": 0,
                "settings": {"policy": "full-approve", "k": k, "attack": "none"}}
    task = {"run_id": "r1", "task_id": "user_task_0", "policy_name": "full_approve",
            "k": k, "task_completed": completed, "actual_escalation_count": 0,
            "requested_escalation_count": 0, "reviewer_retry_count": 0,
            "reviewer_retry_tokens": 0,
            "tokens": {"agent": agent, "policy": 0, "reviewer": reviewer}}
    summary = {"run_id": "r1", "task_id": "user_task_0", "status": "completed", "error_type": None}
    return manifest, [], [task], [], summary


def http(component, number, amount, cost="0.001"):
    return [
        {"record_type": "api_attempt", "run_id": "r1", "component": component, "attempt": number},
        {"record_type": "api_response", "run_id": "r1", "component": component,
         "attempt": number, "status": 200, "usage_known": True,
         "total_tokens": amount, "provider_cost": cost},
    ]


def call(number, before, actual=True, requested=True, retry_count=0, retry_tokens=0):
    return {"record_type": "tool_call", "run_id": "r1", "call_id": f"r1-{number}",
            "requested_escalation": requested, "actually_escalated": actual,
            "budget_before": before, "budget_after": before - int(actual),
            "reviewer_retry_count": retry_count, "reviewer_retry_tokens": retry_tokens}


def test_retry_subset_and_late_inclusion_do_not_double_count_failed_task_cost():
    args = sample(reviewer=13, k=3, completed=False)
    manifest, calls, tasks, usage, summary = args
    manifest["settings"]["policy"] = "full-escalate"
    tasks[0].update(policy_name="full_escalate", actual_escalation_count=3,
                    requested_escalation_count=4, reviewer_retry_count=1, reviewer_retry_tokens=3)
    calls.extend([call(1, 3, retry_count=1, retry_tokens=3), call(2, 2), call(3, 1),
                  call(4, 0, actual=False)])
    calls.extend([
        {"record_type": "late_reviewer_usage", "run_id": "r1", "call_id": "r1-2",
         "late_reviewer_tokens": 5, "included_in_task_total": True},
        {"record_type": "late_reviewer_usage", "run_id": "r1", "call_id": "r1-3",
         "late_reviewer_tokens": 7, "included_in_task_total": False},
    ])
    usage.extend(http("agent", 1, 10))
    for number, amount in enumerate([3, 5, 5, 7], 1):
        usage.extend(http("reviewer", number, amount))
    before = deepcopy(args)
    result = reconcile_run_usage(*args)
    assert result["issues"] == []
    assert result["tokens_recorded"] == {"agent": 10, "policy": 0, "reviewer": 20}
    assert result["tokens_complete"] == result["tokens_recorded"]
    assert result["reviewer_retry_tokens"] == 3
    assert result["late_included_tokens"] == 5
    assert result["late_excluded_tokens"] == 7
    assert result["actual_reviews"] == 3
    assert result["requested_reviews"] == 4
    assert result["budget_exhausted_requests"] == 1
    assert result["hitl_utility_completed"] == 0
    assert result["provider_cost_recorded"] == "0.005"
    assert result["provider_cost_complete"] is True
    assert result["usage_fully_verified"] is True
    assert args == before
    json.dumps(result)


def test_timeout_attempt_with_zero_task_counter_is_unknown_not_free():
    args = sample(agent=0, completed=None)
    args[3].append(http("agent", 1, 0)[0])
    args[4].update(status="error", error_type="APITimeoutError")
    result = reconcile_run_usage(*args)
    assert result["issues"] == []
    assert result["tokens_recorded"]["agent"] == 0
    assert result["tokens_complete"]["agent"] is None
    assert result["api_attempts"] == 1
    assert result["api_responses"] == 0
    assert result["unknown_usage_requests"] == 1
    assert result["provider_cost_recorded"] == "0"
    assert result["provider_cost_complete"] is False
    assert result["component_usage"]["policy"]["verified_no_model_invocation"] is True
    assert result["tokens_complete"]["reviewer"] == 0


def test_known_usage_and_missing_retry_response_keep_partial_lower_bound():
    args = sample(agent=25, completed=False)
    args[3].extend(http("agent", 1, 10))
    args[3].append(http("agent", 2, 15)[0])
    result = reconcile_run_usage(*args)
    assert result["issues"] == []
    assert result["tokens_recorded"]["agent"] == 25
    assert result["tokens_complete"]["agent"] is None
    assert result["component_usage"]["agent"]["ledger_known_tokens"] == 10
    assert result["unknown_usage_requests"] == 1
    assert result["provider_cost_recorded"] == "0.001"
    assert result["provider_cost_complete"] is False


def test_null_task_amounts_and_no_ledger_remain_unknown():
    args = sample(agent=None, reviewer=None, completed=None)
    args[4].update(status="error", error_type="RuntimeError")
    result = reconcile_run_usage(*args)
    assert result["issues"] == []
    assert result["tokens_recorded"] == {"agent": None, "policy": 0, "reviewer": None}
    assert result["tokens_complete"] == result["tokens_recorded"]
    assert result["component_usage"]["agent"]["has_ledger"] is False
    assert result["provider_cost_complete"] is False
    assert result["usage_fully_verified"] is False


def test_absent_agent_ledger_does_not_verify_an_empty_task():
    result = reconcile_run_usage(*sample(agent=0, completed=False))
    assert result["tokens_complete"]["agent"] is None
    assert result["component_usage"]["agent"]["request_keys"] == 0
    assert result["component_usage"]["agent"]["usage_complete"] is False
    assert result["unknown_usage_requests"] == 0  # no fabricated request count
    assert result["warnings"]


def test_http_usage_is_validation_not_an_additional_token_total():
    args = sample(agent=10)
    args[3].extend(http("agent", 1, 10))
    result = reconcile_run_usage(*args)
    assert result["tokens_recorded"]["agent"] == 10
    assert result["tokens_complete"]["agent"] == 10
    assert result["issues"] == []


def test_conflicting_task_and_ledger_totals_are_not_certified():
    args = sample(agent=11)
    args[3].extend(http("agent", 1, 10))
    result = reconcile_run_usage(*args)
    assert "token_ledger_mismatch" in {item["code"] for item in result["issues"]}
    assert result["tokens_recorded"]["agent"] == 11
    assert result["tokens_complete"]["agent"] is None
    assert result["accounting_consistent"] is False


def test_response_usage_unknown_with_returned_zero_is_not_known_zero():
    args = sample(agent=0)
    args[3].extend(http("agent", 1, 0, cost=None))
    args[3][-1]["usage_known"] = False
    result = reconcile_run_usage(*args)
    assert result["tokens_complete"]["agent"] is None
    assert result["unknown_usage_requests"] == 1
    assert result["provider_cost_complete"] is False


def test_identical_repeated_rows_are_counted_once():
    args = sample(agent=10)
    pair = http("agent", 1, 10)
    args[3].extend(pair + deepcopy(pair))
    args[2].append(deepcopy(args[2][0]))
    result = reconcile_run_usage(*args)
    assert result["api_attempts"] == result["api_responses"] == 1
    assert result["provider_cost_recorded"] == "0.001"
    assert result["tokens_complete"]["agent"] == 10
    assert result["issues"] == []


def test_conflicting_http_copies_cannot_be_certified_complete():
    args = sample(agent=10)
    args[3].extend(http("agent", 1, 10))
    args[3].append({**args[3][-1], "total_tokens": 99})
    result = reconcile_run_usage(*args)
    assert "conflicting_usage_row" in {item["code"] for item in result["issues"]}
    assert result["tokens_complete"]["agent"] is None
    assert result["provider_cost_complete"] is False


def test_response_without_attempt_is_reported_without_double_adding_cost():
    args = sample(agent=10)
    args[3].append(http("agent", 1, 10)[1])
    result = reconcile_run_usage(*args)
    assert result["api_attempts"] == 0 and result["api_responses"] == 1
    assert "response_without_attempt" in {item["code"] for item in result["issues"]}
    assert result["provider_cost_recorded"] == "0.001"
    assert result["provider_cost_complete"] is False


def test_late_unknown_inclusion_cannot_be_added_or_dropped_silently():
    args = sample(reviewer=0, k=1, completed=False)
    args[2][0].update(actual_escalation_count=1, requested_escalation_count=1)
    args[1].append(call(1, 1))
    args[1].append({"record_type": "late_reviewer_usage", "run_id": "r1", "call_id": "r1-1",
                    "late_reviewer_tokens": 5, "included_in_task_total": None})
    args[3].extend(http("agent", 1, 10) + http("reviewer", 1, 5))
    result = reconcile_run_usage(*args)
    assert result["task_tokens_recorded"]["reviewer"] == 0
    assert result["tokens_recorded"]["reviewer"] is None
    assert result["tokens_complete"]["reviewer"] is None
    assert result["late_unknown_inclusion_rows"] == 1
    assert "invalid_late_usage" in {item["code"] for item in result["issues"]}


def test_incorrect_budget_charge_and_review_total_are_visible():
    args = sample(k=1, completed=False)
    args[1].append(call(1, 1))
    args[1][0]["budget_after"] = 1
    result = reconcile_run_usage(*args)
    codes = {item["code"] for item in result["issues"]}
    assert "budget_charge_mismatch" in codes
    assert "review_total_mismatch" in codes


def test_wrong_uuid_and_invalid_token_breakdown_are_visible():
    args = sample(agent=10)
    args[3].extend(http("agent", 1, 10))
    args[3][0]["run_id"] = "other"
    args[3][1].update(prompt_tokens=9, completion_tokens=9)
    result = reconcile_run_usage(*args)
    codes = {item["code"] for item in result["issues"]}
    assert {"run_id_mismatch", "usage_token_breakdown_mismatch"} <= codes
    assert result["tokens_complete"]["agent"] is None


def test_missing_task_row_preserves_known_ledger_as_evidence_without_inventing_totals():
    args = sample()
    args[2].clear()
    args[3].extend(http("agent", 1, 10))
    result = reconcile_run_usage(*args)
    assert result["tokens_recorded"]["agent"] is None
    assert result["component_usage"]["agent"]["ledger_known_tokens"] == 10
    assert result["tokens_complete"]["agent"] is None
    assert "missing_task_total" in {item["code"] for item in result["warnings"]}
