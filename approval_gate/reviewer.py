"""Fake reviewer plus the wrapper that turns reviewer failures into a denial."""

from __future__ import annotations

import threading
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


DEFAULT_REVIEWER_TIMEOUT_SECONDS = 30.0


def invoke_reviewer(
    reviewer: Any,
    request: dict,
    timeout_seconds: float = DEFAULT_REVIEWER_TIMEOUT_SECONDS,
) -> ReviewerCall:
    """Call the reviewer and stop waiting after timeout_seconds.

    token_usage is the latest attempt, including a failed one.
    retry_tokens counts earlier technical retries only. The gate adds both into
    tokens.reviewer, and also stores retry_tokens on its own so the retry portion
    can be reported without adding it a second time.
    """
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be > 0")
    box: dict[str, ReviewerCall] = {}

    def run() -> None:
        box["result"] = _invoke_reviewer_once(reviewer, request)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(timeout_seconds)
    if thread.is_alive():
        return ReviewerCall(
            None,
            "Reviewer timed out",
            take_token_usage(reviewer),
            0,
            0,
            "Reviewer timed out",
        )
    return box["result"]


def _invoke_reviewer_once(reviewer: Any, request: dict) -> ReviewerCall:
    try:
        payload = call_component(reviewer, request, "review")
        decision, reason = parse_reviewer_output(payload)
    except ReviewerTimeout as error:
        return _failed_review(reviewer, error, error.retry_count, error.retry_tokens)
    except ReviewerFormatError as error:
        return _failed_review(reviewer, error, error.retry_count, error.retry_tokens)
    except Exception as error:
        return _failed_review(reviewer, error, 0, 0)
    return ReviewerCall(decision, reason, take_token_usage(reviewer), 0, 0, None)


def _failed_review(reviewer: Any, error: Exception, retry_count: int, retry_tokens: int) -> ReviewerCall:
    message = str(error) or type(error).__name__
    return ReviewerCall(None, message, take_token_usage(reviewer), retry_count, retry_tokens, message)
