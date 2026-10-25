"""Experiment pipeline that runs the approval executor instead of ToolsExecutor."""

import re

from agentdojo.agent_pipeline.agent_pipeline import AgentPipeline, PipelineConfig, get_llm
from agentdojo.agent_pipeline.basic_elements import InitQuery, SystemMessage
from agentdojo.agent_pipeline.tool_execution import ToolsExecutionLoop
from agentdojo.models import MODEL_PROVIDERS, ModelsEnum

from approval_gate.contract import component_name
from approval_gate.executor import ApprovalGatedToolsExecutor


def experiment_pipeline_name(model_name: str, policy_name: str, k: int, config_id: str = "default") -> str:
    """Name AgentDojo uses as the result directory. One name per model, policy, k, and config."""
    raw = f"{model_name}__{policy_name}__k{k}__{config_id}"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("_")


def build_approval_pipeline(
    config: PipelineConfig,
    gate: ApprovalGatedToolsExecutor,
    config_id: str = "default",
) -> AgentPipeline:
    """Same shape as AgentPipeline.from_config with no defense, but the tool step is the gate.

    The returned pipeline does not call start_task or finish_task. The experiment
    runner must do that once around the whole task, not once per agent turn.
    """
    if config.defense is not None:
        raise ValueError("The approval pipeline does not add AgentDojo defenses. Pass defense=None.")
    llm = (
        get_llm(MODEL_PROVIDERS[ModelsEnum(config.llm)], config.llm, config.model_id, config.tool_delimiter)
        if isinstance(config.llm, str)
        else config.llm
    )
    llm_name = config.llm if isinstance(config.llm, str) else getattr(llm, "name", "custom-llm")
    if config.system_message is None:
        raise ValueError("PipelineConfig.system_message is missing")
    tools_loop = ToolsExecutionLoop([gate, llm])
    pipeline = AgentPipeline([SystemMessage(config.system_message), InitQuery(), llm, tools_loop])
    pipeline.name = experiment_pipeline_name(
        str(llm_name),
        component_name(gate.policy, "policy"),
        gate.k,
        config_id,
    )
    return pipeline
