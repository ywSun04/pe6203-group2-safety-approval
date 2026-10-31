"""Strict, evaluator-only reconciliation of the frozen experiment evidence.

Original manifests are never changed. Only known LF/CRLF source fingerprints
and evidence-backed repetition mappings can affect derived grouping metadata.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

FROZEN_COMMIT = "4fc6bdfe4fc0eac03cb13c3f0a041b3d690983f2"
AGENTDOJO_COMMIT = "089ed468cf3ed0322acc66b0211f26d9d90dbf60"
PROMPT_SHA256 = "f65dcec71074a8402c7a094e4f4976cc95a33b655e0d7084563ecbf602f040a9"
PROTOCOL = "member5-frozen4fc-reconciliation-v1"

# Each pair is SHA-256(LF frozen reference), SHA-256(its exact CRLF transform).
# The accompanying evidence file records the Git blob paths and derivation.
SOURCE_HASHES = {
    "approval_gate.executor": ("a568667dfe029c39245424b3088701b891263cfae20e3630c5d8aff71ff48ca8", "ed1d49ee48f7f62791eb86e072814fce139e65faec33216d8fbd2177f894d653"),
    "approval_gate.policies.basic_risk": ("e4546a7e122a4b655bf8669173adfd44f27cdf132cbd262c17e07ebdfd61d82a", "6a4a43ee6d81385f8e6d848fd3bffa942ec9218eed91c73ee5b408075be29182"),
    "approval_gate.policies.budget_aware": ("fd365bb31783cc3328acd6df010da9fe3281308ae7a6e63161bf63b5da2ebb61", "65f8d2c0f7c074a22b7c1dfabf67b019ecf988c57d17fd0c646816670e4b7f6e"),
    "reviewer.llm_reviewer": ("f06ae668da62ef4d22edbe6d8121b58bd62d5ff04e351eca4101174889e3d669", "2b8b6c55e5427ff3d6d20aea95075fd8e04b821108d0df44d64f5eccaea81e20"),
    "agentdojo.task_suite.task_suite": ("2e69da06f7e150dd6d238c53a74845b56eebeb224e07f694e1051a6e0c6a2bc1", "5a989815b0d66d87a0f1b802b1753c6a37d181d02b3dbc5933a330f2eb85fef1"),
}
RUNNER_HASHES = ("d788546cc4478a659d87603b143e3fe7fe037249d3562d718ff235fbcfd1ce28", "71452fc9c4b852d18774fe74d85e502920a0f7f4ef2f0c7f8c39f2ede6aa367d")


class ReconciliationError(ValueError):
    """Evidence does not meet the explicit reconciliation protocol."""


def json_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def canonical_profile(settings):
    """Return the frozen common profile, rejecting all unrecognised drift."""
    profile = {k: v for k, v in settings.items()
               if k not in {"policy", "k", "attack", "attack_sha256", "injection_task"}}
    expected = {
        "suite": "workspace", "suite_version": "v1.2.2",
        "model_id": "openai/gpt-4o-mini", "reviewer_model": "openai/gpt-4o-mini",
        "agent_base_url": "https://openrouter.ai/api/v1",
        "reviewer_base_url": "https://openrouter.ai/api/v1",
        "reviewer_prompt_sha256": PROMPT_SHA256,
        "reviewer_timeout_seconds": 30.0, "connect_timeout_seconds": 2.0,
        "max_agent_requests": 20, "max_output_tokens": 2048, "temperature": 0.0,
    }
    if set(profile) != set(expected) | {"source_versions", "runner_sha256"}:
        raise ReconciliationError("Unexpected or missing runtime profile fields")
    for field, value in expected.items():
        actual = profile[field]
        if actual != value or isinstance(actual, bool):
            raise ReconciliationError(f"Unapproved frozen setting: {field}")
        if field in {"max_agent_requests", "max_output_tokens"} and type(actual) is not int:
            raise ReconciliationError(f"Noninteger frozen cap: {field}")
    versions = profile["source_versions"]
    if not isinstance(versions, dict) or set(versions) != {"integration_commit", "agentdojo_commit", "module_sha256", "versions"}:
        raise ReconciliationError("Unexpected source-version fields")
    if versions["integration_commit"] != FROZEN_COMMIT or versions["agentdojo_commit"] != AGENTDOJO_COMMIT:
        raise ReconciliationError("Frozen source commit mismatch")
    if versions["versions"] != {"agentdojo": "0.1.35", "openai": "3.39.0", "httpx": "0.28.1"}:
        raise ReconciliationError("Unapproved dependency versions")
    modules = versions["module_sha256"]
    if not isinstance(modules, dict) or set(modules) != set(SOURCE_HASHES):
        raise ReconciliationError("Unexpected module fingerprint set")
    for name, accepted in SOURCE_HASHES.items():
        if modules[name] not in accepted:
            raise ReconciliationError(f"Unapproved module fingerprint: {name}")
    if profile["runner_sha256"] not in RUNNER_HASHES:
        raise ReconciliationError("Unapproved runner fingerprint")
    return {
        **expected,
        "source_versions": {
            "integration_commit": FROZEN_COMMIT, "agentdojo_commit": AGENTDOJO_COMMIT,
            "module_sha256": {name: hashes[0] for name, hashes in SOURCE_HASHES.items()},
            "versions": dict(versions["versions"]),
        },
        "runner_sha256": RUNNER_HASHES[0],
    }


def reconciliation_signature(run_id, directory, manifest, registered):
    """Verify a sidecar before deriving a common profile or repetition.

The registry remains evaluator evidence, like authorisation annotations. This
check binds it to the exact raw manifest and preserves both source identities.
It does not infer owner acknowledgement or independent repetition from a name.
"""
    proof = registered.get("reconciliation")
    if not isinstance(proof, dict) or proof.get("protocol") != PROTOCOL:
        raise ReconciliationError("Missing or unknown reconciliation protocol")
    if proof.get("run_id") != run_id or manifest.get("run_id") != run_id:
        raise ReconciliationError("Reconciliation run ID mismatch")
    path = Path(directory) / "manifest.json"
    if hashlib.sha256(path.read_bytes()).hexdigest() != proof.get("raw_manifest_sha256"):
        raise ReconciliationError("Raw manifest does not match the sidecar hash")
    raw_rep = manifest.get("repetition")
    if type(raw_rep) is not int or raw_rep not in {0, 1, 2} or type(proof.get("raw_repetition")) is not int or raw_rep != proof["raw_repetition"]:
        raise ReconciliationError("Raw repetition does not match the sidecar")
    rep = proof.get("planned_repetition")
    if type(rep) is not int or rep not in {0, 1, 2} or type(registered.get("repetition")) is not int or registered["repetition"] != rep:
        raise ReconciliationError("Invalid reconciled repetition")
    if "owner_acknowledged" in proof and type(proof["owner_acknowledged"]) is not bool:
        raise ReconciliationError("Owner acknowledgement must be an explicit boolean")
    if not isinstance(proof.get("evidence_refs"), list) or not proof["evidence_refs"] or not all(isinstance(v, str) and v for v in proof["evidence_refs"]):
        raise ReconciliationError("Repetition mapping needs evidence references")
    settings = manifest.get("settings", {})
    if manifest.get("config_id") != json_sha(settings)[:20]:
        raise ReconciliationError("Raw configuration ID is invalid")
    raw_profile = {k: v for k, v in settings.items()
                   if k not in {"policy", "k", "attack", "attack_sha256", "injection_task"}}
    if proof.get("raw_profile_sha256") != json_sha(raw_profile):
        raise ReconciliationError("Raw profile does not match the sidecar")
    canonical = canonical_profile(settings)
    signature = json_sha(canonical)
    if proof.get("canonical_profile_sha256") != signature:
        raise ReconciliationError("Canonical profile does not match the sidecar")
    return signature[:16]
