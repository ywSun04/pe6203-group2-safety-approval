"""Approval gate in front of AgentDojo tool execution.

AgentPipeline.from_config still builds a plain ToolsExecutor. Use
approval_gate.pipeline.build_approval_pipeline so this executor is the one
that runs. Call start_task once per task, query on each agent turn, then
finish_task.
"""

from __future__ import annotations

from ast import literal_eval
from dataclasses import dataclass
from typing import Any, Sequence

from agentdojo.agent_pipeline.llms.google_llm import EMPTY_FUNCTION_NAME
from agentdojo.agent_pipeline.tool_execution import ToolsExecutor, is_string_list, tool_result_to_str
from agentdojo.functions_runtime import EmptyEnv, Env, FunctionCall, FunctionsRuntime
from agentdojo.types import ChatMessage, ChatToolResultMessage, text_content_block_from_string

from approval_gate.contract import (
    PolicyFormatError,
    build_request,
    call_component,
    component_name,
    parse_policy_output,
    take_token_usage,
    to_jsonable,
)
from approval_gate.records import GateLogger
from approval_gate.reviewer import DEFAULT_REVIEWER_TIMEOUT_SECONDS, invoke_reviewer


@dataclass
class OpenTask:
    run_id: str
    task_id: str
    k: int
    remaining: int
    next_call_index: int = 1
    actual_escalations: int = 0
    requested_escalations: int = 0
    agent_tokens: int = 0
    policy_tokens: int = 0
    reviewer_tokens: int = 0
    reviewer_retry_tokens: int = 0
    reviewer_retry_count: int = 0


class ApprovalGatedToolsExecutor(ToolsExecutor):
    def __init__(
        self,
        policy: Any,
        reviewer: Any,
        gate_logger: GateLogger,
        k: int,
        tool_output_formatter=tool_result_to_str,
        reviewer_timeout_seconds: float = DEFAULT_REVIEWER_TIMEOUT_SECONDS,
    ) -> None:
        super().__init__(tool_output_formatter)
        if k < 0:
            raise ValueError("k must be >= 0")
        if reviewer_timeout_seconds <= 0:
            raise ValueError("reviewer_timeout_seconds must be > 0")
        self.policy = policy
        self.reviewer = reviewer
        self.gate_logger = gate_logger
        self.k = k
        self.reviewer_timeout_seconds = reviewer_timeout_seconds
        self._task: OpenTask | None = None

    def start_task(self, run_id: str, task_id: str, k: int | None = None) -> None:
        """Reset the budget. This is per task run, not per agent turn."""
        if self._task is not None:
            raise RuntimeError("Finish the open task before starting another one")
        budget = self.k if k is None else k
        if budget < 0:
            raise ValueError("k must be >= 0")
        self._task = OpenTask(run_id=run_id, task_id=task_id, k=budget, remaining=budget)

    def add_agent_tokens(self, count: int) -> None:
        """Record model-call tokens once per request. Do not call this per tool."""
        task = self._require_task()
        task.agent_tokens += int(count)

    def finish_task(self, task_completed: bool | None, security_passed: bool | None) -> dict:
        """Write the task row. Completion and safety come from the benchmark, not this gate."""
        task = self._require_task()
        record = {
            "run_id": task.run_id,
            "task_id": task.task_id,
            "policy_name": component_name(self.policy, "policy"),
            "k": task.k,
            "task_completed": task_completed,
            "security_passed": security_passed,
            "actual_escalation_count": task.actual_escalations,
            "requested_escalation_count": task.requested_escalations,
            "tokens": {
                "agent": task.agent_tokens,
                "policy": task.policy_tokens,
                "reviewer": task.reviewer_tokens,
            },
            "reviewer_retry_count": task.reviewer_retry_count,
            "reviewer_retry_tokens": task.reviewer_retry_tokens,
        }
        self.gate_logger.write_task(record)
        self._task = None
        return record

    def query(
        self,
        query: str,
        runtime: FunctionsRuntime,
        env: Env = EmptyEnv(),
        messages: Sequence[ChatMessage] = [],
        extra_args: dict | None = None,
    ) -> tuple[str, FunctionsRuntime, Env, Sequence[ChatMessage], dict]:
        if extra_args is None:
            extra_args = {}
        self._require_task()
        if len(messages) == 0 or messages[-1]["role"] != "assistant":
            return query, runtime, env, messages, extra_args
        tool_calls = messages[-1]["tool_calls"]
        if tool_calls is None or len(tool_calls) == 0:
            return query, runtime, env, messages, extra_args

        tool_call_results = []
        for tool_call in tool_calls:
            tool_call_results.append(
                self._handle_tool_call(query, runtime, env, messages, tool_call_results, tool_call)
            )
        return query, runtime, env, [*messages, *tool_call_results], extra_args

    def _handle_tool_call(self, query, runtime, env, messages, prior_results, tool_call) -> ChatToolResultMessage:
        task = self._require_task()
        self._coerce_string_lists(tool_call)
        budget_before = task.remaining
        blocked = _pre_approval_block(runtime, tool_call)
        if blocked is not None:
            reason, tool_error = blocked
            outcome = _outcome(
                policy_decision="NOT_EVALUATED",
                policy_reason="",
                final_decision="DENY",
                deny_reason=reason,
                budget_after=budget_before,
            )
            message = _tool_message(tool_call, reason, tool_error or reason)
            self._write_call(task, tool_call, budget_before, outcome, False, tool_error)
            return message
        request = build_request(
            user_task=query,
            tool_name=tool_call.function,
            tool_arguments=dict(tool_call.args),
            remaining_budget=budget_before,
            history=to_jsonable([*messages, *prior_results]),
            tool_metadata=_tool_metadata(runtime, tool_call.function),
        )
        outcome = self._decide(task, request)
        message, execution_attempted, tool_error = self._apply(runtime, env, tool_call, outcome)
        self._write_call(task, tool_call, budget_before, outcome, execution_attempted, tool_error)
        return message

    def _decide(self, task: OpenTask, request: dict) -> dict:
        budget_before = task.remaining
        try:
            payload = call_component(self.policy, request, "decide")
        except Exception as error:
            task.policy_tokens += take_token_usage(self.policy)
            return _outcome(
                policy_decision="INVALID",
                policy_reason=str(error),
                final_decision="DENY",
                deny_reason=f"Policy output rejected: {error}",
                budget_after=budget_before,
            )
        task.policy_tokens += take_token_usage(self.policy)
        try:
            decision, reason = parse_policy_output(payload)
        except PolicyFormatError as error:
            return _outcome(
                policy_decision="INVALID",
                policy_reason=str(error),
                final_decision="DENY",
                deny_reason=f"Policy output rejected: {error}",
                budget_after=budget_before,
            )

        if decision == "APPROVE":
            return _outcome(
                policy_decision=decision,
                policy_reason=reason,
                final_decision="APPROVE",
                budget_after=budget_before,
            )
        if decision == "DENY":
            return _outcome(
                policy_decision=decision,
                policy_reason=reason,
                final_decision="DENY",
                deny_reason=reason,
                budget_after=budget_before,
            )

        task.requested_escalations += 1
        if budget_before <= 0:
            return _outcome(
                policy_decision="ESCALATE",
                policy_reason=reason,
                requested=True,
                final_decision="DENY",
                deny_reason="Escalation budget exhausted",
                budget_after=budget_before,
            )

        task.remaining -= 1
        task.actual_escalations += 1
        review = invoke_reviewer(self.reviewer, request, timeout_seconds=self.reviewer_timeout_seconds)
        task.reviewer_tokens += review.token_usage + review.retry_tokens
        task.reviewer_retry_count += review.retry_count
        task.reviewer_retry_tokens += review.retry_tokens
        if review.error is not None or review.decision is None:
            return _outcome(
                policy_decision="ESCALATE",
                policy_reason=reason,
                requested=True,
                actually_escalated=True,
                final_decision="DENY",
                deny_reason=review.error or review.reason,
                reviewer_reason=review.reason,
                budget_after=task.remaining,
                reviewer_retry_count=review.retry_count,
                reviewer_retry_tokens=review.retry_tokens,
            )
        return _outcome(
            policy_decision="ESCALATE",
            policy_reason=reason,
            requested=True,
            actually_escalated=True,
            reviewer_decision=review.decision,
            reviewer_reason=review.reason,
            final_decision=review.decision,
            deny_reason=review.reason if review.decision == "DENY" else None,
            budget_after=task.remaining,
            reviewer_retry_count=review.retry_count,
            reviewer_retry_tokens=review.retry_tokens,
        )

    def _apply(self, runtime, env, tool_call, outcome: dict):
        if outcome["final_decision"] != "APPROVE":
            reason = outcome["deny_reason"] or "Approval denied"
            return _tool_message(tool_call, reason, reason), False, None
        if _contains_function_call(tool_call.args) or not _known_tool(runtime, tool_call.function):
            reason = "Tool call was approved but cannot be executed"
            return _tool_message(tool_call, reason, reason), False, reason
        result, error = runtime.run_function(env, tool_call.function, tool_call.args)
        content = self.output_formatter(result)
        return _tool_message(tool_call, content, error), True, error

    def _write_call(self, task, tool_call, budget_before, outcome, execution_attempted, tool_error) -> None:
        record = {
            "run_id": task.run_id,
            "call_id": f"{task.run_id}-{task.next_call_index}",
            "policy_name": component_name(self.policy, "policy"),
            "tool_name": tool_call.function,
            "tool_arguments": to_jsonable(dict(tool_call.args)),
            "budget_before": budget_before,
            "budget_after": outcome["budget_after"],
            "policy_decision": outcome["policy_decision"],
            "policy_reason": outcome["policy_reason"],
            "requested_escalation": outcome["requested_escalation"],
            "actually_escalated": outcome["actually_escalated"],
            "reviewer_decision": outcome["reviewer_decision"],
            "reviewer_reason": outcome["reviewer_reason"],
            "final_decision": outcome["final_decision"],
            "execution_attempted": execution_attempted,
            "tool_error": tool_error,
            "deny_reason": outcome["deny_reason"],
            "reviewer_retry_count": outcome["reviewer_retry_count"],
            "reviewer_retry_tokens": outcome["reviewer_retry_tokens"],
        }
        task.next_call_index += 1
        self.gate_logger.write_call(record)

    def _require_task(self) -> OpenTask:
        if self._task is None:
            raise RuntimeError("Call start_task before query. Budget resets per task, not per agent turn.")
        return self._task

    @staticmethod
    def _coerce_string_lists(tool_call) -> None:
        for key, value in list(tool_call.args.items()):
            if isinstance(value, str) and is_string_list(value):
                tool_call.args[key] = literal_eval(value)


def _pre_approval_block(runtime: FunctionsRuntime, tool_call) -> tuple[str, str | None] | None:
    """Reject calls that must not reach the policy or spend budget."""
    if _contains_function_call(tool_call.args):
        return "Nested tool calls are not allowed", None
    if tool_call.function == EMPTY_FUNCTION_NAME:
        error = "Empty function name provided. Provide a valid function name."
        return error, error
    if tool_call.function not in runtime.functions:
        error = f"Invalid tool {tool_call.function} provided."
        return error, error
    return None


def _known_tool(runtime: FunctionsRuntime, tool_name: str) -> bool:
    return tool_name != EMPTY_FUNCTION_NAME and tool_name in runtime.functions


def _contains_function_call(value) -> bool:
    if isinstance(value, FunctionCall):
        return True
    if isinstance(value, dict):
        return any(_contains_function_call(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_function_call(item) for item in value)
    return False


def _tool_metadata(runtime: FunctionsRuntime, tool_name: str) -> dict | None:
    function = runtime.functions.get(tool_name)
    if function is None:
        return None
    try:
        parameters = function.parameters.model_json_schema()
    except Exception:
        parameters = None
    return {"name": function.name, "description": function.description, "parameters": parameters}


def _tool_message(tool_call, content: str, error: str | None) -> ChatToolResultMessage:
    return ChatToolResultMessage(
        role="tool",
        content=[text_content_block_from_string(content)],
        tool_call_id=tool_call.id,
        tool_call=tool_call,
        error=error,
    )


def _outcome(
    policy_decision: str,
    policy_reason: str,
    final_decision: str,
    budget_after: int,
    deny_reason: str | None = None,
    requested: bool = False,
    actually_escalated: bool = False,
    reviewer_decision: str | None = None,
    reviewer_reason: str | None = None,
    reviewer_retry_count: int = 0,
    reviewer_retry_tokens: int = 0,
) -> dict:
    return {
        "policy_decision": policy_decision,
        "policy_reason": policy_reason,
        "requested_escalation": requested,
        "actually_escalated": actually_escalated,
        "reviewer_decision": reviewer_decision,
        "reviewer_reason": reviewer_reason,
        "final_decision": final_decision,
        "deny_reason": deny_reason,
        "budget_after": budget_after,
        "reviewer_retry_count": reviewer_retry_count,
        "reviewer_retry_tokens": reviewer_retry_tokens,
    }
