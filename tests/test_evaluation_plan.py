"""Offline scheduler/coverage contract tests. No model or AgentDojo import."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from evaluation import EvaluationError, evaluate
from scripts.member5_experiment_plan import build_plan, sha, write_plan


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.commit = "a"*40
        self.config = dict(suite="workspace", suite_version="v1.2.2", agentdojo_commit="b"*40,
            model_id="openai/gpt-4o-mini", reviewer_model="openai/gpt-4o-mini",
            task_ids=["user_task_0", "user_task_1"], policies=["full-approve", "basic_risk"],
            k=[0, 2], repeat=2, conditions=["none", "file"], attack_manifest="attacks.json")
        self.cases = []
        for index, task in enumerate(self.config["task_ids"]):
            filename = f"attack{index}.json"
            (self.root / filename).write_text(json.dumps({"vector": f"synthetic fixture {index}"}))
            self.cases.append(dict(task_id=task, attack_id=f"attack_{index}", attack_file=filename,
                attack_file_sha256=hashlib.sha256((self.root / filename).read_bytes()).hexdigest(),
                injection_task_id=f"injection_task_{index}"))
        self.manifest = {k: self.config[k] for k in ("suite", "suite_version", "agentdojo_commit")}
        self.manifest["cases"] = self.cases
        self.save_config()

    def tearDown(self):
        self.temp.cleanup()

    def save_config(self):
        (self.root / "plan.json").write_text(json.dumps(self.config))
        (self.root / "attacks.json").write_text(json.dumps(self.manifest))

    def build(self, **kwargs):
        return build_plan(self.root / "plan.json", self.root, integration_commit=self.commit, **kwargs)

    def log(self, name="run1", **settings_changes):
        result = self.build()
        profile = result["coverage"]["frozen_expected_profile"]
        settings = {**profile, "policy": "full-approve", "k": 0, "attack": "none",
            "attack_sha256": sha({}), "injection_task": None,
            "source_versions": {"integration_commit": self.commit, "agentdojo_commit": self.config["agentdojo_commit"], "versions": {"agentdojo": "test"}},
            "runner_sha256": "c"*64, **settings_changes}
        directory = self.root / "logs" / name
        directory.mkdir(parents=True)
        (directory / "manifest.json").write_text(json.dumps(dict(run_id=name, task_id="user_task_0", repetition=0, config_id="test", settings=settings)))
        return directory

    def test_fixed_slots_and_command_count(self):
        result = self.build()
        self.assertEqual(result["coverage"]["planned_runs"], 32)
        self.assertEqual(result["coverage"]["missing_runs"], 32)
        self.assertEqual(len(result["commands"]), 4)
        self.assertEqual(len({row["slot_id"] for row in result["evaluation_plan"]}), 32)
        self.assertTrue(all("--live" not in c["argv"] for c in result["commands"]))
        self.assertTrue(all(r["evidence_kind"] == "unclassified" for r in result["evaluation_plan"]))

    def test_missing_logs_compatible_with_evaluator(self):
        result = self.build()
        report = evaluate([self.root], registry=result["registry"], plan=result["evaluation_plan"])
        self.assertEqual(len(report["tasks"]), 32)
        self.assertEqual(sum(g["missing_task_rows"] for g in report["groups"]), 32)
        self.assertTrue(all(g["tcr_strict"] is None for g in report["groups"]))

    def test_saved_uuid_maps_to_slot_and_shares_signature(self):
        self.log()
        result = self.build(log_roots=[self.root / "logs"], evidence_kind="formal")
        self.assertEqual(result["coverage"]["matched_runs"], 1)
        actual = [row for row in result["evaluation_plan"] if row["matched"]]
        self.assertEqual(actual[0]["run_id"], "run1")
        self.assertEqual(len({r["configuration_signature"] for r in result["evaluation_plan"]}), 1)
        report = evaluate([self.root / "logs"], registry=result["registry"], plan=result["evaluation_plan"])
        self.assertEqual(sum(g["planned_tasks"] for g in report["groups"]), 32)

    def test_duplicate_slot_is_error(self):
        self.log("run1")
        self.log("run2")
        with self.assertRaisesRegex(EvaluationError, "Duplicate planned slot"):
            self.build(log_roots=[self.root / "logs"])

    def test_wrong_model_is_error(self):
        self.log(model_id="different")
        with self.assertRaisesRegex(EvaluationError, "model_id"):
            self.build(log_roots=[self.root / "logs"])

    def test_wrong_integration_commit_is_error(self):
        self.log(source_versions={"integration_commit": "d"*40, "agentdojo_commit": self.config["agentdojo_commit"]})
        with self.assertRaisesRegex(EvaluationError, "Integration commit"):
            self.build(log_roots=[self.root / "logs"])

    def test_wrong_payload_hash_is_error(self):
        self.log(attack="file", injection_task="injection_task_0", attack_sha256="d"*64)
        with self.assertRaisesRegex(EvaluationError, "attack assignment"):
            self.build(log_roots=[self.root / "logs"])

    def test_extra_runtime_setting_change_is_error(self):
        self.log("run1")
        path = self.log("run2", policy="basic_risk", unexpected_setting=2) / "manifest.json"
        with self.assertRaisesRegex(EvaluationError, "Different runtime/source"):
            self.build(log_roots=[self.root / "logs"])

    def test_frozen_pack_pools_task_specific_attacks(self):
        result = self.build()
        attacked = [r for r in result["evaluation_plan"] if r["condition"] == "file"]
        self.assertEqual(len({r["attack_pack_sha256"] for r in attacked}), 1)
        self.assertEqual(len({r["attack_id"] for r in attacked}), 2)
        report = evaluate([self.root], registry=result["registry"], plan=result["evaluation_plan"])
        attacked_groups = [g for g in report["groups"] if g["condition"] == "file"]
        self.assertTrue(all(g["planned_tasks"] == 4 for g in attacked_groups))

    def test_modified_fixture_is_error(self):
        (self.root / "attack0.json").write_text("{}")
        with self.assertRaisesRegex(EvaluationError, "hash mismatch"):
            self.build()

    def test_output_never_overwrites(self):
        result = self.build()
        output = self.root / "out"
        write_plan(result, output)
        with self.assertRaises(FileExistsError):
            write_plan(result, output)
        self.assertEqual(len(list(output.iterdir())), 5)

    def test_full_project_grid_is_2400(self):
        root = Path(__file__).resolve().parents[1]
        config = root / "configs/member5/experiment-plan.json"
        if config.exists():
            result = build_plan(config, root, integration_commit=self.commit)
            self.assertEqual(len(result["evaluation_plan"]), 2400)
            self.assertEqual(len(result["commands"]), 40)

    def test_boolean_repetition_not_coerced_to_slot_one(self):
        directory = self.log()
        path = directory / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["repetition"] = False
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(EvaluationError, "Observed repetition"):
            self.build(log_roots=[self.root / "logs"])


if __name__ == "__main__":
    unittest.main()
