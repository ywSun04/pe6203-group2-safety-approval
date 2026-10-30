"""Evidence binding and strict fingerprint equivalence, without API calls."""
import copy
import json

import pytest

from evaluation.reconciliation import (
    AGENTDOJO_COMMIT, FROZEN_COMMIT, PROMPT_SHA256, PROTOCOL,
    RUNNER_HASHES, SOURCE_HASHES, ReconciliationError,
    canonical_profile, json_sha, reconciliation_signature,
)


def settings(crlf=False):
    return {
        "suite": "workspace", "suite_version": "v1.2.2",
        "model_id": "openai/gpt-4o-mini", "reviewer_model": "openai/gpt-4o-mini",
        "agent_base_url": "https://openrouter.ai/api/v1",
        "reviewer_base_url": "https://openrouter.ai/api/v1",
        "reviewer_prompt_sha256": PROMPT_SHA256,
        "reviewer_timeout_seconds": 30, "connect_timeout_seconds": 2,
        "max_agent_requests": 20, "max_output_tokens": 2048, "temperature": 0,
        "policy": "full-approve", "k": 2, "attack": "none",
        "attack_sha256": json_sha({}), "injection_task": None,
        "source_versions": {"integration_commit": FROZEN_COMMIT,
            "agentdojo_commit": AGENTDOJO_COMMIT,
            "versions": {"agentdojo": "0.1.35", "openai": "3.39.0", "httpx": "0.28.1"},
            "module_sha256": {name: pair[int(crlf)] for name, pair in SOURCE_HASHES.items()}},
        "runner_sha256": RUNNER_HASHES[int(crlf)],
    }


def test_only_known_newline_equivalence_and_numeric_serialization_are_pooled():
    lf, crlf = settings(), settings(True)
    crlf["reviewer_timeout_seconds"] = 30.0
    before = copy.deepcopy(crlf)
    assert canonical_profile(lf) == canonical_profile(crlf)
    assert json_sha(canonical_profile(crlf))[:16] == "ed94c6d6374d08d4"
    assert crlf == before


@pytest.mark.parametrize("change", ["unknown_hash", "prompt", "caps", "dependency", "source", "extra_module", "extra_field", "bool_timeout"])
def test_real_runtime_drift_is_rejected(change):
    value = settings(True)
    if change == "unknown_hash": value["source_versions"]["module_sha256"]["approval_gate.executor"] = "0" * 64
    elif change == "prompt": value["reviewer_prompt_sha256"] = "0" * 64
    elif change == "caps": value["max_agent_requests"] = 5
    elif change == "dependency": value["source_versions"]["versions"]["openai"] = "other"
    elif change == "source": value["source_versions"]["integration_commit"] = "0" * 40
    elif change == "extra_module": value["source_versions"]["module_sha256"]["other"] = "0" * 64
    elif change == "extra_field": value["unreviewed_option"] = "changed"
    else: value["reviewer_timeout_seconds"] = True
    with pytest.raises(ReconciliationError): canonical_profile(value)


def sidecar(tmp_path):
    value = settings(True)
    manifest = {"run_id": "saved-run", "task_id": "user_task_0", "repetition": 0,
                "config_id": json_sha(value)[:20], "settings": value}
    raw = json.dumps(manifest).encode()
    (tmp_path / "manifest.json").write_bytes(raw)
    import hashlib
    proof = {"protocol": PROTOCOL, "run_id": "saved-run",
        "raw_manifest_sha256": hashlib.sha256(raw).hexdigest(), "raw_repetition": 0,
        "planned_repetition": 2, "evidence_refs": ["scheduler.json:completed[key]"],
        "raw_profile_sha256": json_sha({k:v for k,v in value.items() if k not in {"policy", "k", "attack", "attack_sha256", "injection_task"}}),
        "canonical_profile_sha256": json_sha(canonical_profile(value))}
    return manifest, {"repetition": 2, "reconciliation": proof}, raw


def test_repetition_mapping_is_separate_and_bound_to_unchanged_manifest(tmp_path):
    manifest, registered, raw = sidecar(tmp_path)
    assert reconciliation_signature("saved-run", tmp_path, manifest, registered) == "ed94c6d6374d08d4"
    assert manifest["repetition"] == 0 and registered["repetition"] == 2
    assert (tmp_path / "manifest.json").read_bytes() == raw


@pytest.mark.parametrize("change", ["raw_bytes", "missing_evidence", "original_rep", "planned_rep", "profile_proof", "config_id", "raw_rep_boolean", "proof_rep_boolean", "registered_rep_boolean", "owner_ack_string"])
def test_mapping_cannot_mask_changed_or_unbound_evidence(tmp_path, change):
    manifest, registered, raw = sidecar(tmp_path)
    proof = registered["reconciliation"]
    if change == "raw_bytes": (tmp_path / "manifest.json").write_bytes(raw + b"\n")
    elif change == "missing_evidence": proof["evidence_refs"] = []
    elif change == "original_rep": proof["raw_repetition"] = 1
    elif change == "planned_rep": registered["repetition"] = 1
    elif change == "profile_proof": proof["canonical_profile_sha256"] = "0" * 64
    elif change == "raw_rep_boolean": manifest["repetition"] = False
    elif change == "proof_rep_boolean": proof["raw_repetition"] = False
    elif change == "registered_rep_boolean": registered["repetition"] = True;proof["planned_repetition"] = 1
    elif change == "owner_ack_string": proof["owner_acknowledged"] = "False"
    else: manifest["config_id"] = "wrong"
    with pytest.raises(ReconciliationError): reconciliation_signature("saved-run", tmp_path, manifest, registered)
