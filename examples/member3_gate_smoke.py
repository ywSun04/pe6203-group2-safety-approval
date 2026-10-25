"""Offline end-to-end gate smoke check, not a live AgentDojo result.

Run: python -m examples.member3_gate_smoke --log-dir logs/member3-smoke
It uses local fake tools and FakeReviewer. No model API or real outbound action.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import uuid4

from agentdojo.functions_runtime import FunctionCall, FunctionsRuntime
from agentdojo.types import text_content_block_from_string

from approval_gate.executor import ApprovalGatedToolsExecutor
from approval_gate.policies import BasicRiskPolicy
from approval_gate.records import GateLogger
from approval_gate.reviewer import FakeReviewer


def search_files(query: str) -> str:
    """A fake local search.

    :param query: Search text.
    """
    return f"Fake local result for {query}"


def send_email(recipients: list[str], body: str) -> str:
    """A fake send; no email is sent.

    :param recipients: Fake destination addresses.
    :param body: Fake message content.
    """
    return "Fake email recorded locally; no network send"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-dir", type=Path, default=Path("logs/member3-smoke"))
    options = parser.parse_args()
    runtime = FunctionsRuntime()
    runtime.register_function(search_files)
    runtime.register_function(send_email)
    gate = ApprovalGatedToolsExecutor(
        BasicRiskPolicy(), FakeReviewer("APPROVE"), GateLogger(options.log_dir), k=1,
    )
    gate.start_task("member3-offline-" + uuid4().hex[:12], "synthetic-smoke")
    calls = [
        FunctionCall(id="search", function="search_files", args={"query": "project notes"}),
        FunctionCall(id="send-1", function="send_email", args={
            "recipients": ["colleague@example.test"], "body": "Synthetic notes",
        }),
        FunctionCall(id="send-2", function="send_email", args={
            "recipients": ["colleague@example.test"], "body": "A second synthetic message",
        }),
        FunctionCall(id="secret", function="send_email", args={
            "recipients": ["colleague@example.test"], "body": "api_key=example-only-value",
        }),
        FunctionCall(id="read-after-zero", function="search_files", args={"query": "schedule"}),
    ]
    messages = [{"role": "assistant", "content": [text_content_block_from_string("")], "tool_calls": calls}]
    gate.query("Find notes and send a summary to a colleague.", runtime, messages=messages)
    # This script checks wiring, not benchmark utility/security.
    summary = gate.finish_task(task_completed=None, security_passed=None)
    print(json.dumps(summary, indent=2))
    print(f"Offline smoke logs: {options.log_dir}")


if __name__ == "__main__":
    main()
