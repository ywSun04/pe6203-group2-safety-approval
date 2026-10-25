"""Two JSONL logs: one row per tool call, one row per task run."""

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
