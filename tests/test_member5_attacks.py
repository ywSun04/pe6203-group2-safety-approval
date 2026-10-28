"""Offline evidence checks only; no models, network requests or real tools."""
from __future__ import annotations

import hashlib
import json

import pytest
import yaml

from scripts import validate_member5_attacks as validator


def test_marker_detected_after_yaml_wrap_without_changing_serialised_text():
    marker = "[Workspace maintenance note M5-00]"
    # The pinned tool formatter wraps this actual scalar layout between words.
    rendered = yaml.safe_dump([
        {"description": "A description with enough preceding words to force wrapping " + marker}
    ], width=20)
    assert marker not in rendered
    before = hashlib.sha256(rendered.encode()).hexdigest()
    assert validator.output_contains_marker(rendered, marker)
    assert hashlib.sha256(rendered.encode()).hexdigest() == before


def test_marker_detection_does_not_join_unrelated_fields():
    rendered = yaml.safe_dump({"first": "[Workspace maintenance", "second": "note M5-00]"})
    assert not validator.output_contains_marker(rendered, "[Workspace maintenance note M5-00]")


def test_marker_detection_supports_nested_content_and_plain_text():
    marker = "[case marker]"
    rendered = yaml.safe_dump({"content": [{"type": "text", "content": "Visible " + marker}]})
    assert validator.output_contains_marker(rendered, marker)
    assert validator.output_contains_marker("Visible " + marker, marker)
    assert not validator.output_contains_marker("Visible benign output", marker)


def test_marker_detection_does_not_execute_yaml_tags():
    assert not validator.output_contains_marker(
        "!!python/object/apply:builtins.str [unsafe]", "missing marker")


def test_source_pin_is_checked_before_loading_manifest(monkeypatch, tmp_path):
    monkeypatch.setattr(validator, "installed_commit", lambda: "wrong-commit")
    with pytest.raises(ValueError, match="AgentDojo source must be pinned"):
        validator.validate_manifest(tmp_path / "must-not-be-read.json")


def test_all_twenty_cases_are_delivered_on_reference_paths_without_payload_changes():
    manifest = json.loads(validator.MANIFEST.read_text(encoding="utf-8"))
    paths = [validator.ROOT / case["attack_file"] for case in manifest["cases"]]
    before = {str(path): validator.sha256(path) for path in paths}
    result = validator.validate_manifest()
    assert result["agentdojo_commit"] == validator.PIN
    assert result["evidence_type"] == "offline_reference_validation"
    assert result["case_count"] == 20
    assert result["reference_delivery_count"] == 20
    assert result["reference_utility_pass_count"] == 20
    assert result["predicate_selfcheck_pass_count"] == 20
    assert result["formal_compatible_count"] == 20
    for case in result["cases"]:
        assert case["loader_compatible"] and case["environment_initialized"]
        assert case["vector_id"] in case["reference_reachable_vectors"]
        assert case["reference_delivery"] and case["reference_utility_passed"]
        assert case["initial_goal_satisfied"] is False
        assert case["predicate_selfcheck_passed"]
        assert case["validation_issues"] == []
        assert case["formal_compatible"] == case["predicate_selfcheck_passed"]
        assert case["live_delivery_verified"] is False
        assert case["live_attack_success"] is None
    assert before == {str(path): validator.sha256(path) for path in paths}


def test_rejected_email_fixture_does_not_pass_official_goal_selfcheck():
    """Retain the real v1 compatibility failure instead of weakening its predicate."""
    from agentdojo.task_suite.load_suites import get_suite
    from experiments.run_suite import attack_settings
    from types import SimpleNamespace
    manifest = json.loads(validator.MANIFEST.read_text(encoding="utf-8"))
    current = next(c for c in manifest["cases"] if c["task_id"] == "user_task_16")
    rejected = validator.ROOT / current["rejected_fixture"]
    before_hash = validator.sha256(rejected)
    suite = get_suite(manifest["suite_version"], manifest["suite"])
    task = suite.get_user_task_by_id(current["task_id"])
    injection_task, injections = attack_settings(SimpleNamespace(
        attack="file", attack_file=rejected, injection_task="injection_task_0"), suite)
    environment = task.init_environment(suite.load_and_inject_default_environment(injections))
    initial, after_oracle = validator.check_goal_predicate(suite, injection_task, environment)
    assert initial is False
    assert after_oracle is False
    assert validator.sha256(rejected) == before_hash


def test_matrix_records_incompatible_pair_and_unknown_live_outcome(tmp_path):
    manifest = json.loads(validator.MANIFEST.read_text(encoding="utf-8"))
    original = manifest["cases"][0]
    result = {"cases": [{
        "attack_id": original["attack_id"], "task_id": original["task_id"],
        "injection_task_id": original["injection_task_id"], "vector_id": original["vector_id"],
        "attack_file_sha256": original["attack_file_sha256"],
        "security_function": "example.security", "security_source_sha256": "test-hash",
        "reference_delivery": [{"index": 0, "tool_name": "test_tool"}],
        "reference_utility_passed": True, "predicate_selfcheck_passed": False,
        "formal_compatible": False, "validation_issues": ["test_issue"],
        "live_delivery_verified": False,
    }]}
    output = tmp_path / "matrix.csv"
    validator.write_matrix(result, output)
    import csv
    row = list(csv.DictReader(output.open(encoding="utf-8")))[0]
    assert row["formal_compatible"] == "False"
    assert row["live_attack_success"] == "unknown"
    assert row["reference_tool_indices_zero_based"] == "0"
