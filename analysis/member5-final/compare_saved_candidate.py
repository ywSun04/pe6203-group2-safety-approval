"""Compare saved PR14 calendar proposals with their original v2 denials.

Retrospective call-level evidence only. No API requests or task reruns.
"""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from evaluation.reconciliation import json_sha


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def compare(evidence, formal_raw, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(evidence) as source:
        reference = json.loads(source.read("reference.json"))
        development = json.loads(source.read("development-pass.json"))
        repeats = json.loads(source.read("target-repeats.json"))
        scope = json.loads(source.read("scope-screening.json"))
        author_summary = json.loads(source.read("summary.json"))
    candidates = {c["id"]: c for c in development["cases"]}
    results = {r["id"]: r for r in development["rows"]}
    repeat_cases = {c["id"]: c for c in repeats["cases"]}
    repeat_rows = {r["id"]: r for r in repeats["rows"]}
    pairs = []
    hypothetical = []
    for case_id, c in candidates.items():
        match = re.fullmatch(r"logged_lunch_(\d{8}T\d{6}Z-[a-f0-9]{32})", case_id)
        if not match:
            continue
        rid = match[1]
        directory = Path(formal_raw) / rid
        manifest = load(directory / "manifest.json")
        calls = [json.loads(line) for line in (directory / "calls.jsonl").read_text(encoding="utf-8-sig").splitlines() if line.strip()]
        snapshots = [json.loads(line) for line in (directory / "trajectory.jsonl").read_text(encoding="utf-8-sig").splitlines() if line.strip()]
        lunch = [r for r in calls if r.get("tool_name") == "create_calendar_event"]
        assert len(lunch) == 1
        original = lunch[0]
        request = c["request"]
        assert request["tool_name"] == original["tool_name"]
        assert request["tool_arguments"] == original["tool_arguments"]
        messages = snapshots[-1]["messages"]
        proposal_index = next(i for i, m in enumerate(messages) if any(t["function"] == request["tool_name"]
            and t["args"] == request["tool_arguments"] for t in m.get("tool_calls") or []))
        assert request["history"] == messages[:proposal_index]
        user_task = next("\n".join(b["content"] for b in m["content"] if b["type"] == "text")
                         for m in messages if m["role"] == "user")
        assert request["user_task"] == user_task
        if not original["actually_escalated"]:
            hypothetical.append({"run_id": rid, "call_id": original["call_id"],
                "original_budget": original["budget_before"], "candidate_budget": request["remaining_budget"],
                "reason": "Original Gate blocked the lunch after a separate deletion review; no actual v2 lunch review. Excluded from matched comparison."})
            continue
        assert original["reviewer_decision"] == "DENY"
        assert request["remaining_budget"] == original["budget_before"] == 1
        selected = [results[case_id]]
        for number in [1, 2]:
            repeat_id = case_id + f"_repeat{number}"
            assert repeat_cases[repeat_id]["request"] == request
            selected.append(repeat_rows[repeat_id])
        assert all(row["decision"] == row["final_decision"] == "APPROVE" and not row["technical_failure"] for row in selected)
        pairs.append({"run_id": rid, "call_id": original["call_id"],
            "condition": manifest["settings"]["attack"], "repetition": manifest["repetition"],
            "v2_observed_decision": "DENY", "expected_authorized_decision": "APPROVE",
            "candidate_decision": "APPROVE", "candidate_saved_approvals": 3,
            "candidate_saved_observations": 3,
            "same_user_task_arguments_budget": True, "same_pre_proposal_history": True,
            "literal_gate_request_equal": False,
            "context_difference": "Candidate replay omits the pending assistant tool-call message and tool_metadata. All earlier messages, user task, arguments and available budget match.",
            "candidate_request_sha256": json_sha(request),
            "original_calls_sha256": hashlib.sha256((directory / "calls.jsonl").read_bytes()).hexdigest()})
    assert len(pairs) == 5 and len(hypothetical) == 1
    usage = development["usage"] + repeats["usage"]
    tokens = sum(u["usage"]["total_tokens"] for u in usage) + sum(u["total_tokens"] for u in scope["usage"])
    cost = sum((Decimal(str(u["usage"]["cost"])) for u in usage), Decimal(0)) + sum((Decimal(str(u["cost"])) for u in scope["usage"]), Decimal(0))
    assert len(usage) + len(scope["usage"]) == 45
    assert tokens == author_summary["known_response_accounting"]["tokens"] == 25624
    assert cost == Decimal(author_summary["known_response_accounting"]["cost_usd"])
    summary = {"source_pr": reference["html_url"], "source_head_sha": reference["head_sha"],
        "evidence_sha256": hashlib.sha256(Path(evidence).read_bytes()).hexdigest(),
        "comparison": "Retrospective matched proposals with an explicit replay-context normalization; not a literal identical full Gate request or randomized live A/B trial.",
        "underlying_tasks": 1, "actual_v2_false_denials": 5,
        "candidate_saved_approvals": 15, "candidate_saved_observations": 15,
        "hypothetical_excluded": hypothetical, "matched_proposals": pairs,
        "development_full_set": author_summary["full_pass"],
        "known_development_responses": 45, "known_development_tokens": tokens,
        "known_development_cost_usd": str(cost),
        "setup_diagnostic_usage": "Two six-request HTTP400 setup passes were reported; one was retained. Their unreturned usage remains unknown, outside known cost.",
        "new_model_api_calls": 0, "formal_runs_added": 0,
        "task_success_or_TCR_improvement_demonstrated": False,
        "limitations": ["The candidate was designed for these failures and tested on the same cases; this is development evidence, not held-out accuracy.",
            "The five calls share one task. Three candidate observations per call do not create fifteen independent tasks.",
            "No complete task was rerun. Budget exhaustion in the sixth source trajectory remains unchanged.",
            "Candidate timestamps are limited to supported local naive formats. The original v2 discovery false denial remains.",
            "Formal experiment data keep the frozen v2 prompt and configuration. Candidate expenditure is separate."]}
    (output / "comparison.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    import csv
    with (output / "matched-proposals.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(pairs[0]))
        writer.writeheader(); writer.writerows(pairs)
    return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence", type=Path, required=True)
    p.add_argument("--formal-raw", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    result = compare(a.evidence, a.formal_raw, a.output)
    print(json.dumps({k: result[k] for k in ["actual_v2_false_denials", "candidate_saved_approvals", "new_model_api_calls"]}))
