"""Verify the group's pinned AgentDojo source; distribution version alone is insufficient."""

from __future__ import annotations

import json
import sys
from importlib.metadata import PackageNotFoundError, distribution, version

EXPECTED_COMMIT = "089ed468cf3ed0322acc66b0211f26d9d90dbf60"


def main() -> int:
    try:
        package = distribution("agentdojo")
        direct = json.loads(package.read_text("direct_url.json") or "{}")
    except (PackageNotFoundError, json.JSONDecodeError):
        print("AgentDojo is missing or its source metadata is unreadable.")
        return 1
    info = direct.get("vcs_info", {})
    commit = info.get("commit_id")
    # Only emit public package metadata; never enumerate environment/API keys.
    report = {
        "python": sys.version.split()[0],
        "agentdojo_distribution_version": package.version,
        "source_commit": commit,
        "expected_commit": EXPECTED_COMMIT,
        "commit_matches": commit == EXPECTED_COMMIT,
    }
    try:
        report["pytest"] = version("pytest")
    except PackageNotFoundError:
        report["pytest"] = None
    print(json.dumps(report, indent=2))
    if commit != EXPECTED_COMMIT:
        print("Install requirements.txt in this environment. Do not use an unpinned PyPI release.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
