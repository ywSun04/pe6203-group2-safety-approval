"""Approval request and decision shapes shared by every policy and the reviewer."""

from __future__ import annotations

from typing import Any

REQUIRED_FIELDS = ("user_task", "tool_name", "tool_arguments", "remaining_budget")
OPTIONAL_FIELDS = ("history", "tool_metadata")
POLICY_DECISIONS = ("APPROVE", "DENY", "ESCALATE")
REVIEWER_DECISIONS = ("APPROVE", "DENY")

# Benchmark objects that must not be copied into history or tool metadata.
# These names are not stripped from tool arguments. A real tool parameter may use the same name.
PRIVATE_CONTEXT_FIELDS = ("task", "ground_truth", "attack", "attack_annotation", "oracle")
VISIBLE_MESSAGE_FIELDS = ("role", "content", "tool_calls", "tool_call", "tool_call_id", "error")
VISIBLE_METADATA_FIELDS = ("name", "description", "parameters")


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


def project_history(history: list) -> list:
    """Keep chat fields only. Do not attach the benchmark task, labels, or attacks."""
    projected = []
    for message in to_jsonable(history):
        if not isinstance(message, dict):
            continue
        projected.append(
            {
                key: message[key]
                for key in VISIBLE_MESSAGE_FIELDS
                if key in message and key not in PRIVATE_CONTEXT_FIELDS
            }
        )
    return projected


def project_tool_metadata(metadata: dict) -> dict:
    """Keep the tool schema only. Parameter names are left intact."""
    raw = to_jsonable(metadata)
    if not isinstance(raw, dict):
        return {}
    return {key: raw[key] for key in VISIBLE_METADATA_FIELDS if key in raw}


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
    """Build the only dict a policy or reviewer is allowed to see.

    tool_arguments is the full argument dict that will be executed.
    history and tool_metadata are projected to visible chat and schema fields.
    """
    request = {
        "user_task": user_task,
        "tool_name": tool_name,
        "tool_arguments": to_jsonable(tool_arguments),
        "remaining_budget": int(remaining_budget),
    }
    if history is not None:
        request["history"] = project_history(history)
    if tool_metadata is not None:
        request["tool_metadata"] = project_tool_metadata(tool_metadata)
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
