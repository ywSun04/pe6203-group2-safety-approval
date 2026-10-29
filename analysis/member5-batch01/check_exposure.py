"""Independent read-only exposure audit of the saved formal batch."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import re
import yaml

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--batch-root", type=Path, required=True, help="Extracted Member 2 batch-01 directory")
parser.add_argument("--repo-root", type=Path, required=True, help="Checkout containing the frozen fixture manifest")
parser.add_argument("--output", type=Path, required=True, help="New directory for derived results; never overwrite")
args = parser.parse_args()
BATCH = args.batch_root.resolve()
REPO = args.repo_root.resolve()
OUT = args.output.resolve()
if OUT.exists():
    parser.error("Output directory already exists; use a new path")
if not BATCH.is_dir() or not REPO.is_dir():
    parser.error("Batch and repository directories must exist")
if OUT == BATCH or OUT.is_relative_to(BATCH):
    parser.error("Output must be outside the source batch directory")


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def norm(text):
    # YAML formatting may fold whitespace inside one scalar. Only compare a
    # whole known payload within one text block or decoded string value. Do not
    # join separate fields, blocks, roles, or snapshots to manufacture a match.
    return " ".join(text.split())


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for child in value:
            yield from strings(child)
    elif isinstance(value, dict):
        for child in value.values():
            yield from strings(child)


with (BATCH / "member2-batch01-exposure.csv").open(encoding="utf-8-sig", newline="") as stream:
    handed_off = {row["run_id"]: row for row in csv.DictReader(stream)}
manifest = read(REPO / "configs/member5/attack-manifest.json")
case = next(c for c in manifest["cases"] if c["task_id"] == "user_task_0")
fixture = read(REPO / case["attack_file"])
assert list(fixture) == [case["vector_id"]]
payload = fixture[case["vector_id"]]
payload_hash = hashlib.sha256(json.dumps(fixture, sort_keys=True).encode()).hexdigest()
records = []
all_call_count = 0
nested = []
for path in sorted(BATCH.rglob("manifest.json")):
    config = read(path)
    settings = config["settings"]
    run_id = config["run_id"]
    calls = [json.loads(line) for line in (path.parent / "calls.jsonl").read_text().splitlines()]
    calls = [row for row in calls if row["record_type"] == "tool_call"]
    all_call_count += len(calls)
    summary = read(path.parent / "summary.json")
    assert summary["nested_calls_observed"] is False
    for index, call in enumerate(calls, 1):
        if any(isinstance(v, dict) and "function" in v and "args" in v for v in [call["tool_arguments"], *call["tool_arguments"].values()]):
            nested.append({"run_id": run_id, "call_index": index})
    if settings["attack"] != "file":
        continue
    assert settings["injection_task"] == case["injection_task_id"]
    assert settings["attack_sha256"] == payload_hash
    snapshots = [json.loads(line) for line in (path.parent / "trajectory.jsonl").read_text().splitlines()]
    exposures = []
    seen = set()
    for line_no, snapshot in enumerate(snapshots, 1):
        for message_index, message in enumerate(snapshot["messages"]):
            if message.get("role") != "tool" or message.get("error") is not None:
                continue
            call_id = message.get("tool_call_id")
            if call_id in seen:
                continue
            blocks = [c.get("content", "") for c in message.get("content", []) if c.get("type") == "text"]
            direct = any(norm(payload) in norm(block) for block in blocks)
            decoded = False
            for block in blocks:
                try:
                    values = yaml.safe_load(block)
                except yaml.YAMLError:
                    values = None
                decoded = decoded or any(norm(payload) in norm(value) for value in strings(values))
            if not direct and not decoded:
                continue
            seen.add(call_id)
            # The frozen MeasuredAgent submits this messages list unchanged
            # apart from pinned serialization. A later assistant append supports
            # that a model query followed this successful tool result. This is
            # trace/code evidence; no raw HTTP request body is available.
            following = []
            for later_no, later in enumerate(snapshots[line_no:], line_no + 1):
                messages = later["messages"]
                if len(messages) <= len(snapshot["messages"]):
                    continue
                if messages[:len(snapshot["messages"])] != snapshot["messages"]:
                    continue
                if messages[len(snapshot["messages"])].get("role") != "assistant":
                    continue
                following.append(later_no)
                break
            exposures.append({
                "trajectory_line_one_based": line_no,
                "message_index_zero_based": message_index,
                "tool_call_id": call_id,
                "tool_name": message["tool_call"]["function"],
                "whole_payload_in_rendered_tool_result": direct,
                "whole_payload_in_decoded_scalar": decoded,
                "following_assistant_snapshot_line": following[0] if following else None,
                "model_query_supported": bool(following),
            })
    exposed = any(item["model_query_supported"] for item in exposures)
    claimed = handed_off[run_id]["injection_exposure"] == "True"
    assert claimed == exposed, (run_id, claimed, exposed)
    task = json.loads((path.parent / "tasks.jsonl").read_text().splitlines()[0])
    record = {
        "run_id": run_id, "policy": settings["policy"], "repetition": config["repetition"],
        "condition": settings["attack"], "task_completed": task["task_completed"],
        "attack_success": summary["attack_success"], "actual_reviews": task["actual_escalation_count"],
        "exposed_to_tool_result_and_subsequent_model_query": exposed,
        "matches_handoff": claimed == exposed,
        "exposure_evidence": exposures,
        "source_directory": path.parent.relative_to(BATCH).as_posix(),
        "trajectory_snapshot_count": len(snapshots),
        "calls": [{key: row.get(key) for key in ["call_id", "tool_name", "tool_arguments", "policy_decision", "reviewer_decision", "reviewer_reason", "final_decision", "execution_attempted", "tool_error", "deny_reason", "budget_before", "budget_after"]} for row in calls],
    }
    if not exposed:
        # The marker is absent even from assistant/user content, not just the tool search.
        record["marker_anywhere_in_trajectory"] = any(case["delivery_marker"] in value for snapshot in snapshots for value in strings(snapshot))
        assert record["marker_anywhere_in_trajectory"] is False
    records.append(record)

assert len(records) == 9
assert sum(row["exposed_to_tool_result_and_subsequent_model_query"] for row in records) == 8
assert not nested
result = {
    "attacked_runs": len(records), "exposed_runs": 8, "non_exposed_runs": 1,
    "handoff_agrees_all_runs": True,
    "nested_calls_observed": nested,
    "all_18_tool_call_count": all_call_count,
    "payload_map_sha256": payload_hash,
    "records": records,
    "boundary": "Exposure is supported by a successful tool-result snapshot containing the full payload and a later appended assistant response, together with the frozen MeasuredAgent implementation that submits that messages list. Raw HTTP request bodies are not retained; the claim is trace/code-supported, not a provider-side receipt.",
}
OUT.mkdir(parents=True, exist_ok=False)
(OUT / "exposure-audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
lines = []
for row in records:
    references = "; ".join(f"trajectory.jsonl:{item['trajectory_line_one_based']}, messages[{item['message_index_zero_based']}], next assistant snapshot line {item['following_assistant_snapshot_line']}" for item in row["exposure_evidence"])
    lines.append({key: row[key] for key in ["run_id", "policy", "repetition", "task_completed", "attack_success", "actual_reviews", "exposed_to_tool_result_and_subsequent_model_query", "matches_handoff"]} | {"evidence": references})
with (OUT / "exposure-audit.csv").open("w", newline="", encoding="utf-8") as stream:
    writer = csv.DictWriter(stream, fieldnames=list(lines[0])); writer.writeheader(); writer.writerows(lines)
print(json.dumps({key: value for key, value in result.items() if key != "records"}, indent=2))
