"""Fake reviewer plus the wrapper that turns reviewer failures into a denial."""

from __future__ import annotations

import inspect
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from approval_gate.contract import (
    ReviewerFormatError,
    ReviewerTimeout,
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
    on_late_usage: Callable[[int], None] | None = None,
) -> ReviewerCall:
    """Call the reviewer and stop waiting after timeout_seconds.

    The returned usage is a snapshot taken when the attempt finishes. A timed-out
    call does not read the reviewer's shared counter. If that call later finishes,
    on_late_usage receives the final token count once.

    token_usage is the latest attempt, including a failed one. retry_tokens counts
    earlier technical retries only. The gate adds both into tokens.reviewer.
    A real reviewer must pass this same timeout to its model client.
    """
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be > 0")
    box: dict[str, Any] = {}
    state = {"closed": False}
    lock = threading.Lock()

    def run() -> None:
        try:
            result = _invoke_reviewer_once(reviewer, request, timeout_seconds)
        except Exception as error:
            result = ReviewerCall(None, f"{type(error).__name__}: {error}", 0, 0, 0, f"{type(error).__name__}: {error}")
        with lock:
            if state["closed"]:
                box["late"] = result.token_usage + result.retry_tokens
            else:
                box["result"] = result

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(timeout_seconds)
    with lock:
        if "result" in box:
            return box["result"]
        state["closed"] = True

    def watch() -> None:
        thread.join()
        with lock:
            late = int(box.get("late", 0))
        if late and on_late_usage is not None:
            on_late_usage(late)

    threading.Thread(target=watch, daemon=True).start()
    return ReviewerCall(None, "Reviewer timed out", 0, 0, 0, "Reviewer timed out")


def _invoke_reviewer_once(reviewer: Any, request: dict, timeout_seconds: float) -> ReviewerCall:
    with _reviewer_lock(reviewer):
        try:
            payload = _call_review(reviewer, request, timeout_seconds)
            decision, reason = parse_reviewer_output(payload)
        except ReviewerTimeout as error:
            return _failed_review(reviewer, error, error.retry_count, error.retry_tokens)
        except ReviewerFormatError as error:
            return _failed_review(reviewer, error, error.retry_count, error.retry_tokens)
        except Exception as error:
            return _failed_review(reviewer, error, 0, 0)
        return ReviewerCall(decision, reason, take_token_usage(reviewer), 0, 0, None)


def _call_review(reviewer: Any, request: dict, timeout_seconds: float) -> Any:
    method = getattr(reviewer, "review", None)
    if not callable(method):
        if not callable(reviewer):
            raise TypeError(f"{reviewer!r} is not callable and has no review()")
        method = reviewer
    kwargs = {}
    try:
        parameters = inspect.signature(method).parameters
    except (TypeError, ValueError):
        parameters = {}
    if "timeout_seconds" in parameters:
        kwargs["timeout_seconds"] = timeout_seconds
    return method(request, **kwargs)


_REVIEWER_LOCKS: dict[int, threading.Lock] = {}
_REVIEWER_LOCKS_GUARD = threading.Lock()


def _reviewer_lock(reviewer: Any) -> threading.Lock:
    with _REVIEWER_LOCKS_GUARD:
        lock = _REVIEWER_LOCKS.get(id(reviewer))
        if lock is None:
            lock = threading.Lock()
            _REVIEWER_LOCKS[id(reviewer)] = lock
        return lock


def _failed_review(reviewer: Any, error: Exception, retry_count: int, retry_tokens: int) -> ReviewerCall:
    message = str(error) or type(error).__name__
    return ReviewerCall(None, message, take_token_usage(reviewer), retry_count, retry_tokens, message)
