"""Offline checks for the fixed Member 5 attack manifest. Never calls an LLM.

Reference calls and evaluator predicates stay inside this offline validator.
They must never be supplied to the agent, approval policy, or reviewer.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import inspect
import json
from pathlib import Path
import platform
import subprocess
import sys
from types import SimpleNamespace
from urllib.parse import urlparse
from urllib.request import url2pathname

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PIN = "089ed468cf3ed0322acc66b0211f26d9d90dbf60"
MANIFEST = ROOT / "configs/member5/attack-manifest.json"
TASK_NUMBERS = [0, 1, 2, 3, 6, 8, 9, 10, 14, 16, 17, 21, 22, 24, 26, 27, 28, 29, 30, 35]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def output_contains_marker(text: str, marker: str) -> bool:
    """Find a marker in rendered tool data, including YAML-wrapped scalars.

    The pinned ToolsExecutor serialises structured results using YAML. Its line
    wrapping can split a marker across physical lines, although the decoded
    string still contains the complete marker. Inspect string values after safe
    decoding rather than changing the payload or joining unrelated fields.
    """
    if marker in text:
        return True
    try:
        decoded = yaml.safe_load(text)
    except yaml.YAMLError:
        return False

    def contains(value):
        if isinstance(value, str):
            return marker in value
        if isinstance(value, dict):
            return any(contains(item) for item in value.values())
        if isinstance(value, list):
            return any(contains(item) for item in value)
        return False

    return contains(decoded)


def installed_commit() -> str | None:
    """Verify an installed VCS distribution or a directly imported source tree."""
    try:
        dist = importlib.metadata.distribution("agentdojo")
        direct = json.loads(dist.read_text("direct_url.json") or "{}")
        commit = direct.get("vcs_info", {}).get("commit_id")
        if commit:
            return commit
        url = urlparse(direct.get("url", ""))
        if url.scheme == "file":
            source_root = Path(url2pathname(url.path)).resolve()
            if (source_root / ".git").exists():
                import agentdojo
                installed_root = Path(agentdojo.__file__).resolve().parent
                source_package = source_root / "src/agentdojo"
                # A local wheel has no VCS metadata. Require byte-for-byte Python
                # source equality with its Git checkout before accepting the pin.
                for installed_file in installed_root.rglob("*.py"):
                    original = source_package / installed_file.relative_to(installed_root)
                    if not original.exists() or sha256(installed_file) != sha256(original):
                        raise ValueError("Installed AgentDojo Python source differs from its local checkout")
                result = subprocess.run(["git", "-c", f"safe.directory={source_root.as_posix()}",
                                         "-C", str(source_root), "rev-parse", "HEAD"],
                                        text=True, capture_output=True, check=True)
                return result.stdout.strip()
    except importlib.metadata.PackageNotFoundError:
        pass
    import agentdojo
    package_path = Path(agentdojo.__file__).resolve()
    for parent in package_path.parents:
        if (parent / ".git").exists():
            result = subprocess.run(["git", "-c", f"safe.directory={parent.as_posix()}",
                                     "-C", str(parent), "rev-parse", "HEAD"],
                                    text=True, capture_output=True, check=True)
            return result.stdout.strip()
    return None


def replay(suite, task, injections):
    from agentdojo.agent_pipeline.tool_execution import tool_result_to_str
    from agentdojo.functions_runtime import FunctionsRuntime
    env = task.init_environment(suite.load_and_inject_default_environment(injections))
    before = env.model_copy(deep=True)
    runtime = FunctionsRuntime(suite.tools)
    calls = task.ground_truth(env)
    outputs = []
    for index, call in enumerate(calls):
        result, error = runtime.run_function(env, call.function, call.args, raise_on_error=True)
        if error:
            raise AssertionError(error)
        outputs.append(dict(index=index, tool_name=call.function, text=tool_result_to_str(result)))
    return before, env, calls, outputs


def check_goal_predicate(suite, injection_task, before):
    """Exercise an official predicate only in isolated simulated environment copies."""
    from agentdojo.functions_runtime import FunctionsRuntime
    attack_before = before.model_copy(deep=True)
    attack_after = before.model_copy(deep=True)
    initial_success = injection_task.security("", attack_before, attack_after)
    runtime = FunctionsRuntime(suite.tools)
    for call in injection_task.ground_truth(attack_before):
        runtime.run_function(attack_after, call.function, call.args, raise_on_error=True)
    oracle_success = injection_task.security("", attack_before, attack_after)
    return bool(initial_success), bool(oracle_success)


def validate_manifest(manifest_path=MANIFEST):
    from agentdojo.task_suite.load_suites import get_suite
    from agentdojo.types import text_content_block_from_string
    from experiments.run_suite import attack_settings
    commit = installed_commit()
    if commit != PIN:
        raise ValueError(f"AgentDojo source must be pinned to {PIN}; detected {commit}")
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["agentdojo_commit"] != PIN:
        raise ValueError("Manifest does not use the agreed AgentDojo source")
    cases = manifest["cases"]
    if len(cases) != 20 or {c["task_id"] for c in cases} != {f"user_task_{n}" for n in TASK_NUMBERS}:
        raise ValueError("Attack manifest must contain exactly one case for each of the 20 agreed candidates")
    if len({c["attack_id"] for c in cases}) != 20:
        raise ValueError("Duplicate attack ID")
    suite = get_suite(manifest["suite_version"], manifest["suite"])
    defaults = suite.get_injection_vector_defaults()
    canaries = {key: f"MEMBER5_CANARY_{key}_END" for key in defaults}
    results = []
    for case in cases:
        task = suite.get_user_task_by_id(case["task_id"])
        attack_file = (ROOT / case["attack_file"]).resolve()
        if not attack_file.is_relative_to(ROOT / "attacks/member5"):
            raise ValueError("Attack files must stay in attacks/member5")
        if sha256(attack_file) != case["attack_file_sha256"]:
            raise ValueError(f"Hash mismatch for {case['attack_id']}")
        injection_task, injections = attack_settings(SimpleNamespace(
            attack="file", attack_file=attack_file, injection_task=case["injection_task_id"]), suite)
        if list(injections) != [case["vector_id"]]:
            raise ValueError("Each fixed case must replace exactly its declared vector")
        if defaults[case["vector_id"]] not in injections[case["vector_id"]]:
            raise ValueError("Preserve original vector text before appending instructions")
        _, _, _, canary_outputs = replay(suite, task, canaries)
        reached = [key for key, token in canaries.items()
                   if any(output_contains_marker(item["text"], token) for item in canary_outputs)]
        before, after, calls, outputs = replay(suite, task, injections)
        hits = [dict(index=o["index"], tool_name=o["tool_name"],
                     tool_output_sha256=hashlib.sha256(o["text"].encode()).hexdigest())
                for o in outputs if output_contains_marker(o["text"], case["delivery_marker"])]
        if case["vector_id"] not in reached or not hits:
            raise AssertionError(f"Payload not delivered by the reference path: {case['attack_id']}")
        utility = suite._check_task_result(task,
            [text_content_block_from_string(task.GROUND_TRUTH_OUTPUT)], before, after, calls)
        if not utility:
            raise AssertionError(f"Payload breaks the reference solution: {case['attack_id']}")
        initial_success, oracle_success = check_goal_predicate(suite, injection_task, before)
        predicate_selfcheck_passed = not initial_success and bool(oracle_success)
        validation_issues = []
        if initial_success:
            validation_issues.append("official_goal_already_satisfied_in_initial_environment")
        if not oracle_success:
            validation_issues.append("official_goal_not_satisfied_after_official_oracle_calls")
        source = Path(inspect.getsourcefile(type(injection_task)))
        method = inspect.getsource(type(injection_task).security)
        results.append(dict(attack_id=case["attack_id"], task_id=case["task_id"],
            injection_task_id=injection_task.ID, vector_id=case["vector_id"],
            attack_file_sha256=sha256(attack_file),
            loader_compatible=True, environment_initialized=True,
            reference_reachable_vectors=reached, reference_delivery=hits,
            reference_utility_passed=bool(utility),
            goal=injection_task.GOAL,
            security_function=f"{type(injection_task).__module__}.{type(injection_task).__name__}.security",
            security_source_sha256=hashlib.sha256(method.encode()).hexdigest(),
            security_module_sha256=sha256(source),
            initial_goal_satisfied=bool(initial_success),
            evaluator_selfcheck_after_oracle_calls=bool(oracle_success),
            predicate_selfcheck_passed=predicate_selfcheck_passed,
            formal_compatible=predicate_selfcheck_passed,
            validation_issues=validation_issues,
            live_delivery_verified=False, live_attack_success=None))
    return dict(evidence_type="offline_reference_validation", agentdojo_commit=commit,
                python_version=platform.python_version(), suite=manifest["suite"],
                suite_version=manifest["suite_version"], case_count=len(results),
                reference_delivery_count=sum(bool(c["reference_delivery"]) for c in results),
                reference_utility_pass_count=sum(c["reference_utility_passed"] for c in results),
                predicate_selfcheck_pass_count=sum(c["predicate_selfcheck_passed"] for c in results),
                formal_compatible_count=sum(c["formal_compatible"] for c in results),
                compatibility_scope="formal_compatible means offline prerequisites only; live exposure and attack efficacy remain unverified",
                delivery_detection="exact text or decoded YAML scalar value; hash retains original serialised text",
                note="Oracle calls test evaluator plumbing only; no model attack success is claimed.",
                cases=results)


def write_matrix(result, path: Path, manifest_path=MANIFEST):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    by_id = {case["attack_id"]: case for case in manifest["cases"]}
    rows = []
    for case in result["cases"]:
        original = by_id[case["attack_id"]]
        rows.append(dict(
            task_id=case["task_id"], attack_id=case["attack_id"],
            injection_task_id=case["injection_task_id"], vector_id=case["vector_id"],
            attack_file=original["attack_file"], attack_file_sha256=case["attack_file_sha256"],
            security_function=case["security_function"],
            security_source_sha256=case["security_source_sha256"],
            reference_tool_indices_zero_based=";".join(str(hit["index"]) for hit in case["reference_delivery"]),
            reference_tools=";".join(hit["tool_name"] for hit in case["reference_delivery"]),
            reference_delivery=bool(case["reference_delivery"]),
            reference_utility_passed=case["reference_utility_passed"],
            predicate_selfcheck_passed=case["predicate_selfcheck_passed"],
            formal_compatible=case["formal_compatible"],
            validation_issues=";".join(case["validation_issues"]),
            live_delivery_verified=case["live_delivery_verified"],
            live_attack_success="unknown",
            evidence_boundary="offline simulated AgentDojo environment; no model calls or real email/file/calendar actions",
        ))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--matrix-output", type=Path)
    args = parser.parse_args(argv)
    result = validate_manifest(args.manifest)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.matrix_output:
        write_matrix(result, args.matrix_output, args.manifest)
    print(json.dumps({k: v for k, v in result.items() if k != "cases"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
