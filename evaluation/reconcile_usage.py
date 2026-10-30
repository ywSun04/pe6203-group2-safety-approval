"""Reconcile one saved run without reading files, changing records or calling APIs.

Task totals are the token ledger. HTTP usage validates them; it is not added to
them. A returned zero and a verified zero are kept separate. The caller decides
whether this UUID is a primary, retry, supplemental or smoke observation and
must count each UUID only once when aggregating expenditure.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence


COMPONENTS = ("agent", "policy", "reviewer")
DETERMINISTIC_POLICIES = {
    "full-approve", "full_approve", "full-escalate", "full_escalate",
    "basic_risk", "basic_risk_v2", "budget_aware", "budget_aware_v1",
}


def _count(value: Any) -> bool:
    return type(value) is int and value >= 0


def _money(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and result >= 0 else None
    except InvalidOperation:
        return None


def reconcile_run_usage(
    manifest: Mapping[str, Any],
    call_rows: Sequence[Mapping[str, Any]],
    task_rows: Sequence[Mapping[str, Any]],
    usage_rows: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return recorded amounts, completeness, intervention counts and issues.

    Arguments are decoded original records. Missing files can be represented by
    empty row lists. ``issues`` means inconsistent/invalid evidence; ``warnings``
    identifies missing evidence that remains unknown. Neither list replaces the
    original records. ``tokens_complete`` uses None when usage cannot be fully
    verified; ``tokens_recorded`` still preserves known task amounts. Provider
    costs are decimal strings and diagnostic fields, never an invoice estimate.
    """
    summary = summary or {}
    settings = manifest.get("settings", {})
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    run_id = manifest.get("run_id")

    def issue(code: str, message: str) -> None:
        issues.append({"code": code, "message": message})

    def warn(code: str, message: str) -> None:
        warnings.append({"code": code, "message": message})

    if not isinstance(run_id, str) or not run_id:
        issue("missing_run_id", "Manifest has no valid run_id.")
    for name, rows in (("call", call_rows), ("task", task_rows), ("usage", usage_rows)):
        for index, row in enumerate(rows, 1):
            if row.get("run_id") != run_id:
                issue("run_id_mismatch", f"{name} row {index} does not match manifest run_id.")
    if summary and summary.get("run_id") != run_id:
        issue("run_id_mismatch", "Summary does not match manifest run_id.")

    unique_tasks: list[Mapping[str, Any]] = []
    for row in task_rows:
        if row not in unique_tasks:
            unique_tasks.append(row)
        else:
            warn("identical_task_row", "An identical task row was counted once.")
    if len(unique_tasks) > 1:
        issue("multiple_task_rows", "A run has conflicting or multiple task rows.")
    task = unique_tasks[0] if len(unique_tasks) == 1 else {}
    if not task:
        warn("missing_task_total", "No unambiguous task-total row is available.")
    task_id = manifest.get("task_id")
    if task and task.get("task_id") != task_id:
        issue("task_id_mismatch", "Task row does not match manifest task_id.")
    if summary.get("task_id", task_id) != task_id:
        issue("task_id_mismatch", "Summary does not match manifest task_id.")

    calls: list[Mapping[str, Any]] = []
    late: list[Mapping[str, Any]] = []
    seen_calls: dict[tuple[str, str], Mapping[str, Any]] = {}
    for index, row in enumerate(call_rows, 1):
        kind = row.get("record_type")
        if kind not in {"tool_call", "late_reviewer_usage"}:
            issue("unknown_call_record", f"Call row {index} has an unsupported record_type.")
            continue
        call_id = row.get("call_id")
        if not isinstance(call_id, str) or not call_id:
            issue("missing_call_id", f"Call row {index} has no valid call_id.")
            call_id = f"missing-{index}"
        key = (kind, call_id)
        if key in seen_calls:
            if row == seen_calls[key]:
                warn("identical_call_row", f"Identical {kind} row {call_id} was counted once.")
            else:
                issue("conflicting_call_row", f"Conflicting {kind} rows for {call_id}.")
            continue
        seen_calls[key] = row
        (calls if kind == "tool_call" else late).append(row)

    actual = sum(row.get("actually_escalated") is True for row in calls)
    requested = sum(row.get("requested_escalation") is True for row in calls)
    budget_denied = sum(
        row.get("requested_escalation") is True
        and row.get("actually_escalated") is False
        and row.get("budget_before") == 0
        for row in calls
    )
    budget = settings.get("k", task.get("k"))
    if not _count(budget):
        issue("invalid_budget", "Initial budget is not a nonnegative integer.")
        budget = None
    if task and task.get("k") != settings.get("k", task.get("k")):
        issue("budget_mismatch", "Task and manifest budget differ.")
    for row in calls:
        call_id = row.get("call_id", "unknown")
        if type(row.get("actually_escalated")) is not bool or type(row.get("requested_escalation")) is not bool:
            issue("invalid_review_flag", f"Call {call_id} needs boolean review flags.")
        if row.get("actually_escalated") is True and row.get("requested_escalation") is not True:
            issue("review_without_request", f"Call {call_id} starts a review without a request.")
        if budget is not None:
            if row.get("budget_before") != budget:
                issue("budget_discontinuity", f"Call {call_id} does not start at the prior remaining budget.")
            budget -= int(row.get("actually_escalated") is True)
            if budget < 0 or row.get("budget_after") != budget:
                issue("budget_charge_mismatch", f"Call {call_id} does not charge exactly one per started review.")
    for field, observed in (("actual_escalation_count", actual), ("requested_escalation_count", requested)):
        if task and task.get(field) != observed:
            issue("review_total_mismatch", f"Task {field} differs from the call records.")

    retry_count = sum(row.get("reviewer_retry_count", 0) for row in calls if _count(row.get("reviewer_retry_count", 0)))
    retry_tokens = sum(row.get("reviewer_retry_tokens", 0) for row in calls if _count(row.get("reviewer_retry_tokens", 0)))
    for row in calls:
        if not _count(row.get("reviewer_retry_count", 0)) or not _count(row.get("reviewer_retry_tokens", 0)):
            issue("invalid_retry_count", "A call has invalid retry counts or tokens.")
    for field, observed in (("reviewer_retry_count", retry_count), ("reviewer_retry_tokens", retry_tokens)):
        if task and task.get(field) != observed:
            issue("retry_total_mismatch", f"Task {field} differs from the call records.")

    included = excluded = 0
    invalid_late = 0
    for row in late:
        if ("tool_call", row.get("call_id")) not in seen_calls:
            issue("orphan_late_usage", "A late-usage row has no originating tool call.")
        amount = row.get("late_reviewer_tokens")
        flag = row.get("included_in_task_total")
        if not _count(amount) or type(flag) is not bool:
            invalid_late += 1
            issue("invalid_late_usage", "Late usage needs known nonnegative tokens and an inclusion flag.")
        elif flag:
            included += amount
        else:
            excluded += amount
    task_tokens = task.get("tokens") if isinstance(task.get("tokens"), Mapping) else {}
    recorded: dict[str, int | None] = {}
    for component in COMPONENTS:
        amount = task_tokens.get(component)
        recorded[component] = amount if _count(amount) else None
        if amount is not None and not _count(amount):
            issue("invalid_task_tokens", f"Task {component} tokens are invalid.")
    task_recorded = dict(recorded)
    if recorded["reviewer"] is not None:
        recorded["reviewer"] = None if invalid_late else recorded["reviewer"] + excluded
    if task_recorded["reviewer"] is not None and retry_tokens > task_recorded["reviewer"]:
        issue("retry_subset_mismatch", "Retry tokens exceed the Reviewer task total that should already include them.")

    attempts: dict[tuple[str, int], Mapping[str, Any]] = {}
    responses: dict[tuple[str, int], Mapping[str, Any]] = {}
    tainted_components: set[str] = set()
    for index, row in enumerate(usage_rows, 1):
        component, number = row.get("component"), row.get("attempt")
        if component not in COMPONENTS or not _count(number):
            issue("invalid_usage_key", f"Usage row {index} has an invalid component or attempt number.")
            if component in COMPONENTS:
                tainted_components.add(component)
            continue
        kind = row.get("record_type")
        if kind not in {"api_attempt", "api_response"}:
            issue("unknown_usage_record", f"Usage row {index} has an unsupported record_type.")
            tainted_components.add(component)
            continue
        target = attempts if kind == "api_attempt" else responses
        key = (component, number)
        if key in target:
            if row == target[key]:
                warn("identical_usage_row", f"An identical {component} {kind} row was counted once.")
            else:
                issue("conflicting_usage_row", f"Conflicting {component} {kind} records for attempt {number}.")
                tainted_components.add(component)
            continue
        target[key] = row

    policy = task.get("policy_name", settings.get("policy"))
    component_usage: dict[str, dict[str, Any]] = {}
    complete_tokens: dict[str, int | None] = {}
    all_keys = attempts.keys() | responses.keys()
    cost_total = Decimal(0)
    for component in COMPONENTS:
        keys = {key for key in all_keys if key[0] == component}
        known_tokens = 0
        unknown = known = cost_known = cost_unknown = 0
        cost = Decimal(0)
        response_without_attempt = 0
        non_200 = 0
        for key in sorted(keys):
            response = responses.get(key)
            if key not in attempts:
                response_without_attempt += 1
                issue("response_without_attempt", f"{component} response {key[1]} has no attempt row.")
            valid_usage = response is not None and response.get("usage_known") is True and _count(response.get("total_tokens"))
            if valid_usage:
                known += 1
                known_tokens += response["total_tokens"]
                prompt, completion = response.get("prompt_tokens"), response.get("completion_tokens")
                if _count(prompt) and _count(completion) and prompt + completion != response["total_tokens"]:
                    issue("usage_token_breakdown_mismatch", f"{component} attempt {key[1]} prompt/completion do not equal total.")
                    tainted_components.add(component)
            else:
                unknown += 1
            amount = _money(response.get("provider_cost")) if response is not None else None
            if amount is None:
                cost_unknown += 1
            else:
                cost += amount
                cost_known += 1
            if response is not None and response.get("status") != 200:
                non_200 += 1
        no_model_expected = (
            component == "policy" and policy in DETERMINISTIC_POLICIES and recorded[component] == 0
            or component == "reviewer" and task and actual == 0 and recorded[component] == 0
        )
        absence_verified = not keys and bool(no_model_expected)
        ledger_complete = bool(keys) and not unknown and not response_without_attempt and component not in tainted_components
        amount = recorded[component]
        usage_complete = amount is not None and (absence_verified or ledger_complete)
        if ledger_complete and amount is not None and known_tokens != amount:
            issue("token_ledger_mismatch", f"{component} task/late total {amount} differs from HTTP usage {known_tokens}.")
            usage_complete = False
        if component == "reviewer" and invalid_late:
            usage_complete = False
        if not usage_complete:
            warn("usage_unresolved", f"{component} usage is not fully verified; recorded zero is not proof of zero cost.")
        cost_complete = bool(absence_verified or keys and not cost_unknown and not response_without_attempt and component not in tainted_components)
        cost_total += cost
        component_usage[component] = {
            "attempt_rows": sum(key[0] == component for key in attempts),
            "response_rows": sum(key[0] == component for key in responses),
            "request_keys": len(keys), "known_usage_requests": known,
            "unknown_usage_requests": unknown, "responses_without_attempt": response_without_attempt,
            "non_200_responses": non_200, "ledger_known_tokens": known_tokens,
            "has_ledger": bool(keys), "verified_no_model_invocation": absence_verified,
            "usage_complete": usage_complete, "provider_cost_recorded": str(cost),
            "provider_cost_known_requests": cost_known, "provider_cost_unknown_requests": cost_unknown,
            "provider_cost_complete": cost_complete,
        }
        complete_tokens[component] = amount if usage_complete else None

    return {
        "run_id": run_id, "task_id": task_id, "policy_name": policy,
        "k": settings.get("k", task.get("k")), "condition": settings.get("attack"),
        "raw_repetition": manifest.get("repetition"), "status": summary.get("status"),
        "error_type": summary.get("error_type"), "task_completed": task.get("task_completed"),
        "tool_call_count": len(calls), "actual_reviews": actual,
        "requested_reviews": requested, "budget_exhausted_requests": budget_denied,
        "hitl_utility_completed": actual if task.get("task_completed") is True else 0,
        "reviewer_retry_count": retry_count, "reviewer_retry_tokens": retry_tokens,
        "late_usage_rows": len(late), "late_included_tokens": included,
        "late_excluded_tokens": excluded, "late_unknown_inclusion_rows": invalid_late,
        "task_tokens_recorded": task_recorded, "tokens_recorded": recorded,
        "tokens_complete": complete_tokens, "component_usage": component_usage,
        "api_attempts": len(attempts), "api_responses": len(responses),
        "unknown_usage_requests": sum(row["unknown_usage_requests"] for row in component_usage.values()),
        "provider_cost_recorded": str(cost_total),
        "provider_cost_complete": all(row["provider_cost_complete"] for row in component_usage.values()),
        "accounting_consistent": not issues,
        "usage_fully_verified": not issues and all(value is not None for value in complete_tokens.values()),
        "issues": issues, "warnings": warnings,
    }
