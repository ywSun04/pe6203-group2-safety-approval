"""Handoff checks that do not call a model."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_one_task
from approval_gate.model_env import missing_model_settings
from approval_gate.scripted_demo import run_scripted_demo


def test_missing_openai_key_does_not_call_a_model(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    code = run_one_task.main(
        [
            "--policy",
            "full-approve",
            "--model",
            "gpt-4o-mini-2024-07-18",
            "--log-dir",
            str(tmp_path),
        ]
    )
    error = capsys.readouterr().err
    assert code == 2
    assert "did not call a model" in error
    assert "OPENAI_API_KEY" in error
    assert not (tmp_path / "calls.jsonl").exists()


def test_omitted_model_does_not_call_a_model(tmp_path, capsys):
    code = run_one_task.main(["--policy", "full-escalate", "--k", "1", "--log-dir", str(tmp_path)])
    error = capsys.readouterr().err
    assert code == 2
    assert "--model" in error
    assert not (tmp_path / "calls.jsonl").exists()


def test_omitted_run_id_is_generated_and_manual_id_is_kept():
    generated = run_one_task.parse_args(["--policy", "full-approve", "--log-dir", "logs"])
    manual = run_one_task.parse_args(["--policy", "full-approve", "--log-dir", "logs", "--run-id", "manual-7"])
    assert generated.run_id is None
    assert manual.run_id == "manual-7"
    assert run_one_task.new_run_id() != run_one_task.new_run_id()


def test_unknown_model_is_rejected():
    try:
        missing_model_settings("not-a-group-model", None)
    except ValueError as error:
        assert "Unknown model" in str(error)
    else:
        raise AssertionError("unknown model was accepted")


def test_scripted_demo_shows_approve_deny_and_exhausted_budget(tmp_path):
    summary = run_scripted_demo(tmp_path)
    assert summary["reviewer-approves"]["executed"] == ["notes.txt"]
    assert summary["reviewer-approves"]["call_rows"][0]["execution_attempted"] is True
    assert summary["reviewer-approves"]["call_rows"][0]["final_decision"] == "APPROVE"

    denied = summary["reviewer-denies"]["call_rows"][0]
    assert summary["reviewer-denies"]["executed"] == []
    assert denied["execution_attempted"] is False
    assert denied["final_decision"] == "DENY"
    assert denied["budget_before"] == 1
    assert denied["budget_after"] == 0
    assert denied["actually_escalated"] is True

    rows = summary["budget-exhausted"]["call_rows"]
    assert summary["budget-exhausted"]["executed"] == ["first.txt"]
    assert summary["budget-exhausted"]["reviewer_calls"] == 1
    assert rows[0]["actually_escalated"] is True
    assert rows[1]["requested_escalation"] is True
    assert rows[1]["actually_escalated"] is False
    assert rows[1]["reviewer_decision"] is None
    assert rows[1]["execution_attempted"] is False
    assert "test data" in (tmp_path / "README.md").read_text(encoding="utf-8")
