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


def test_tool_arguments_match_the_executed_call():
    request = build_request(
        "Organize project files",
        "read_file",
        {"path": "temp.txt", "task": "delete_all", "ground_truth": "secret"},
        1,
        history=[{"role": "user", "content": "go", "attack": "ignore", "ground_truth": "label"}],
        tool_metadata={"name": "read_file", "description": "Read", "oracle": "yes", "parameters": {"task": "string"}},
    )
    assert request["tool_arguments"] == {"path": "temp.txt", "task": "delete_all", "ground_truth": "secret"}
    assert request["history"] == [{"role": "user", "content": "go"}]
    assert request["tool_metadata"] == {
        "name": "read_file",
        "description": "Read",
        "parameters": {"task": "string"},
    }


def test_seen_arguments_are_the_arguments_that_run(tmp_path):
    def write_note(task: str) -> str:
        """Write a note.

        :param task: The note to write.
        """
        write_note.executed.append(task)
        return task

    write_note.executed = []
    functions = FunctionsRuntime()
    functions.register_function(write_note)
    seen = {}

    class Capture:
        name = "capture"
        last_token_usage = 0

        def decide(self, request):
            seen.update(request["tool_arguments"])
            return {"decision": "APPROVE", "reason": "args match"}

    executor = gate(tmp_path, Capture(), FakeReviewer(), k=0)
    ask(executor, functions, [one_call(name="write_note", args={"task": "delete_all"})])
    assert seen == {"task": "delete_all"}
    assert write_note.executed == ["delete_all"]


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


def test_gate_records_late_usage_without_keeping_the_shared_counter(tmp_path):
    functions = runtime()

    class SlowReviewer:
        name = "slow-reviewer"
        last_token_usage = 17

        def review(self, request, timeout_seconds=None):
            time.sleep(1.2)
            self.last_token_usage = 99
            return {"decision": "APPROVE", "reason": "too late"}

    executor = gate(tmp_path, FullEscalate(), SlowReviewer(), k=2, timeout=0.2)
    ask(executor, functions, [one_call(args={"path": "temp.txt"})])
    assert read_file.executed == []
    deadline = time.time() + 3
    late_text = ""
    while time.time() < deadline:
        if executor.gate_logger.calls_path.exists():
            late_text = executor.gate_logger.calls_path.read_text(encoding="utf-8")
            if "late_reviewer_usage" in late_text:
                break
        time.sleep(0.05)
    assert "late_reviewer_usage" in late_text
    assert '"late_reviewer_tokens": 99' in late_text

    class FiveTokenReviewer:
        name = "five-reviewer"
        last_token_usage = 0

        def review(self, request):
            self.last_token_usage = 5
            return {"decision": "DENY", "reason": "next call"}

    executor.reviewer = FiveTokenReviewer()
    ask(executor, functions, [one_call(args={"path": "other.txt"}, call_id="call-2")])
    task = executor.finish_task(False, False)
    assert task["tokens"]["reviewer"] == 104
    assert read_file.executed == []


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
    assert pipeline.name == "scripted__full_approve__k0__default"
    other = build_approval_pipeline(config, gate(tmp_path / "other", FullEscalate(), FakeReviewer(), k=2), "attack")
    assert other.name == "scripted__full_escalate__k2__attack"
    pipeline.query("Organize project files", functions)
    assert read_file.executed == ["temp.txt"]
