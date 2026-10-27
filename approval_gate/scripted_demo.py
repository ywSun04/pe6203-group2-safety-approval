"""Three scripted decisions for a talk. No model API is called.

The logs are test data. They are not a live-model run and not an official benchmark result.
"""

from __future__ import annotations

import json
from pathlib import Path

from agentdojo.functions_runtime import FunctionCall, FunctionsRuntime

from approval_gate.executor import ApprovalGatedToolsExecutor
from approval_gate.records import GateLogger
from approval_gate.stubs import FullEscalate


def read_file(path: str) -> str:
    """Read a file.

    :param path: The file path.
    """
    read_file.executed.append(path)
    return path


class DemoReviewer:
    """Stand-in reviewer used only by the scripted demo."""

    name = "scripted_demo_reviewer"

    def __init__(self, decision: str) -> None:
        self.decision = decision
        self.last_token_usage = 0
        self.calls = 0

    def review(self, request: dict, timeout_seconds: float | None = None) -> dict:
        self.calls += 1
        self.last_token_usage = 11
        return {"decision": self.decision, "reason": f"Scripted demo {self.decision}"}


def run_scripted_demo(output_dir: str | Path) -> dict:
    """Write three labeled cases and return a short summary of each."""
    root = Path(output_dir)
    if root.exists():
        for path in root.rglob("*.jsonl"):
            path.unlink()
    approved = _run_case(root / "reviewer-approves", "APPROVE", 1, ["notes.txt"])
    denied = _run_case(root / "reviewer-denies", "DENY", 1, ["notes.txt"])
    exhausted = _run_case(root / "budget-exhausted", "APPROVE", 1, ["first.txt", "second.txt"])
    summary = {
        "label": "Scripted demo. Test data. Not a live-model result.",
        "reviewer-approves": approved,
        "reviewer-denies": denied,
        "budget-exhausted": exhausted,
    }
    _write_label(root, summary)
    return summary


def _run_case(directory: Path, decision: str, k: int, paths: list[str]) -> dict:
    read_file.executed = []
    reviewer = DemoReviewer(decision)
    functions = FunctionsRuntime()
    functions.register_function(read_file)
    gate = ApprovalGatedToolsExecutor(FullEscalate(), reviewer, GateLogger(directory), k=k)
    gate.start_task(directory.name, "scripted-demo")
    calls = [FunctionCall(function="read_file", args={"path": path}, id=f"call-{index}") for index, path in enumerate(paths, start=1)]
    gate.query(
        "Organize project files",
        functions,
        messages=[{"role": "assistant", "content": None, "tool_calls": calls}],
    )
    task = gate.finish_task(False, False)
    calls_text = (directory / "calls.jsonl").read_text(encoding="utf-8")
    return {
        "executed": list(read_file.executed),
        "reviewer_calls": reviewer.calls,
        "task_reviewer_tokens": task["tokens"]["reviewer"],
        "actual_escalation_count": task["actual_escalation_count"],
        "requested_escalation_count": task["requested_escalation_count"],
        "call_rows": [json.loads(line) for line in calls_text.splitlines() if line],
    }


def _write_label(root: Path, summary: dict) -> None:
    root.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Scripted demo",
        "",
        "These logs are test data. A fake reviewer and a local `read_file` tool produced them.",
        "They are not a live-model result and not an official AgentDojo benchmark result.",
        "",
        "- `reviewer-approves`: the reviewer returns APPROVE, and the tool runs.",
        "- `reviewer-denies`: the reviewer returns DENY, the tool does not run, and the budget still decreases by one.",
        "- `budget-exhausted`: the first escalation uses the only budget unit. The second escalation is denied and does not call the reviewer.",
        "",
        "```json",
        json.dumps(
            {
                "reviewer-approves": {
                    "executed": summary["reviewer-approves"]["executed"],
                    "reviewer_calls": summary["reviewer-approves"]["reviewer_calls"],
                },
                "reviewer-denies": {
                    "executed": summary["reviewer-denies"]["executed"],
                    "reviewer_calls": summary["reviewer-denies"]["reviewer_calls"],
                },
                "budget-exhausted": {
                    "executed": summary["budget-exhausted"]["executed"],
                    "reviewer_calls": summary["budget-exhausted"]["reviewer_calls"],
                    "requested_escalation_count": summary["budget-exhausted"]["requested_escalation_count"],
                    "actual_escalation_count": summary["budget-exhausted"]["actual_escalation_count"],
                },
            },
            indent=2,
        ),
        "```",
        "",
    ]
    (root / "README.md").write_text("\n".join(lines), encoding="utf-8")
