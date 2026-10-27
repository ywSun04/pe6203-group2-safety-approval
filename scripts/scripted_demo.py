"""Write the three scripted demo logs under demo/scripted."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from approval_gate.scripted_demo import run_scripted_demo


def main() -> None:
    summary = run_scripted_demo(ROOT / "demo" / "scripted")
    approved = summary["reviewer-approves"]
    denied = summary["reviewer-denies"]
    exhausted = summary["budget-exhausted"]
    if approved["executed"] != ["notes.txt"] or approved["reviewer_calls"] != 1:
        raise SystemExit("reviewer-approves did not execute the tool")
    if denied["executed"] != [] or denied["reviewer_calls"] != 1:
        raise SystemExit("reviewer-denies executed a tool or skipped the reviewer")
    if exhausted["executed"] != ["first.txt"] or exhausted["reviewer_calls"] != 1:
        raise SystemExit("budget-exhausted called the reviewer twice or skipped the first tool")
    if exhausted["requested_escalation_count"] != 2 or exhausted["actual_escalation_count"] != 1:
        raise SystemExit("budget-exhausted did not keep requested and actual escalations apart")
    print("Wrote scripted demo logs to demo/scripted")
    print(summary["label"])


if __name__ == "__main__":
    main()
