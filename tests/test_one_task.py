"""One real AgentDojo user task, replayed through the approval gate.

This does not call a model API. The scripted model emits the task's own ground-truth
tool calls, and the gate is the component that executes them.
"""

from agentdojo.agent_pipeline.agent_pipeline import PipelineConfig
from agentdojo.agent_pipeline.base_pipeline_element import BasePipelineElement
from agentdojo.task_suite.load_suites import get_suite
from agentdojo.types import text_content_block_from_string

from approval_gate.pipeline import build_approval_pipeline
from approval_gate.records import GateLogger
from approval_gate.reviewer import FakeReviewer
from approval_gate.stubs import FullApprove
from approval_gate.executor import ApprovalGatedToolsExecutor


class GroundTruthReplay(BasePipelineElement):
    name = "ground-truth-replay"

    def __init__(self, task) -> None:
        self.task = task
        self.calls = None
        self.index = 0

    def query(self, query, runtime, env, messages, extra_args):
        if self.calls is None:
            self.calls = list(self.task.ground_truth(env))
        if self.index < len(self.calls):
            call = self.calls[self.index]
            self.index += 1
            message = {
                "role": "assistant",
                "content": [text_content_block_from_string("")],
                "tool_calls": [call],
            }
        else:
            message = {
                "role": "assistant",
                "content": [text_content_block_from_string(self.task.GROUND_TRUTH_OUTPUT)],
                "tool_calls": [],
            }
        return query, runtime, env, [*messages, message], extra_args


def test_workspace_user_task_runs_through_the_gate(tmp_path):
    suite = get_suite("v1.2.2", "workspace")
    task = suite.get_user_task_by_id("user_task_0")
    gate = ApprovalGatedToolsExecutor(FullApprove(), FakeReviewer(), GateLogger(tmp_path), k=0)
    pipeline = build_approval_pipeline(
        PipelineConfig(
            llm=GroundTruthReplay(task),
            model_id=None,
            defense=None,
            system_message_name=None,
            system_message="You are a test agent.",
        ),
        gate,
        config_id="workspace-user-task-0",
    )
    gate.start_task("workspace-user-task-0", task.ID)
    utility, security = suite.run_task_with_pipeline(pipeline, task, injection_task=None, injections={})
    record = gate.finish_task(utility, security)
    assert utility is True
    assert security is True
    assert record["task_completed"] is True
    assert gate.gate_logger.calls_path.exists()
