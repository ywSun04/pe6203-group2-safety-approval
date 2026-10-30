"""Reconcile curated saved evidence offline. Never runs an experiment or model.

Uses an explicit M6 mapping review, retains raw manifests, and writes all
generated files into a new directory. A missing record is not payment approval.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from decimal import Decimal
import csv
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evaluation import evaluate
from evaluation.reconcile_usage import reconcile_run_usage
from evaluation.reconciliation import FROZEN_COMMIT, PROTOCOL, canonical_profile, json_sha


def sha(data):
    return hashlib.sha256(data).hexdigest()


def check(ok, message):
    if not ok:
        raise ValueError(message)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_csv(path, rows):
    if not rows:
        return
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def select_primary(records):
    """Select by launch identity alone; outcomes cannot influence inclusion."""
    return min(records, key=lambda row: row["run_id"])


def read_evidence(archive, output):
    records = {}
    with zipfile.ZipFile(archive) as source:
        infos = source.infolist()
        names = {i.filename for i in infos}
        check(len(names) == len(infos), "Repeated ZIP member name")
        check(sum(i.file_size for i in infos) <= 120_000_000, "Evidence size limit exceeded")
        check(all(i.file_size <= 5_000_000 for i in infos), "Evidence member size limit exceeded")
        catalog = json.loads(source.read("source-catalog.json"))
        for run_id, entry in catalog["runs"].items():
            check(re.fullmatch(r"\d{8}T\d{6}Z-[a-f0-9]{32}", run_id), "Unexpected run ID")
            data = {}
            directory = output / "raw-run-files" / run_id
            directory.mkdir(parents=True, exist_ok=False)
            for name, expected in entry["files_sha256"].items():
                check(name in {"manifest.json", "tasks.jsonl", "calls.jsonl", "usage.jsonl", "summary.json", "trajectory.jsonl"}, "Unexpected run file")
                member = f"runs/{run_id}/{name}"
                raw = source.read(member)
                check(sha(raw) == expected, f"Evidence hash mismatch: {member}")
                (directory / name).write_bytes(raw)
                data[name] = raw
            check({"manifest.json", "tasks.jsonl", "usage.jsonl", "summary.json", "trajectory.jsonl"} <= data.keys(), "Incomplete run evidence")
            manifest = json.loads(data["manifest.json"].decode("utf-8-sig"))
            check(manifest.get("run_id") == run_id, "Catalog/manifest run ID mismatch")
            rows = lambda name: [json.loads(line) for line in data.get(name, b"").decode("utf-8-sig").splitlines() if line.strip()]
            records[run_id] = {
                "run_id": run_id, "manifest": manifest, "catalog": entry,
                "directory": directory, "manifest_sha256": sha(data["manifest.json"]),
                "calls": rows("calls.jsonl"), "tasks": rows("tasks.jsonl"),
                "usage": rows("usage.jsonl"), "summary": json.loads(data["summary.json"].decode("utf-8-sig")),
            }
    return catalog, records


def aggregate_cost(records):
    result = {}
    for role in ["primary_formal", "retry_formal", "supplemental_formal", "smoke"]:
        selected = [r["accounting"] for r in records if r["role"] == role]
        result[role] = {
            "unique_runs": len(selected),
            "tokens_recorded": {c: sum(r["tokens_recorded"][c] or 0 for r in selected) for c in ["agent", "policy", "reviewer"]},
            "tokens_complete": {c: sum(r["tokens_complete"][c] for r in selected) if all(r["tokens_complete"][c] is not None for r in selected) else None for c in ["agent", "policy", "reviewer"]},
            "runs_with_unresolved_usage": sum(not r["usage_fully_verified"] for r in selected),
            "unknown_usage_requests": sum(r["unknown_usage_requests"] for r in selected),
            "actual_reviews": sum(r["actual_reviews"] for r in selected),
            "requested_reviews": sum(r["requested_reviews"] for r in selected),
            "budget_exhausted_requests": sum(r["budget_exhausted_requests"] for r in selected),
            "provider_cost_recorded": str(sum((Decimal(r["provider_cost_recorded"]) for r in selected), Decimal(0))),
            "provider_cost_complete": all(r["provider_cost_complete"] for r in selected),
        }
    return result


def reconcile(archive, mapping_path, output):
    output = Path(output).resolve()
    check(not output.exists(), "Output directory already exists")
    check(not output.is_relative_to(Path(archive).resolve()), "Output overlaps evidence input")
    mapping = load(mapping_path)
    output.mkdir(parents=True, exist_ok=False)
    catalog, runs = read_evidence(archive, output)
    mapped = {r["run_id"]: r for r in mapping["rows"]}
    check(len(mapped) == len(mapping["rows"]), "Repeated mapping run ID")
    m6_ids = {rid for rid, r in runs.items() if r["catalog"]["owner"] == "Member 6"}
    check(m6_ids == set(mapped), "M6 mapping must cover every supplied M6 UUID exactly once")
    spec = importlib.util.spec_from_file_location("saved_plan", ROOT / "scripts/member5_experiment_plan.py")
    planmod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(planmod)
    plan = planmod.build_plan(ROOT / "configs/member5/experiment-plan.json", ROOT,
                              evidence_kind="formal", integration_commit=FROZEN_COMMIT)
    expected = {(r["task_id"], r["runner_policy"], r["k"], r["repetition"], r["condition"]): r for r in plan["evaluation_plan"]}
    grouped = defaultdict(list)
    common_profile = None
    all_rows = []
    for rid, record in sorted(runs.items()):
        m = record["manifest"]
        s = m["settings"]
        check(type(m.get("repetition")) is int and m["repetition"] in {0, 1, 2}, "Invalid raw repetition type or value")
        owner = record["catalog"]["owner"]
        if owner == "Member 6":
            proposed = mapped[rid]
            check(proposed["source_path"] == record["catalog"]["source_manifest"], "Mapping/source path mismatch")
            check(proposed["source_manifest_sha256"] == record["manifest_sha256"], "Mapping/raw manifest hash mismatch")
            check(proposed["files_sha256"] == record["catalog"]["files_sha256"], "Mapping/companion hash mismatch")
            check((proposed["task_id"], proposed["policy"], proposed["k"], proposed["condition"], proposed["original_repetition"]) == (m["task_id"], s["policy"], s["k"], s["attack"], m["repetition"]), "Mapping/raw identity mismatch")
            rep = proposed["proposed_repetition"]
            evidence = proposed["mapping_evidence_refs"]
            smoke = proposed["source_cohort"] == "live_smoke"
            original_smoke = record["catalog"]["source_manifest"].startswith("logs/member6_live_smoke/")
            check(smoke == original_smoke, "Mapping cannot change the original smoke/formal cohort")
            check(original_smoke or record["catalog"]["source_manifest"].startswith("logs/member6_formal/"), "Unrecognised original M6 cohort")
            needs_ack = proposed["needs_owner_confirmation"]
        else:
            rep = m["repetition"]
            evidence = [record["catalog"]["source_archive"] + "!" + record["catalog"]["source_manifest"]]
            smoke = False
            needs_ack = False
        check(m["config_id"] == json_sha(s)[:20], "Raw configuration ID mismatch")
        record.update(owner=owner, planned_repetition=rep, evidence_refs=evidence, owner_ack_required=needs_ack)
        accounting = reconcile_run_usage(m, record["calls"], record["tasks"], record["usage"], record["summary"])
        check(accounting["accounting_consistent"], f"Accounting discrepancy for {rid}: {accounting['issues']}")
        record["accounting"] = accounting
        if smoke:
            record["role"] = "smoke"
            record["primary_run_id"] = None
        else:
            check(type(rep) is int and rep in {0, 1, 2} and evidence, "Unbound repetition mapping")
            profile = canonical_profile(s)
            if common_profile is None:
                common_profile = profile
            check(profile == common_profile, "Unapproved common-profile difference")
            slot = (m["task_id"], s["policy"], s["k"], rep, s["attack"])
            check(slot in expected, f"Run outside the fixed grid: {slot}")
            target = expected[slot]
            check(s["attack_sha256"] == target["attack_sha256"] and (s["injection_task"] or "none") == target["attack_id"], "Task/attack assignment mismatch")
            record["slot"] = slot
            grouped[slot].append(record)
        all_rows.append(record)
    for slot, attempts in grouped.items():
        primary = select_primary(attempts)
        for r in attempts:
            r["primary_run_id"] = primary["run_id"]
            r["role"] = "primary_formal" if r is primary else "retry_formal" if r["owner"] == primary["owner"] else "supplemental_formal"
    signature = json_sha(common_profile)
    registry = {}
    primary_directories = []
    for slot, row in expected.items():
        row["configuration_signature"] = signature[:16]
        if slot in grouped:
            r = select_primary(grouped[slot]);m = r["manifest"]
            row.update(run_id=r["run_id"], matched=True)
            primary_directories.append(r["directory"])
        keys = ["evidence_kind", "experiment_id", "suite", "suite_version", "model_id", "reviewer_model", "condition", "attack_id", "attack_sha256", "attack_pack_id", "attack_pack_sha256", "repetition"]
        entry = {k: row[k] for k in keys}
        entry["security_scope"] = "benchmark_goal"
        if slot in grouped:
            s = m["settings"]
            entry["reconciliation"] = {
                "protocol": PROTOCOL, "run_id": r["run_id"],
                "raw_manifest_sha256": r["manifest_sha256"],
                "raw_repetition": m["repetition"], "planned_repetition": row["repetition"],
                "raw_profile_sha256": json_sha(planmod.normalized(s)),
                "canonical_profile_sha256": signature,
                "evidence_refs": r["evidence_refs"], "owner_acknowledged": False,
            }
        registry[row["run_id"]] = entry
    result = evaluate(primary_directories, registry=registry, plan=list(expected.values()))
    check(not result["warnings"], "Unexpected evaluator warnings")
    totals = Counter(r["role"] for r in all_rows)
    ledger = []
    for r in all_rows:
        m=r["manifest"];s=m["settings"];a=r["accounting"]
        ledger.append({"run_id":r["run_id"],"owner":r["owner"],"policy":s["policy"],"task_id":m["task_id"],"k":s["k"],"condition":s["attack"],"raw_repetition":m["repetition"],"planned_repetition":r["planned_repetition"],"role":r["role"],"primary_run_id":r["primary_run_id"],"mapping_owner_ack_required":r["owner_ack_required"],"status":a["status"],"error_type":a["error_type"],"task_completed":a["task_completed"],"actual_reviews":a["actual_reviews"],"requested_reviews":a["requested_reviews"],"budget_exhausted_requests":a["budget_exhausted_requests"],"agent_tokens_recorded":a["tokens_recorded"]["agent"],"reviewer_tokens_recorded":a["tokens_recorded"]["reviewer"],"policy_tokens_recorded":a["tokens_recorded"]["policy"],"usage_fully_verified":a["usage_fully_verified"],"unknown_usage_requests":a["unknown_usage_requests"],"provider_cost_recorded":a["provider_cost_recorded"],"provider_cost_complete":a["provider_cost_complete"]})
    missing=[]
    for slot,row in expected.items():
        if slot in grouped:continue
        held=row["runner_policy"]=="budget_aware" and row["condition"]=="none" and row["task_id"]=="user_task_0" and row["k"] in {1,2}
        missing.append({"slot_id":row["slot_id"],"owner":"Member 6" if row["runner_policy"]=="budget_aware" else "Member 2","task_id":row["task_id"],"policy":row["runner_policy"],"k":row["k"],"condition":row["condition"],"planned_repetition":row["repetition"],"status":"hold_prior_M6_review" if held else "not_accounted_in_supplied_evidence","execution_released":False})
    costs=aggregate_cost(all_rows)
    summary={"protocol":PROTOCOL,"execution_freeze":FROZEN_COMMIT,"source_archive_sha256":sha(Path(archive).read_bytes()),"unique_raw_runs":len(runs),"raw_records_by_owner":dict(Counter(r["owner"] for r in all_rows)),"roles":dict(totals),"candidate_accounted_slots":len(grouped),"planned_slots":len(expected),"not_accounted_slots":len(missing),"missing_by_owner":dict(Counter(r["owner"] for r in missing)),"held_missing_slots":sum(r["status"].startswith("hold") for r in missing),"mapping_owner_ack_required_runs":sum(r["owner_ack_required"] for r in all_rows),"common_configuration_signature":signature[:16],"evaluator_warnings":result["warnings"],"accounting_issues":[],"costs_by_role":costs,"new_model_api_calls":0,"execution_released":False,"limitations":["Mapping review is M5 evidence verification; running-owner acknowledgement remains explicit and is not inferred.",f"The {len(missing)}-position remainder describes supplied evidence, not a claim of never-attempted positions or payment approval.","First-launched primary outcomes retain failures. Retry and supplemental expenditure remain separate; never add usage ledger totals twice.","Original security flags are benchmark-goal evidence. Positive strict all-action safety is not inferred.","Candidate Reviewer v3 development must not be pooled into this frozen v2 experiment."]}
    write_json(output/"summary.json",summary)
    write_json(output/"registry.json",registry)
    write_json(output/"evaluation-plan.json",list(expected.values()))
    write_json(output/"accounting-details.json",[r["accounting"] for r in all_rows])
    write_json(output/"evaluation-summary.json",{"groups":result["groups"],"warnings":result["warnings"],"observed_tasks":[r for r in result["tasks"] if r["observed_task_row"]]})
    write_csv(output/"run-ledger.csv",ledger)
    write_csv(output/"missing-slots.csv",missing)
    write_csv(output/"group-metrics.csv",result["groups"])
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence",type=Path,required=True)
    parser.add_argument("--mapping",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    try:
        result=reconcile(args.evidence,args.mapping,args.output)
    except (OSError,ValueError,KeyError,zipfile.BadZipFile) as error:
        parser.exit(2,f"Reconciliation failed: {error}\n")
    print(json.dumps({k:v for k,v in result.items() if k!="costs_by_role"},indent=2))


if __name__=="__main__":
    main()
