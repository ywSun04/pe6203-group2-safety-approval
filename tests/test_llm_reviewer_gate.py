"""Real gate, real reviewer adapter, fake tools and scripted model responses."""
import pytest
from agentdojo.functions_runtime import FunctionCall, FunctionsRuntime
from approval_gate.executor import ApprovalGatedToolsExecutor
from approval_gate.records import GateLogger
from approval_gate.stubs import FullEscalate
from reviewer.llm_reviewer import LlmReviewer
from tests.test_llm_reviewer import Client, response


@pytest.mark.parametrize("decision,expected", [("APPROVE", ["public.txt"]), ("DENY", [])])
def test_execution_budget_and_cost(tmp_path, decision, expected):
    executed = []
    def read_file(path: str) -> str:
        """Read file.

        :param path: File path.
        """
        executed.append(path); return "public contents"
    runtime = FunctionsRuntime(); runtime.register_function(read_file)
    client = Client(response('{"decision":"' + decision + '","reason":"Scope checked"}'))
    gate = ApprovalGatedToolsExecutor(FullEscalate(), LlmReviewer("test-model", client), GateLogger(tmp_path), k=1)
    gate.start_task("reviewer-smoke", "synthetic-task")
    calls = [FunctionCall(function="read_file", args={"path":p}, id=str(i)) for i,p in enumerate(["public.txt", "second.txt"])]
    gate.query("Read public.txt", runtime, messages=[{"role":"assistant", "content":None, "tool_calls":calls}])
    summary = gate.finish_task(None, None)
    assert executed == expected and len(client.calls) == 1
    assert summary["actual_escalation_count"] == 1 and summary["requested_escalation_count"] == 2
    assert summary["tokens"]["reviewer"] == 17 and summary["reviewer_retry_tokens"] == 0


@pytest.mark.parametrize("error", [False, True])
def test_invalid_or_timed_out_review_cannot_execute(tmp_path, error):
    executed = []
    def read_file(path: str) -> str:
        """Read file.

        :param path: File path.
        """
        executed.append(path); return "data"
    runtime = FunctionsRuntime(); runtime.register_function(read_file)
    client = Client(response('{"decision":"ESCALATE","reason":"no"}'), error=TimeoutError() if error else None)
    gate = ApprovalGatedToolsExecutor(FullEscalate(), LlmReviewer("test-model", client), GateLogger(tmp_path), k=1)
    gate.start_task("failure", "synthetic-task")
    call = FunctionCall(function="read_file", args={"path":"public.txt"}, id="one")
    gate.query("Read public.txt", runtime, messages=[{"role":"assistant", "content":None, "tool_calls":[call]}])
    summary = gate.finish_task(None, None)
    assert not executed and summary["actual_escalation_count"] == 1
    assert summary["tokens"]["reviewer"] == (0 if error else 17)


@pytest.mark.parametrize("policy", ["basic_risk", "budget_aware"])
def test_full_pipeline_with_both_shared_policies(tmp_path, policy):
    from examples.reviewer_gate_smoke import run
    result = run(tmp_path, policy)
    assert result["executed"] == ["team@example.test"]
    assert result["task"]["tokens"]["reviewer"] == 34
