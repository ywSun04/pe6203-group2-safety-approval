"""Offline smoke check for BudgetAwarePolicy inside the approval gate.

Run: python -m examples.budget_gate_smoke --log-dir logs/budget-gate-smoke
It uses local fake tools and FakeReviewer. No model API or real outbound action.
This is a wiring check, not an AgentDojo benchmark result.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import uuid4

from agentdojo.functions_runtime import FunctionCall, FunctionsRuntime
from agentdojo.types import text_content_block_from_string

from approval_gate.executor import ApprovalGatedToolsExecutor
from approval_gate.policies import make_policy
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


def delete_file(file_id: str) -> str:
    """A fake delete; no file is removed.

    :param file_id: Fake file id.
    """
    return f"Fake delete recorded for {file_id}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-dir", type=Path, default=Path("logs/budget-gate-smoke"))
    parser.add_argument("--k", type=int, default=1)
    options = parser.parse_args()
    runtime = FunctionsRuntime()
    runtime.register_function(search_files)
    runtime.register_function(send_email)
    runtime.register_function(delete_file)
    gate = ApprovalGatedToolsExecutor(
        make_policy("budget_aware"),
        FakeReviewer("APPROVE"),
        GateLogger(options.log_dir),
        k=options.k,
    )
    gate.start_task("offline-budget-" + uuid4().hex[:12], "synthetic-budget-smoke")
    calls = [
        FunctionCall(id="search", function="search_files", args={"query": "project notes"}),
        FunctionCall(id="delete", function="delete_file", args={"file_id": "notes.txt"}),
        FunctionCall(id="send-1", function="send_email", args={
            "recipients": ["colleague@example.test"], "body": "Synthetic notes",
        }),
        FunctionCall(id="send-2", function="send_email", args={
            "recipients": ["colleague@example.test"], "body": "A second synthetic message",
        }),
        FunctionCall(id="read-after", function="search_files", args={"query": "schedule"}),
    ]
    messages = [{"role": "assistant", "content": [text_content_block_from_string("")], "tool_calls": calls}]
    gate.query("Find notes and send a summary to a colleague.", runtime, messages=messages)
    summary = gate.finish_task(task_completed=None, security_passed=None)
    logged = [
        json.loads(line)
        for line in (options.log_dir / "calls.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    print(json.dumps({
        "policy": gate.policy.name,
        "k": options.k,
        "calls": [
            {
                "tool": row["tool_name"],
                "policy_decision": row["policy_decision"],
                "final_decision": row["final_decision"],
                "budget_before": row["budget_before"],
                "budget_after": row["budget_after"],
            }
            for row in logged
        ],
        "actual_escalation_count": summary["actual_escalation_count"],
    }, indent=2))
    print(f"Offline budget-gate logs: {options.log_dir}")


if __name__ == "__main__":
    main()
