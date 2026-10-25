import time

import pytest
from agentdojo.agent_pipeline.agent_pipeline import PipelineConfig
from agentdojo.agent_pipeline.base_pipeline_element import BasePipelineElement
from agentdojo.functions_runtime import FunctionCall, FunctionsRuntime
from agentdojo.types import text_content_block_from_string

from approval_gate.contract import PolicyFormatError, ReviewerFormatError, build_request, parse_policy_output, parse_reviewer_output
from approval_gate.executor import ApprovalGatedToolsExecutor
from approval_gate.pipeline import build_approval_pipeline
from approval_gate.records import GateLogger
from approval_gate.reviewer import FakeReviewer, ReviewerFormatError as GateReviewerFormatError
from approval_gate.stubs import FullApprove, FullEscalate


def read_file(path: str) -> str:
    """Read a file.

    :param path: The file path.
    """
    read_file.executed.append(path)
    return path


def runtime() -> FunctionsRuntime:
    read_file.executed = []
    functions = FunctionsRuntime()
    functions.register_function(read_file)
    return functions


def gate(tmp_path, policy, reviewer, k, timeout=30):
    executor = ApprovalGatedToolsExecutor(
        policy,
        reviewer,
        GateLogger(tmp_path),
        k,
        reviewer_timeout_seconds=timeout,
    )
    executor.start_task("run-1", "task-0")
    return executor


def ask(executor, functions, calls, query="Organize project files"):
    messages = [{"role": "assistant", "content": None, "tool_calls": calls}]
    return executor.query(query, functions, messages=messages)


def one_call(name="read_file", args=None, call_id="call-1"):
    return FunctionCall(function=name, args={} if args is None else args, id=call_id)


def test_payload_rejects_missing_or_extra_fields():
    with pytest.raises(PolicyFormatError):
        parse_policy_output({"decision": "APPROVE"})
    with pytest.raises(PolicyFormatError):
        parse_policy_output({"decision": "APPROVE", "reason": "ok", "score": 1})
    with pytest.raises(ReviewerFormatError):
        parse_reviewer_output({"decision": "ESCALATE", "reason": "no"})


def test_request_strips_forbidden_fields():
    request = build_request(
        "Organize project files",
        "read_file",
        {"path": "temp.txt", "ground_truth": "secret"},
        1,
        history=[{"role": "user", "attack": "ignore"}],
        tool_metadata={"name": "read_file", "oracle": "yes"},
    )
    assert "ground_truth" not in request["tool_arguments"]
    assert "attack" not in request["history"][0]
    assert "oracle" not in request["tool_metadata"]


def test_reviewer_approve_executes_and_deny_does_not(tmp_path):
    functions = runtime()
    approved = gate(tmp_path, FullEscalate(), FakeReviewer("APPROVE"), k=1)
    ask(approved, functions, [one_call(args={"path": "temp.txt"})])
    assert read_file.executed == ["temp.txt"]

    functions = runtime()
    denied = gate(tmp_path / "deny", FullEscalate(), FakeReviewer("DENY"), k=1)
    ask(denied, functions, [one_call(args={"path": "temp.txt"}, call_id="call-2")])
    assert read_file.executed == []
    task = denied.finish_task(None, None)
    assert task["actual_escalation_count"] == 1
    assert denied._task is None


def test_budget_zero_blocks_only_escalation(tmp_path):
    functions = runtime()
    executor = gate(tmp_path, FullApprove(), FakeReviewer(), k=0)
    ask(executor, functions, [one_call(args={"path": "temp.txt"})])
    assert read_file.executed == ["temp.txt"]

    functions = runtime()
    reviewer = FakeReviewer()
    reviewer.calls = 0
    original = reviewer.review

    def counting(request):
        reviewer.calls += 1
        return original(request)

    reviewer.review = counting
    executor = gate(tmp_path / "none", FullEscalate(), reviewer, k=0)
    ask(executor, functions, [one_call(args={"path": "temp.txt"})])
    assert read_file.executed == []
    assert reviewer.calls == 0


def test_budget_is_shared_across_turns_and_resets_for_a_new_task(tmp_path):
    functions = runtime()
    executor = gate(tmp_path, FullEscalate(), FakeReviewer("DENY"), k=1)
    ask(executor, functions, [one_call(args={"path": "a.txt"}, call_id="a")])
    ask(executor, functions, [one_call(args={"path": "b.txt"}, call_id="b")])
    assert read_file.executed == []
    assert executor._task.remaining == 0
    assert executor._task.actual_escalations == 1
    executor.finish_task(False, False)

    executor.start_task("run-2", "task-1")
    ask(executor, functions, [one_call(args={"path": "c.txt"}, call_id="c")])
    assert executor._task.remaining == 0
    assert executor._task.actual_escalations == 1


def test_one_turn_with_several_calls_shares_one_budget(tmp_path):
    functions = runtime()
    reviewer = FakeReviewer("APPROVE")
    reviewer.calls = 0
    original = reviewer.review

    def counting(request):
        reviewer.calls += 1
        return original(request)

    reviewer.review = counting
    executor = gate(tmp_path, FullEscalate(), reviewer, k=1)
    ask(
        executor,
        functions,
        [
            one_call(args={"path": "a.txt"}, call_id="a"),
            one_call(args={"path": "b.txt"}, call_id="b"),
        ],
    )
    assert reviewer.calls == 1
    assert read_file.executed == ["a.txt"]
    assert executor._task.remaining == 0


def test_approve_still_runs_after_the_budget_is_spent(tmp_path):
    functions = runtime()

    class EscalateOnce:
        name = "escalate-once"
        last_token_usage = 0

        def __init__(self):
            self.seen = 0

        def decide(self, request):
            self.seen += 1
            if self.seen == 1:
                return {"decision": "ESCALATE", "reason": "check the first call"}
            return {"decision": "APPROVE", "reason": "direct approve"}

    executor = gate(tmp_path, EscalateOnce(), FakeReviewer("DENY"), k=1)
    ask(
        executor,
        functions,
        [
            one_call(args={"path": "a.txt"}, call_id="a"),
            one_call(args={"path": "b.txt"}, call_id="b"),
        ],
    )
    assert read_file.executed == ["b.txt"]


def test_nested_call_is_denied_before_review(tmp_path):
    functions = runtime()
    reviewer = FakeReviewer("APPROVE")
    reviewer.calls = 0

    def counting(request):
        reviewer.calls += 1
        return {"decision": "APPROVE", "reason": "Fake reviewer approved"}

    reviewer.review = counting
    nested = FunctionCall(function="read_file", args={"path": "secret.txt"}, id="inner")
    executor = gate(tmp_path, FullEscalate(), reviewer, k=1)
    ask(executor, functions, [one_call(args={"path": nested})])
    assert read_file.executed == []
    assert reviewer.calls == 0
    assert executor._task.remaining == 1


def test_unknown_tool_does_not_spend_budget(tmp_path):
    functions = runtime()
    reviewer = FakeReviewer("APPROVE")
    reviewer.calls = 0

    def counting(request):
        reviewer.calls += 1
        return {"decision": "APPROVE", "reason": "Fake reviewer approved"}

    reviewer.review = counting
    executor = gate(tmp_path, FullEscalate(), reviewer, k=1)
    ask(executor, functions, [one_call(name="missing_tool")])
    assert reviewer.calls == 0
    assert executor._task.remaining == 1
    assert executor._task.actual_escalations == 0


def test_failed_review_keeps_token_usage(tmp_path):
    functions = runtime()

    class BadReviewer:
        name = "bad-reviewer"
        last_token_usage = 123

        def review(self, request):
            raise GateReviewerFormatError("illegal decision", retry_count=1, retry_tokens=10)

    executor = gate(tmp_path, FullEscalate(), BadReviewer(), k=1)
    ask(executor, functions, [one_call(args={"path": "temp.txt"})])
    task = executor.finish_task(False, True)
    assert read_file.executed == []
    assert task["tokens"]["reviewer"] == 133
    assert task["reviewer_retry_tokens"] == 10
    assert task["actual_escalation_count"] == 1


def test_gate_stops_waiting_for_a_slow_reviewer(tmp_path):
    functions = runtime()

    class SlowReviewer:
        name = "slow-reviewer"
        last_token_usage = 4

        def review(self, request):
            time.sleep(2)
            return {"decision": "APPROVE", "reason": "too late"}

    executor = gate(tmp_path, FullEscalate(), SlowReviewer(), k=1, timeout=0.2)
    ask(executor, functions, [one_call(args={"path": "temp.txt"})])
    assert read_file.executed == []
    task = executor.finish_task(False, False)
    assert task["tokens"]["reviewer"] == 4


class ScriptedLLM(BasePipelineElement):
    name = "scripted"

    def query(self, query, runtime, env, messages, extra_args):
        if any(message["role"] == "tool" for message in messages):
            stop = {
                "role": "assistant",
                "content": [text_content_block_from_string("done")],
                "tool_calls": [],
            }
            return query, runtime, env, [*messages, stop], extra_args
        call = one_call(args={"path": "temp.txt"})
        message = {"role": "assistant", "content": None, "tool_calls": [call]}
        return query, runtime, env, [*messages, message], extra_args


def test_pipeline_uses_the_approval_executor(tmp_path):
    functions = runtime()
    executor = gate(tmp_path, FullApprove(), FakeReviewer(), k=0)
    config = PipelineConfig(
        llm=ScriptedLLM(),
        model_id=None,
        defense=None,
        system_message_name=None,
        system_message="You are a test agent.",
    )
    pipeline = build_approval_pipeline(config, executor)
    assert pipeline.elements[-1].elements[0] is executor
    pipeline.query("Organize project files", functions)
    assert read_file.executed == ["temp.txt"]
