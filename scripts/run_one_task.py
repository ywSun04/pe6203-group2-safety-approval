"""Run one AgentDojo user task through the approval gate.

This is a single-task connection example. It is not the group's benchmark driver.
Member 2 owns the task suite sweep, attack configuration, and result cache.
A live model call from this script has not been verified.

The command checks the model settings before it constructs a client. Missing
settings print the names that are still required and do not send a request.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from approval_gate.model_env import missing_model_settings


def new_run_id() -> str:
    """A new log id. Reusing one id in the same directory mixes appended rows."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"run-{stamp}-{uuid.uuid4().hex[:8]}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one user task through the approval gate.")
    parser.add_argument("--policy", required=True, choices=("full-approve", "full-escalate"))
    parser.add_argument("--k", type=int, default=0, help="Escalation budget for this task. Default: 0.")
    parser.add_argument("--suite", default="workspace")
    parser.add_argument("--suite-version", default="v1.2.2")
    parser.add_argument("--task", default="user_task_0")
    parser.add_argument("--config-id", default="smoke", help="Becomes part of pipeline.name so result caches stay separate.")
    parser.add_argument("--log-dir", type=Path, required=True)
    parser.add_argument(
        "--run-id",
        default=None,
        help="Log id for this run. Omit it to generate a new id. Reusing an id in the same log directory mixes rows.",
    )
    parser.add_argument("--model", help="A model name from AgentDojo ModelsEnum. This script does not choose one.")
    parser.add_argument("--model-id", default=None, help="Required for openai-compatible and some local servers.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.model:
        print(
            "No model was given, so this script did not call a model.\n"
            "Pass --model with a name from AgentDojo ModelsEnum, for example gpt-4o-mini-2024-07-18.\n"
            "This entry does not choose the group's model.",
            file=sys.stderr,
        )
        return 2
    try:
        missing = missing_model_settings(args.model, args.model_id)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        print("This script did not call a model.", file=sys.stderr)
        return 2
    if missing:
        print("Model configuration is missing, so this script did not call a model.", file=sys.stderr)
        print(f"Model: {args.model}", file=sys.stderr)
        print("Set these and run again:", file=sys.stderr)
        for item in missing:
            print(f"- {item}", file=sys.stderr)
        print("A live run from this entry is still unverified.", file=sys.stderr)
        return 2
    return _run_configured_task(args)


def _run_configured_task(args: argparse.Namespace) -> int:
    from agentdojo.agent_pipeline.agent_pipeline import PipelineConfig
    from agentdojo.task_suite.load_suites import get_suite

    from approval_gate.executor import ApprovalGatedToolsExecutor
    from approval_gate.pipeline import build_approval_pipeline
    from approval_gate.records import GateLogger
    from approval_gate.reviewer import FakeReviewer
    from approval_gate.stubs import FullApprove, FullEscalate

    policy = FullApprove() if args.policy == "full-approve" else FullEscalate()
    suite = get_suite(args.suite_version, args.suite)
    task = suite.get_user_task_by_id(args.task)
    gate = ApprovalGatedToolsExecutor(policy, FakeReviewer(), GateLogger(args.log_dir), k=args.k)
    pipeline = build_approval_pipeline(
        PipelineConfig(
            llm=args.model,
            model_id=args.model_id,
            defense=None,
            system_message_name=None,
        ),
        gate,
        config_id=args.config_id,
    )
    run_id = args.run_id or new_run_id()
    print(f"run_id={run_id}")
    print(f"Pipeline: {pipeline.name}")
    print("The stand-in reviewer approves. Replace it with Member 4's reviewer when that module arrives.")
    gate.start_task(run_id, task.ID)
    try:
        utility, security = suite.run_task_with_pipeline(pipeline, task, injection_task=None, injections={})
    except Exception:
        gate.finish_task(False, False)
        raise
    record = gate.finish_task(utility, security)
    print(f"utility={utility} security={security}")
    print(f"task log: {gate.gate_logger.tasks_path}")
    print(f"call log: {gate.gate_logger.calls_path}")
    print(f"tokens.reviewer={record['tokens']['reviewer']} tokens.agent={record['tokens']['agent']}")
    print("tokens.agent stays 0 until the runner records model usage with add_agent_tokens.")
    print("The stock AgentDojo model client does not do that. This single task is not the official suite.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
