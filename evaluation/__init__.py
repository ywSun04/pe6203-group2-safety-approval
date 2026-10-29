"""Offline evaluation of Approval Gate logs. No AgentDojo or model dependency."""

from .logs import EvaluationError, evaluate, write_outputs

__all__ = ["EvaluationError", "evaluate", "write_outputs"]
