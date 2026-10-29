"""Recheck the saved batch-01 registration, evaluation and source fingerprints.

Inputs are read only. Supply independent outputs from the frozen plan generator
and evaluator. The archive fingerprint is recorded provenance unless --archive
is supplied; that optional argument also verifies the original archive bytes.
No model API or experiment tool is called.
"""

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import sys


FROZEN_COMMIT = "4fc6bdfe4fc0eac03cb13c3f0a041b3d690983f2"
ARCHIVE_SHA256 = "7c1b6ff3d2866cea118a90e4c0420288da991f39f6752f3178c9b9af82b52939"
SOURCE_FILES = {
    "approval_gate.executor": "approval_gate/executor.py",
    "approval_gate.policies.basic_risk": "approval_gate/policies/basic_risk.py",
    "approval_gate.policies.budget_aware": "approval_gate/policies/budget_aware.py",
    "reviewer.llm_reviewer": "reviewer/llm_reviewer.py",
}


class AuditError(Exception):
    """A supplied record disagrees with the expected batch."""


def check(condition, message):
    if not condition:
        raise AuditError(message)


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def without_host_paths(rows, fields):
    return [{key: value for key, value in row.items() if key not in fields} for row in rows]


def sha256_json(value):
    # Match the frozen runner's configuration hashing convention.
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def audit(args):
    batch = args.batch_root.resolve()
    repo = args.repo_root.resolve()
    registration = args.registration_root.resolve()
    evaluation = args.evaluation_root.resolve()
    output = args.output.resolve()
    inputs = (batch, registration, evaluation)
    for path in (*inputs, repo):
        check(path.is_dir(), f"Input directory is missing: {path}")
    check(not output.exists(), "Output directory already exists; use a new path")
    check(
        not any(output == path or output.is_relative_to(path) for path in inputs),
        "Output must be outside the source batch and supplied registration/evaluation directories",
    )
    if args.archive is not None:
        actual = hashlib.sha256(args.archive.read_bytes()).hexdigest()
        check(actual == ARCHIVE_SHA256, "Original archive SHA-256 mismatch")

    ours = read(registration / "coverage.json")
    provided = read(batch / "member2-batch01-registration/coverage.json")
    check(ours == provided, "Independent coverage differs from packaged coverage")
    for field, expected in {
        "integration_commit": FROZEN_COMMIT,
        "planned_runs": 2400,
        "matched_runs": 18,
        "missing_runs": 2382,
        "evidence_kind": "formal",
    }.items():
        check(ours[field] == expected, f"Unexpected coverage field: {field}")

    our_plan = read(registration / "evaluation-plan.json")
    their_plan = read(batch / "member2-batch01-registration/evaluation-plan.json")
    check(
        without_host_paths(our_plan, {"directory"})
        == without_host_paths(their_plan, {"directory"}),
        "Independent planned slots differ from packaged planned slots",
    )
    check(len(our_plan) == 2400, "Expected 2,400 planned slots")
    check(sum(row["matched"] for row in our_plan) == 18, "Expected 18 matched slots")
    check(
        read(registration / "registry.json")
        == read(batch / "member2-batch01-registration/registry.json"),
        "Independent registry differs from packaged registry",
    )

    our_evaluation = read(evaluation / "evaluation.json")
    their_evaluation = read(batch / "member2-batch01-evaluation/evaluation.json")
    check(
        our_evaluation["groups"] == their_evaluation["groups"],
        "Independent evaluation groups differ from packaged groups",
    )
    check(
        without_host_paths(our_evaluation["tasks"], {"directory", "task_source"})
        == without_host_paths(their_evaluation["tasks"], {"directory", "task_source"}),
        "Independent task metrics differ from packaged metrics",
    )
    check(
        our_evaluation["warnings"] == their_evaluation["warnings"] == [],
        "Evaluation warnings are present",
    )

    manifest_paths = sorted((batch / "logs").rglob("manifest.json"))
    check(len(manifest_paths) == 18, "Expected exactly 18 run manifests")
    profiles, slots, run_checks = [], [], []
    for path in manifest_paths:
        directory = path.parent
        manifest = read(path)
        settings = manifest["settings"]
        required = ("calls.jsonl", "tasks.jsonl", "usage.jsonl", "summary.json", "trajectory.jsonl")
        check(all((directory / name).is_file() for name in required), f"Incomplete run: {manifest['run_id']}")
        check(manifest["config_id"] == sha256_json(settings)[:20], "Configuration ID mismatch")
        check(settings["source_versions"]["integration_commit"] == FROZEN_COMMIT, "Run freeze mismatch")
        profiles.append({
            key: value for key, value in settings.items()
            if key not in {"policy", "k", "attack", "attack_sha256", "injection_task"}
        })
        slots.append((
            manifest["task_id"], settings["policy"], settings["k"],
            settings["attack"], manifest["repetition"],
        ))
        run_checks.append({
            "run_id": manifest["run_id"], "config_id": manifest["config_id"],
            "directory": directory.relative_to(batch).as_posix(),
            "required_files_present": True, "config_id_recomputed": True,
        })
    expected_slots = set(itertools.product(
        ["user_task_0"], ["full-approve", "full-escalate", "basic_risk"],
        [2], ["none", "file"], range(3),
    ))
    check(set(slots) == expected_slots and len(slots) == len(set(slots)), "Missing or duplicate batch slots")
    check(all(profile == profiles[0] for profile in profiles), "Run profiles differ")
    check(profiles[0] == ours["observed_full_profile"], "Observed coverage profile differs")

    git = ["git", "-c", f"safe.directory={repo.as_posix()}"]

    def frozen_blob(path):
        return subprocess.check_output(git + ["cat-file", "blob", f"{FROZEN_COMMIT}:{path}"], cwd=repo)

    source_matches = []
    for module, path in SOURCE_FILES.items():
        actual = profiles[0]["source_versions"]["module_sha256"][module]
        check(hashlib.sha256(frozen_blob(path)).hexdigest() == actual, f"Frozen module hash mismatch: {module}")
        source_matches.append(module)
    check(
        hashlib.sha256(frozen_blob("experiments/run_suite.py")).hexdigest() == profiles[0]["runner_sha256"],
        "Frozen runner hash mismatch",
    )
    snapshot = read(batch / "preparation/runtime.json")
    check(snapshot["source_versions"] == profiles[0]["source_versions"], "Preparation source versions differ")
    check(snapshot["reviewer_prompt_sha256"] == profiles[0]["reviewer_prompt_sha256"], "Preparation prompt hash differs")
    profile_hash = sha256_json(profiles[0])
    check(profile_hash[:16] == ours["configuration_signature"], "Profile signature mismatch")

    result = {
        "archive_sha256": ARCHIVE_SHA256, "frozen_commit": FROZEN_COMMIT,
        "observed_runs": 18, "planned_runs": 2400, "missing_runs": 2382,
        "duplicate_slots": 0, "complete_slot_set": True, "config_ids_recomputed": 18,
        "recomputed_registration_matches": True, "recomputed_evaluation_matches": True,
        "warnings": [], "recorded_profile_sha256": profile_hash,
        "configuration_signature": ours["configuration_signature"],
        "project_source_hashes_match_frozen_git_blobs": source_matches,
        "runner_hash_matches_frozen_git_blob": True, "run_checks": run_checks,
    }
    environment = {
        "frozen_commit": FROZEN_COMMIT,
        "configuration_signature": ours["configuration_signature"],
        "recorded_profile_sha256": profile_hash, "recorded_profile": profiles[0],
        "prepared_python": snapshot["python"], "prepared_packages": snapshot["installed_packages"],
        "python_and_package_snapshot_source": "preparation/runtime.json; captured before credentials were configured",
        "scope_note": "Source versions, SDK versions and settings are recorded in all 18 run manifests and match. The complete package/Python snapshot is preparation evidence; not a per-run interpreter attestation. Credential-presence flags are intentionally omitted.",
        "source_archive_sha256": ARCHIVE_SHA256,
    }
    output.mkdir(parents=True, exist_ok=False)
    for filename, value in (("registration-audit.json", result), ("environment-profile.json", environment)):
        (output / filename).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "observed_runs": 18, "planned_runs": 2400, "missing_runs": 2382,
        "warnings": [], "configuration_signature": ours["configuration_signature"],
        "archive_bytes_verified": args.archive is not None,
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("batch-root", "repo-root", "registration-root", "evaluation-root", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--archive", type=Path, help="Original zip; verify its bytes against the recorded SHA-256")
    args = parser.parse_args()
    try:
        audit(args)
    except (AuditError, OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print(f"Registration audit failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
