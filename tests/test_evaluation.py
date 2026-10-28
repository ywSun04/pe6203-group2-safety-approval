"""Metric correctness tests; these fixtures are synthetic, never benchmark data."""
import json
import tempfile
import unittest
from pathlib import Path

from evaluation import EvaluationError, evaluate, write_outputs


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.task = dict(run_id="r", task_id="user_task_0", policy_name="full_escalate", k=1,
            task_completed=True, security_passed=True, actual_escalation_count=1,
            requested_escalation_count=1, tokens=dict(agent=10, policy=0, reviewer=15),
            reviewer_retry_count=1, reviewer_retry_tokens=5)
        self.call = dict(record_type="tool_call", run_id="r", call_id="r-1",
            requested_escalation=True, actually_escalated=True,
            budget_before=1, budget_after=0, execution_attempted=True)
        self.registry = {"r": dict(evidence_kind="smoke", experiment_id="test", security_scope="benchmark_goal")}

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, rows):
        (self.root / name).write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    def run_eval(self, tasks=None, calls=None, registry=None, plan=None):
        self.write("tasks.jsonl", [self.task] if tasks is None else tasks)
        self.write("calls.jsonl", [self.call] if calls is None else calls)
        return evaluate([self.root], registry=self.registry if registry is None else registry, plan=plan)

    def test_retry_tokens_not_double_counted(self):
        report = self.run_eval()
        self.assertEqual(report["tasks"][0]["reviewer_tokens_recorded"], 15)

    def test_attack_false_is_not_strict_safety(self):
        group = self.run_eval()["groups"][0]
        self.assertIsNone(group["tcr_strict"])
        self.assertEqual(group["strict_unknown_outcomes"], 1)
        self.assertEqual(group["tcr_benchmark_proxy"], 1)

    def test_strict_audit_requires_evidence(self):
        self.registry["r"]["authorization_audit"] = {"scope": "all_executed_calls", "security_passed": True}
        with self.assertRaises(EvaluationError):
            self.run_eval()

    def test_strict_tcr_with_evidence(self):
        self.registry["r"]["authorization_audit"] = {"scope": "all_executed_calls", "security_passed": True, "evidence_refs": ["trajectory.jsonl:1"]}
        group = self.run_eval()["groups"][0]
        self.assertEqual(group["tcr_strict"], 1)
        self.assertEqual(group["hitl_strict_safe_success_tasks"], 1)

    def test_utility_failure_is_known_safe_completion_failure(self):
        self.task["task_completed"] = False
        group = self.run_eval()["groups"][0]
        self.assertEqual(group["tcr_strict"], 0)
        self.assertEqual(group["hitl_all_tasks"], 1)
        self.assertEqual(group["hitl_utility_completed_tasks"], 0)

    def test_budget_exhaustion_does_not_add_hitl(self):
        second = {**self.call, "call_id": "r-2", "actually_escalated": False,
                  "execution_attempted": False, "budget_before": 0}
        self.task["requested_escalation_count"] = 2
        group = self.run_eval(calls=[self.call, second])["groups"][0]
        self.assertEqual(group["requested_escalations"], 2)
        self.assertEqual(group["hitl_all_tasks"], 1)
        self.assertEqual(group["budget_exhausted_requests"], 1)

    def test_excluded_late_tokens_added_once(self):
        late = dict(record_type="late_reviewer_usage", run_id="r", call_id="r-1",
                    late_reviewer_tokens=7, included_in_task_total=False)
        report = self.run_eval(calls=[self.call, late, late])
        self.assertEqual(report["tasks"][0]["reviewer_tokens_recorded"], 22)
        self.assertEqual(len(report["warnings"]), 1)

    def test_included_late_tokens_not_added(self):
        late = dict(record_type="late_reviewer_usage", run_id="r", call_id="r-1",
                    late_reviewer_tokens=7, included_in_task_total=True)
        self.assertEqual(self.run_eval(calls=[self.call, late])["tasks"][0]["reviewer_tokens_recorded"], 15)

    def test_orphan_late_rejected(self):
        late = dict(record_type="late_reviewer_usage", run_id="r", call_id="r-2",
                    late_reviewer_tokens=7, included_in_task_total=False)
        with self.assertRaises(EvaluationError):
            self.run_eval(calls=[self.call, late])

    def test_identical_duplicate_task_and_call_ignored(self):
        report = self.run_eval(tasks=[self.task, self.task], calls=[self.call, self.call])
        self.assertEqual(len(report["tasks"]), 1)
        self.assertEqual(len(report["warnings"]), 2)

    def test_conflicting_duplicate_rejected(self):
        with self.assertRaises(EvaluationError):
            self.run_eval(tasks=[self.task, {**self.task, "task_completed": False}])

    def test_multiple_tasks_under_run_rejected(self):
        with self.assertRaises(EvaluationError):
            self.run_eval(tasks=[self.task, {**self.task, "task_id": "user_task_1"}])

    def test_missing_planned_runs_stay_in_denominator(self):
        metadata = dict(evidence_kind="smoke", experiment_id="test")
        plan = [dict(run_id="r", task_id="user_task_0", policy_name="full_escalate", k=1, **metadata),
                dict(run_id="r2", task_id="user_task_1", policy_name="full_escalate", k=1, **metadata)]
        self.registry["r2"] = self.registry["r"]
        report = self.run_eval(plan=plan)
        self.assertEqual(sum(g["planned_tasks"] for g in report["groups"]), 2)
        self.assertEqual(sum(g["missing_task_rows"] for g in report["groups"]), 1)
        self.assertEqual(len(report["tasks"]), 2)

    def test_extra_observed_run_rejected_with_plan(self):
        with self.assertRaises(EvaluationError):
            self.run_eval(plan=[])

    def test_manifest_without_task_is_missing_attempt(self):
        (self.root / "manifest.json").write_text(json.dumps(dict(run_id="r", task_id="user_task_0", settings={"policy": "full-escalate", "k": 1})))
        report = self.run_eval(tasks=[])
        self.assertEqual(report["groups"][0]["planned_tasks"], 1)
        self.assertEqual(report["groups"][0]["missing_task_rows"], 1)

    def test_zero_tokens_without_ledger_not_free(self):
        self.task["tokens"]["agent"] = 0
        row = self.run_eval()["tasks"][0]
        self.assertFalse(row["agent_usage_known"])
        self.assertFalse(row["reviewer_usage_known"])

    def test_usage_ledger_not_added_to_task_totals(self):
        self.write("usage.jsonl", [dict(record_type="api_attempt", run_id="r", component="agent", attempt=1),
            dict(record_type="api_response", run_id="r", component="agent", attempt=1, usage_known=True, total_tokens=10)])
        row = self.run_eval()["tasks"][0]
        self.assertTrue(row["agent_usage_known"])
        self.assertEqual(row["agent_tokens_recorded"], 10)

    def test_missing_http_response_is_unknown(self):
        self.write("usage.jsonl", [dict(record_type="api_attempt", run_id="r", component="agent", attempt=1)])
        row = self.run_eval()["tasks"][0]
        self.assertFalse(row["agent_usage_known"])
        self.assertEqual(row["agent_unknown_attempts"], 1)

    def test_invalid_boolean_not_coerced(self):
        self.task["task_completed"] = "false"
        with self.assertRaises(EvaluationError):
            self.run_eval()

    def test_formal_run_requires_experiment_id(self):
        self.registry["r"] = {"evidence_kind": "formal"}
        with self.assertRaises(EvaluationError):
            self.run_eval()

    def test_unregistered_data_never_formal(self):
        self.assertEqual(self.run_eval(registry={})["tasks"][0]["evidence_kind"], "unclassified")

    def test_task_call_accounting_mismatch_rejected(self):
        self.task["actual_escalation_count"] = 0
        with self.assertRaises(EvaluationError):
            self.run_eval()

    def test_excess_budget_rejected(self):
        self.call["budget_before"] = 2
        self.call["budget_after"] = 1
        with self.assertRaises(EvaluationError):
            self.run_eval()

    def test_write_outputs_and_failure_template(self):
        report = self.run_eval()
        out = self.root / "out"
        write_outputs(report, out)
        self.assertEqual(len(list(out.iterdir())), 7)
        template = json.loads((out / "failure_annotation_template.json").read_text())
        self.assertEqual(template["cases"][0]["category"], "unclassified")
        self.assertEqual(template["cases"][0]["review_status"], "pending")

    def test_plots_keep_formal_empty_when_only_smoke(self):
        from xml.etree import ElementTree
        report = self.run_eval()
        out = self.root / "out"
        write_outputs(report, out)
        svg = (out / "TCR_vs_k.svg").read_text()
        ElementTree.fromstring(svg)
        self.assertIn("No registered formal evidence", svg)
        self.assertIn("Strict safety from authorization audit", svg)
        self.assertIn("Benchmark goal proxy from runner", svg)

    def test_unknown_safety_plot_is_gap(self):
        from evaluation.plots import write_tcr_svg
        report = self.run_eval()
        path = self.root / "plot.svg"
        write_tcr_svg(report, path)
        svg = path.read_text()
        self.assertIn("No resolved point estimates", svg)
        # Only the benchmark facet has one actual data point.
        self.assertEqual(svg.count('<circle cx='), 2)  # one point plus legend

    def test_tokens_plot_includes_smoke_only(self):
        from evaluation.plots import write_smoke_tokens_svg
        report = self.run_eval()
        report["tasks"].append({**report["tasks"][0], "run_id": "formal-other", "evidence_kind": "formal", "agent_tokens_recorded": 999999})
        path = self.root / "tokens.svg"
        write_smoke_tokens_svg(report, path)
        svg = path.read_text()
        self.assertNotIn("999,999", svg)
        self.assertIn("Agent 10", svg)

    def test_configuration_changes_create_separate_groups(self):
        self.run_eval()
        child = self.root / "child"
        child.mkdir()
        task = {**self.task, "run_id": "r2"}
        call = {**self.call, "run_id": "r2", "call_id": "r2-1"}
        (child / "tasks.jsonl").write_text(json.dumps(task) + "\n")
        (child / "calls.jsonl").write_text(json.dumps(call) + "\n")
        (child / "manifest.json").write_text(json.dumps({"run_id": "r2", "settings": {"reviewer_timeout_seconds": 120}}))
        report = evaluate([self.root], registry={**self.registry, "r2": self.registry["r"]})
        self.assertEqual(len(report["groups"]), 2)

    def test_budget_continuity_checked(self):
        second = {**self.call, "call_id": "r-2", "actually_escalated": False,
                  "execution_attempted": False, "budget_before": 1, "budget_after": 1}
        self.task["requested_escalation_count"] = 2
        with self.assertRaises(EvaluationError):
            self.run_eval(calls=[self.call, second])

    def test_explicit_attack_pack_pools_task_specific_payloads(self):
        self.run_eval()
        child = self.root / "child"
        child.mkdir()
        task = {**self.task, "run_id": "r2", "task_id": "user_task_1"}
        call = {**self.call, "run_id": "r2", "call_id": "r2-1"}
        (child / "tasks.jsonl").write_text(json.dumps(task) + "\n")
        (child / "calls.jsonl").write_text(json.dumps(call) + "\n")
        base = {**self.registry["r"], "attack_pack_id": "fixed20", "attack_pack_sha256": "a"*64}
        registry = {"r": {**base, "attack_id": "injection_task_0", "attack_sha256": "b"*64},
                    "r2": {**base, "attack_id": "injection_task_1", "attack_sha256": "c"*64}}
        report = evaluate([self.root], registry=registry)
        self.assertEqual(len(report["groups"]), 1)
        self.assertEqual(report["groups"][0]["planned_tasks"], 2)
        self.assertEqual(report["groups"][0]["attack_group_id"], "fixed20")
        self.assertEqual(report["tasks"][0]["attack_id"], "injection_task_0")
        for row in registry.values():
            del row["attack_pack_id"]
            del row["attack_pack_sha256"]
        self.assertEqual(len(evaluate([self.root], registry=registry)["groups"]), 2)

    def test_invalid_attack_pack_rejected(self):
        self.registry["r"]["attack_pack_id"] = "fixed20"
        with self.assertRaises(EvaluationError):
            self.run_eval()

    def test_registry_cannot_hide_different_payload_hash(self):
        self.registry["r"]["attack_sha256"] = "a"*64
        (self.root / "manifest.json").write_text(json.dumps({"run_id": "r", "settings": {"attack_sha256": "b"*64}}))
        with self.assertRaises(EvaluationError):
            self.run_eval()

    def test_manifest_task_mismatch_rejected(self):
        (self.root / "manifest.json").write_text(json.dumps({"run_id": "r", "task_id": "different"}))
        with self.assertRaises(EvaluationError):
            self.run_eval()


if __name__ == "__main__":
    unittest.main()
