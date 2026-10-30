"""Selection and archive guards for offline reconciliation."""
import importlib.util
import json
from pathlib import Path
import zipfile

import pytest

spec = importlib.util.spec_from_file_location("reconcile_saved", Path(__file__).resolve().parents[1] / "scripts/reconcile_saved_runs.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_first_error_stays_primary_when_retry_succeeds():
    first = {"run_id": "20261030T051346Z-7bcfa48ca3b04a8ca6baf6d2ebdb9044", "task_completed": None, "error_type": "APITimeoutError"}
    retry = {"run_id": "20261030T052710Z-2e9e0ee7047744aeadb7ac89b11c97e9", "task_completed": True, "error_type": None}
    assert module.select_primary([retry, first]) is first
    assert module.select_primary([first, retry]) is first


def test_cross_member_overlap_keeps_earlier_assigned_observation():
    earlier = {"run_id": "20261029T152556Z-5b7a63137acb4d34b0afe1cb777622b0", "owner": "Member 2", "task_completed": False}
    later = {"run_id": "20261030T054706Z-bc80959fae4946019ba1b5f6c610769e", "owner": "Member 6", "task_completed": True}
    assert module.select_primary([later, earlier]) is earlier


def test_catalog_cannot_use_traversal_as_run_identifier(tmp_path):
    archive = tmp_path / "evidence.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("source-catalog.json", json.dumps({"runs": {"../escape": {"files_sha256": {}}}}))
    with pytest.raises(ValueError, match="Unexpected run ID"):
        module.read_evidence(archive, tmp_path / "derived")
    assert not (tmp_path / "escape").exists()


def test_catalog_hash_mismatch_does_not_write_a_changed_manifest(tmp_path):
    archive = tmp_path / "evidence.zip"
    run_id = "20261030T051346Z-7bcfa48ca3b04a8ca6baf6d2ebdb9044"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("source-catalog.json", json.dumps({"runs": {run_id: {"files_sha256": {"manifest.json": "0" * 64}}}}))
        z.writestr(f"runs/{run_id}/manifest.json", "{}")
    with pytest.raises(ValueError, match="Evidence hash mismatch"):
        module.read_evidence(archive, tmp_path / "derived")
    assert not (tmp_path / "derived/raw-run-files" / run_id / "manifest.json").exists()
