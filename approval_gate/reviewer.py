"""Fake reviewer plus the wrapper that turns reviewer failures into a denial."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from approval_gate.contract import (
    ReviewerFormatError,
    ReviewerTimeout,
    call_component,
    parse_reviewer_output,
    take_token_usage,
)


class FakeReviewer:
    """Stand-in until Member 4's reviewer arrives.

    mode is APPROVE, DENY, timeout, bad_format, or a list of those values consumed in order.
    """

    name = "fake_reviewer"
    last_token_usage = 0

    def __init__(self, mode: str | list[str] = "APPROVE") -> None:
        self._queue = list(mode) if isinstance(mode, list) else [mode]

    def review(self, request: dict) -> dict:
        mode = self._queue.pop(0) if len(self._queue) > 1 else self._queue[0]
        if mode == "timeout":
            raise ReviewerTimeout("Reviewer timed out", retry_count=1, retry_tokens=0)
        if mode == "bad_format":
            return {"decision": "ESCALATE", "reason": "Reviewer is not allowed to escalate"}
        if mode == "DENY":
            return {"decision": "DENY", "reason": "Fake reviewer denied"}
        if mode == "APPROVE":
            return {"decision": "APPROVE", "reason": "Fake reviewer approved"}
        raise ReviewerFormatError(f"Unknown fake reviewer mode: {mode}")


@dataclass
class ReviewerCall:
    decision: str | None
    reason: str
    token_usage: int
    retry_count: int
    retry_tokens: int
    error: str | None


def invoke_reviewer(reviewer: Any, request: dict) -> ReviewerCall:
    """Call the reviewer. On timeout or a bad payload, return an error instead of raising."""
    try:
        payload = call_component(reviewer, request, "review")
        decision, reason = parse_reviewer_output(payload)
    except ReviewerTimeout as error:
        return ReviewerCall(None, str(error), 0, error.retry_count, error.retry_tokens, str(error))
    except ReviewerFormatError as error:
        return ReviewerCall(None, str(error), 0, error.retry_count, error.retry_tokens, str(error))
    except Exception as error:
        return ReviewerCall(None, f"{type(error).__name__}: {error}", 0, 0, 0, f"{type(error).__name__}: {error}")
    return ReviewerCall(decision, reason, take_token_usage(reviewer), 0, 0, None)
