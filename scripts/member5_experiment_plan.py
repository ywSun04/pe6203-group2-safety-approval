"""Freeze experiment slots and register saved runs. Standard library; never calls APIs."""
from __future__ import annotations

import argparse
import ast
import hashlib
import itertools
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evaluation import EvaluationError

POLICIES = {"full-approve": "full_approve", "full-escalate": "full_escalate",
            "basic_risk": "basic_risk_v2", "budget_aware": "budget_aware_v1"}


def load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (ValueError, OSError) as e:
        raise EvaluationError(f"Cannot read {path}: {e}") from e


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def normalized(settings):
    return {k: v for k, v in settings.items()
            if k not in {"policy", "k", "attack", "attack_sha256", "injection_task"}}


def _unique(values, label):
    if not isinstance(values, list) or not values or len(set(values)) != len(values):
        raise EvaluationError(f"{label} must be a nonempty list of distinct values")


def _positive(value, label, zero=False):
    if type(value) is not int or value < (0 if zero else 1):
        raise EvaluationError(f"{label} must be a {'nonnegative' if zero else 'positive'} integer")


def _commit(repo_root):
    result = subprocess.run(["git", "-C", str(repo_root), "rev-parse", "HEAD"], capture_output=True, text=True)
    if result.returncode:
        raise EvaluationError("Cannot determine integration commit; pass --integration-commit")
    return result.stdout.strip()


def build_plan(config_path, repo_root=ROOT, log_roots=(), evidence_kind="unclassified",
               integration_commit=None, experiment_id="member5-workspace-fixed-v1"):
    """Return immutable slots, runner commands and an evidence registry.

    Observed UUIDs replace reserved IDs only after exact slot and configuration
    checks. The first observed full settings profile becomes the common runtime
    signature; all other observed profiles must match it exactly.
    """
    repo_root = Path(repo_root).resolve()
    config_path = Path(config_path).resolve()
    config = load(config_path)
    if not isinstance(config, dict):
        raise EvaluationError("Experiment plan must be an object")
    for field in ("task_ids", "policies", "k", "conditions"):
        _unique(config.get(field), field)
    if set(config["policies"]) - POLICIES.keys():
        raise EvaluationError("Experiment plan contains an unsupported policy")
    if set(config["conditions"]) - {"none", "file"}:
        raise EvaluationError("Conditions must be none or file")
    for k in config["k"]:
        _positive(k, "k", zero=True)
    _positive(config.get("repeat"), "repeat")
    if evidence_kind not in {"unclassified", "demo", "smoke", "formal"} or not experiment_id:
        raise EvaluationError("Evidence kind and experiment ID must be explicit valid values")
    integration_commit = integration_commit or _commit(repo_root)
    if re.fullmatch(r"[a-fA-F0-9]{40}", integration_commit) is None:
        raise EvaluationError("Integration commit must be a full 40-character SHA")
    integration_commit = integration_commit.lower()
    manifest_path = repo_root / config["attack_manifest"]
    attack_manifest = load(manifest_path)
    for key in ("suite", "suite_version", "agentdojo_commit"):
        if attack_manifest.get(key) != config.get(key):
            raise EvaluationError(f"Attack manifest / experiment plan mismatch: {key}")
    cases = {}
    for case in attack_manifest.get("cases", []):
        task_id = case.get("task_id")
        if task_id in cases:
            raise EvaluationError(f"Multiple attack cases for {task_id}")
        path = repo_root / case["attack_file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != case.get("attack_file_sha256"):
            raise EvaluationError(f"Attack file hash mismatch: {path}")
        payload = load(path)
        if not isinstance(payload, dict) or not payload or any(not isinstance(k, str) or not isinstance(v, str) for k, v in payload.items()):
            raise EvaluationError(f"Invalid attack payload map: {path}")
        cases[task_id] = {**case, "runner_attack_sha256": sha(payload)}
    if set(config["task_ids"]) != set(cases):
        raise EvaluationError("Attack cases must cover the exact planned task set")
    pack_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    pack_id = "member5-fixed20-" + pack_hash[:12]
    count = len(config["task_ids"])*len(config["policies"])*len(config["k"])*config["repeat"]*len(config["conditions"])
    if "planned_total_runs" in config and config["planned_total_runs"] != count:
        raise EvaluationError("planned_total_runs disagrees with experiment grid")
    profile = {
        "suite": config["suite"], "suite_version": config["suite_version"],
        "model_id": config["model_id"], "reviewer_model": config["reviewer_model"],
        "agent_base_url": config.get("agent_base_url", "https://openrouter.ai/api/v1"),
        "reviewer_base_url": config.get("reviewer_base_url", "https://openrouter.ai/api/v1"),
        "reviewer_timeout_seconds": config.get("reviewer_timeout_seconds", 30),
        "connect_timeout_seconds": config.get("connect_timeout_seconds", 2),
        "max_agent_requests": config.get("max_agent_requests", 20),
        "max_output_tokens": config.get("max_output_tokens", 2048), "temperature": 0.0,
    }
    for field in ("max_agent_requests", "max_output_tokens"):
        _positive(profile[field], field)
    for field in ("reviewer_timeout_seconds", "connect_timeout_seconds"):
        if type(profile[field]) not in (int, float) or profile[field] <= 0:
            raise EvaluationError(f"{field} must be positive")
    # Parse a literal source constant, without importing Reviewer or model SDKs.
    reviewer_source = repo_root / "reviewer/llm_reviewer.py"
    if reviewer_source.exists():
        syntax = ast.parse(reviewer_source.read_text(encoding="utf-8"))
        for node in syntax.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "REVIEWER_PROMPT" for t in node.targets):
                profile["reviewer_prompt_sha256"] = hashlib.sha256(ast.literal_eval(node.value).encode()).hexdigest()
                break
    expected = {}
    for condition, task, policy, k, repetition in itertools.product(config["conditions"], config["task_ids"], config["policies"], config["k"], range(config["repeat"])):
        slot = (task, policy, k, repetition, condition)
        reserved = "planned-" + hashlib.sha256(json.dumps([experiment_id, *slot], separators=(",", ":")).encode()).hexdigest()[:24]
        expected[slot] = {"slot_id": reserved, "run_id": reserved, "task_id": task,
            "policy_name": POLICIES[policy], "runner_policy": policy, "k": k,
            "repetition": repetition, "condition": condition, "matched": False}
    observed = {}
    uuid_sources = {}
    full_profile = None
    log_dirs = set()
    for root in log_roots:
        root = Path(root).resolve()
        if not root.is_dir():
            raise EvaluationError(f"Log root does not exist: {root}")
        log_dirs.update(path.parent for path in root.rglob("manifest.json"))
        if (root / "manifest.json").exists():
            log_dirs.add(root)
        # A runner run must have a manifest; loose task rows cannot be registered.
        if any(not (path.parent / "manifest.json").exists() for path in root.rglob("tasks.jsonl")):
            raise EvaluationError(f"Task logs without manifests under {root}")
    for directory in sorted(log_dirs):
        manifest = load(directory / "manifest.json")
        run_id = manifest.get("run_id")
        if not isinstance(run_id, str) or not run_id or run_id.startswith("planned-"):
            raise EvaluationError(f"Invalid actual run ID in {directory}")
        if run_id in uuid_sources:
            raise EvaluationError(f"Repeated run_id {run_id}: {uuid_sources[run_id]} and {directory}")
        uuid_sources[run_id] = directory
        settings = manifest.get("settings")
        if not isinstance(settings, dict):
            raise EvaluationError(f"Missing settings in {directory}")
        _positive(settings.get("k"), f"Observed k in {directory}", zero=True)
        _positive(manifest.get("repetition"), f"Observed repetition in {directory}", zero=True)
        slot = (manifest.get("task_id"), settings.get("policy"), settings.get("k"), manifest.get("repetition"), settings.get("attack"))
        if slot not in expected:
            raise EvaluationError(f"Run is outside the frozen grid: {slot} in {directory}")
        if slot in observed:
            raise EvaluationError(f"Duplicate planned slot {slot}: {observed[slot]['run_id']} and {run_id}")
        for key, value in profile.items():
            if settings.get(key) != value:
                raise EvaluationError(f"Frozen setting mismatch {key} in {directory}")
        versions = settings.get("source_versions", {})
        if versions.get("integration_commit") != integration_commit:
            raise EvaluationError(f"Integration commit mismatch in {directory}")
        if versions.get("agentdojo_commit") != config["agentdojo_commit"]:
            raise EvaluationError(f"AgentDojo commit mismatch in {directory}")
        condition, case = slot[4], cases[slot[0]]
        target = case["injection_task_id"] if condition == "file" else None
        payload_hash = case["runner_attack_sha256"] if condition == "file" else sha({})
        if settings.get("injection_task") != target or settings.get("attack_sha256") != payload_hash:
            raise EvaluationError(f"Task/attack assignment mismatch in {directory}")
        current_profile = normalized(settings)
        if full_profile is None:
            full_profile = current_profile
        elif full_profile != current_profile:
            raise EvaluationError(f"Different runtime/source configuration in {directory}; use a separate experiment")
        observed[slot] = {"run_id": run_id, "directory": str(directory), "config_id": manifest.get("config_id")}
    # With no actual manifests the full package/runtime hash is unknowable.
    # The provisional hash is not reused once actual evidence supplies a profile.
    common_signature = sha(full_profile)[:16] if full_profile is not None else sha({"expected_profile": profile, "integration_commit": integration_commit, "agentdojo_commit": config["agentdojo_commit"]})[:16]
    slots, registry = [], {}
    for slot, base in expected.items():
        task, policy, k, repetition, condition = slot
        case = cases[task]
        row = {**base, **observed.get(slot, {}), "matched": slot in observed,
            "evidence_kind": evidence_kind, "experiment_id": experiment_id,
            "suite": config["suite"], "suite_version": config["suite_version"],
            "model_id": config["model_id"], "reviewer_model": config["reviewer_model"],
            "configuration_signature": common_signature,
            "attack_id": case["injection_task_id"] if condition == "file" else "none",
            "attack_sample_id": case["attack_id"] if condition == "file" else "none",
            "attack_sha256": case["runner_attack_sha256"] if condition == "file" else sha({}),
            "attack_pack_id": pack_id if condition == "file" else None,
            "attack_pack_sha256": pack_hash if condition == "file" else None}
        slots.append(row)
        registry[row["run_id"]] = {key: row[key] for key in ("evidence_kind", "experiment_id", "suite", "suite_version", "model_id", "reviewer_model", "condition", "attack_id", "attack_sha256", "attack_pack_id", "attack_pack_sha256", "repetition")}
        registry[row["run_id"]]["security_scope"] = "benchmark_goal"
    commands = []
    for condition, task in itertools.product(config["conditions"], config["task_ids"]):
        case = cases[task]
        args = ["python", "experiments/run_suite.py", "--suite", config["suite"], "--suite-version", config["suite_version"],
            "--tasks", task, "--model-id", config["model_id"], "--policies", *config["policies"], "--k", *map(str, config["k"]),
            "--repeat", str(config["repeat"]), "--reviewer-timeout", str(profile["reviewer_timeout_seconds"]),
            "--connect-timeout", str(profile["connect_timeout_seconds"]), "--max-agent-requests", str(profile["max_agent_requests"]),
            "--max-output-tokens", str(profile["max_output_tokens"]), "--attack", condition,
            "--log-dir", f"logs/member5-formal/{condition}/{task}"]
        if condition == "file":
            args += ["--attack-file", case["attack_file"], "--injection-task", case["injection_task_id"]]
        commands.append({"task_id": task, "condition": condition, "argv": args,
                         "requires_explicit_live_flag": True, "planned_runs": len(config["policies"])*len(config["k"])*config["repeat"]})
    coverage = {"schema_version": 1, "experiment_id": experiment_id, "evidence_kind": evidence_kind,
        "planned_runs": count, "matched_runs": len(observed), "missing_runs": count-len(observed),
        "runner_command_groups": len(commands), "integration_commit": integration_commit,
        "agentdojo_commit": config["agentdojo_commit"], "attack_pack_id": pack_id, "attack_pack_sha256": pack_hash,
        "configuration_signature": common_signature,
        "configuration_signature_provisional": full_profile is None,
        "frozen_expected_profile": profile, "observed_full_profile": full_profile,
        "api_calls_made": 0, "source_plan_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "note": "Unmatched slots retain the denominator. Registration does not establish attack delivery or action authorization."}
    return {"evaluation_plan": slots, "registry": registry, "commands": commands, "coverage": coverage}


def write_plan(result, output):
    """Refuse an existing output directory; preserve prior registrations."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    for key, name in (("evaluation_plan", "evaluation-plan.json"), ("registry", "registry.json"), ("commands", "runner-commands.json"), ("coverage", "coverage.json")):
        (output / name).write_text(json.dumps(result[key], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["Member 5 experiment runner command groups", "", "These commands are offline preflight only. None contains --live; this script never executes them.",
        "Set provider keys locally. The frozen Reviewer model/endpoints and source commit are in coverage.json.",
        "After team approval and model budget confirmation, Member 2 may explicitly add --live to selected commands.", ""]
    for command in result["commands"]:
        lines.extend([f"{command['condition']} / {command['task_id']} ({command['planned_runs']} runs)", shlex.join(command["argv"]), ""])
    (output / "runner-commands.txt").write_text("\n".join(lines), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/member5/experiment-plan.json")
    parser.add_argument("--logs", nargs="*", type=Path, default=[])
    parser.add_argument("--evidence-kind", choices=["unclassified", "demo", "smoke", "formal"], default="unclassified")
    parser.add_argument("--experiment-id", default="member5-workspace-fixed-v1")
    parser.add_argument("--integration-commit")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = build_plan(args.config, ROOT, args.logs, args.evidence_kind, args.integration_commit, args.experiment_id)
        write_plan(result, args.output)
    except (EvaluationError, OSError, ValueError, KeyError) as e:
        parser.exit(2, f"Plan registration failed: {e}\n")
    print(json.dumps({k: result["coverage"][k] for k in ("planned_runs", "matched_runs", "missing_runs", "runner_command_groups", "api_calls_made")}))
    print(args.output / "evaluation-plan.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
