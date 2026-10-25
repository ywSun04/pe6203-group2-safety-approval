"""Two JSONL logs: one row per tool call, one row per task run.

tokens.reviewer is the total reviewer spend. It includes failed calls and
technical retries. reviewer_retry_tokens is the retry portion already included
in that total. Do not add the two numbers together.

A timed-out review can append a later row with record_type late_reviewer_usage.
included_in_task_total says whether that cost is already in the task row.
Add late_reviewer_tokens only when that field is false.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class GateLogger:
    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.calls_path = self.directory / "calls.jsonl"
        self.tasks_path = self.directory / "tasks.jsonl"

    def write_call(self, record: dict[str, Any]) -> None:
        self._append(self.calls_path, record)

    def write_task(self, record: dict[str, Any]) -> None:
        self._append(self.tasks_path, record)

    def _append(self, path: Path, record: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, default=str)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
