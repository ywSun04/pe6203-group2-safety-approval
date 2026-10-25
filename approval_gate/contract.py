"""Approval request and decision shapes shared by every policy and the reviewer."""

from __future__ import annotations

from typing import Any

REQUIRED_FIELDS = ("user_task", "tool_name", "tool_arguments", "remaining_budget")
OPTIONAL_FIELDS = ("history", "tool_metadata")
POLICY_DECISIONS = ("APPROVE", "DENY", "ESCALATE")
REVIEWER_DECISIONS = ("APPROVE", "DENY")

# Never copy these from the benchmark into a request, even if a caller has them.
FORBIDDEN_FIELDS = ("task", "ground_truth", "attack", "attack_annotation", "oracle")


class PolicyFormatError(ValueError):
    """A policy returned something other than decision + reason."""


class ReviewerFormatError(ValueError):
    """A reviewer returned something other than APPROVE or DENY."""

    def __init__(self, message: str, retry_count: int = 0, retry_tokens: int = 0) -> None:
        super().__init__(message)
        self.retry_count = retry_count
        self.retry_tokens = retry_tokens


class ReviewerTimeout(TimeoutError):
    """The reviewer did not return a usable decision in time."""

    def __init__(self, message: str = "Reviewer timed out", retry_count: int = 0, retry_tokens: int = 0) -> None:
        super().__init__(message)
        self.retry_count = retry_count
        self.retry_tokens = retry_tokens


def without_forbidden(value: Any) -> Any:
    """Serialize a value and drop benchmark secrets at every level."""
    return _strip_forbidden(to_jsonable(value))


def _strip_forbidden(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_forbidden(item)
            for key, item in value.items()
            if key not in FORBIDDEN_FIELDS
        }
    if isinstance(value, list):
        return [_strip_forbidden(item) for item in value]
    return value


def to_jsonable(value: Any) -> Any:
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def build_request(
    user_task: str,
    tool_name: str,
    tool_arguments: dict,
    remaining_budget: int,
    history: list | None = None,
    tool_metadata: dict | None = None,
) -> dict:
    """Build the only dict a policy or reviewer is allowed to see."""
    request = {
        "user_task": user_task,
        "tool_name": tool_name,
        "tool_arguments": without_forbidden(tool_arguments),
        "remaining_budget": int(remaining_budget),
    }
    if history is not None:
        request["history"] = without_forbidden(history)
    if tool_metadata is not None:
        request["tool_metadata"] = without_forbidden(tool_metadata)
    return request


def parse_policy_output(payload: Any) -> tuple[str, str]:
    decision, reason = _parse_output(payload, POLICY_DECISIONS)
    return decision, reason


def parse_reviewer_output(payload: Any) -> tuple[str, str]:
    try:
        return _parse_output(payload, REVIEWER_DECISIONS)
    except PolicyFormatError as error:
        raise ReviewerFormatError(str(error)) from error


def _parse_output(payload: Any, allowed: tuple[str, ...]) -> tuple[str, str]:
    if not isinstance(payload, dict) or set(payload) != {"decision", "reason"}:
        raise PolicyFormatError("Decision payload must contain exactly decision and reason")
    decision = payload["decision"]
    reason = payload["reason"]
    if decision not in allowed or not isinstance(reason, str):
        allowed_text = ", ".join(allowed)
        raise PolicyFormatError(f"decision must be one of {allowed_text}, and reason must be a string")
    return decision, reason


def call_component(component: Any, request: dict, method_name: str) -> Any:
    method = getattr(component, method_name, None)
    if callable(method):
        return method(request)
    if callable(component):
        return component(request)
    raise TypeError(f"{component!r} is not callable and has no {method_name}()")


def component_name(component: Any, fallback: str) -> str:
    return str(getattr(component, "name", getattr(component, "__name__", fallback)))


def take_token_usage(component: Any) -> int:
    usage = getattr(component, "last_token_usage", 0) or 0
    return int(usage)
