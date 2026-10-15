"""Independent acceptance regressions for CR-007; not implementation fixtures."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from qa_master.application import CampaignApplicationService as Service
from qa_master.state_store import StateConflictError
from qa_master.workflow import Workflow


class CanonicalWorkflowIndependentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "campaign.json"

    def tearDown(self):
        self.directory.cleanup()

    def _legacy_campaign(self, **overrides):
        value = {
            "name": "legacy-project",
            "known": {"gitlab": {"status": "PROVIDED", "value": "group/repo"}},
            "approvals": {"execution": "legacy-v1"},
            "artifacts": {"draft": "artifact://draft"},
            "questions": {"requirements": "asked"},
            "history": [{"event": "answer", "field": "gitlab", "status": "PROVIDED"}],
            "run_ids": ["run-1"],
            "task_contract": {
                "schema_version": 1,
                "stages": ["design"],
                "no_execution": True,
                "no_external_writes": True,
                "capabilities": {"execute": False, "external_write": False},
                "authority": "PLANNING_ONLY",
            },
            "revision": 0,
        }
        value.update(overrides)
        return value

    def _write_legacy_campaign(self, **overrides):
        value = self._legacy_campaign(**overrides)
        self.path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return value

    def test_tc_sm_001_canonical_cli_round_trip_preserves_compatibility_projection(self):
        command = [sys.executable, "-m", "qa_master", "--state", str(self.path)]
        environment = dict(os.environ, PYTHONIOENCODING="ascii")
        for args in (("init", "中文项目"), ("answer", "gitlab", "group/repo"),
                     ("plan", "只生成用例，不执行测试")):
            completed = subprocess.run(command + list(args), env=environment, text=True,
                                       capture_output=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
        self.assertTrue(payload["no_execution"])
        self.assertEqual(payload["task_contract"]["authority"], "PLANNING_ONLY")
        status = subprocess.run(command + ["status"], env=environment, text=True,
                                capture_output=True, check=False)
        self.assertEqual(status.returncode, 0, status.stderr)
        state = json.loads(status.stdout)
        self.assertEqual(state["project"], "中文项目")
        self.assertEqual(state["known"]["gitlab"]["status"], "PROVIDED")
        self.assertNotEqual(state["known"]["gitlab"]["value"], "group/repo")
        self.assertFalse(state["execution_authorized"])

    def test_tc_sm_002_legacy_campaign_preserves_complete_private_payload_and_migrates_once(self):
        legacy = self._write_legacy_campaign()
        original = self.path.read_bytes()
        service = Service.load(self.path)
        self.assertTrue(service.needs_migration)
        self.assertEqual(service.document["legacy_payload"], legacy)
        self.assertEqual(self.path.read_bytes(), original)
        service.mutate("pause", reason="migration test")
        backup = list(self.path.parent.glob("campaign.json.legacy-*.json"))
        self.assertEqual(len(backup), 1)
        self.assertEqual(backup[0].read_bytes(), original)
        migrated = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(migrated["schema_name"], "qa-master.campaign")
        self.assertEqual(migrated["schema_version"], 2)
        again = Service.load(self.path)
        self.assertFalse(again.needs_migration)
        before = self.path.read_bytes()
        again.mutate("resume")
        self.assertEqual(len(list(self.path.parent.glob("campaign.json.legacy-*.json"))), 1)
        self.assertNotEqual(self.path.read_bytes(), before)

    def test_tc_sm_003_design_only_legacy_state_remains_default_deny_after_reload(self):
        self._write_legacy_campaign()
        service = Service.load(self.path)
        self.assertEqual(service.check("execution")["state"], "DENIED_BY_TASK_SCOPE")
        service.mutate("pause", reason="persist migration")
        reloaded = Service.load(self.path)
        self.assertEqual(reloaded.check("execution")["state"], "DENIED_BY_TASK_SCOPE")
        recorded = reloaded.mutate("resume")
        self.assertFalse(recorded["execution_authorized"])
        legacy = reloaded.mutate("approve", kind="execution", version="legacy-v2")
        self.assertEqual(legacy["state"], "RECORDED_UNVERIFIED")
        self.assertEqual(reloaded.check("execution")["state"], "DENIED_BY_TASK_SCOPE")

    def test_tc_sm_004_pause_survives_reload_and_rejects_progression_without_write(self):
        service = Service.initialize(self.path, "demo")
        service.mutate("pause", reason="await evidence")
        paused = Service.load(self.path)
        self.assertEqual(paused.status()["mode"], "PAUSED")
        before = self.path.read_bytes()
        for command, payload in (("answer", {"key": "source", "value": "spec"}),
                                 ("plan", {"prompt": "只生成用例"}),
                                 ("approve", {"kind": "execution", "version": "v1"})):
            with self.subTest(command=command), self.assertRaisesRegex(PermissionError, "CAMPAIGN_PAUSED"):
                paused.mutate(command, **payload)
        self.assertEqual(self.path.read_bytes(), before)
        paused.mutate("resume")
        self.assertEqual(Service.load(self.path).status()["mode"], "ACTIVE")

    def test_tc_sm_005_cas_rejects_stale_writer_and_leaves_complete_winner(self):
        Service.initialize(self.path, "demo")
        first, stale = Service.load(self.path), Service.load(self.path)
        first.mutate("answer", key="source", value="spec-v1")
        with self.assertRaises(StateConflictError):
            stale.mutate("pause", reason="stale")
        document = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(document["answers"]["source"]["value"], "spec-v1")
        self.assertFalse(list(self.path.parent.glob(".qa-master-state-*.json")))

    def test_tc_sm_005_parallel_init_has_one_winner_without_partial_state(self):
        barrier = threading.Barrier(2)
        outcomes = []

        def initializer(project):
            barrier.wait()
            try:
                outcomes.append(("created", Service.initialize(self.path, project).status()["project"]))
            except StateConflictError:
                outcomes.append(("conflict", project))

        threads = [threading.Thread(target=initializer, args=(project,)) for project in ("left", "right")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(kind for kind, _ in outcomes), ["conflict", "created"])
        self.assertIn(Service.load(self.path).status()["project"], {"left", "right"})
        self.assertFalse(list(self.path.parent.glob(".qa-master-state-*.json")))

    def test_tc_sm_013_failed_migration_write_retains_legacy_bytes_and_recovers(self):
        self._write_legacy_campaign()
        original = self.path.read_bytes()
        service = Service.load(self.path)
        with patch("qa_master.state_store.os.replace", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                service.mutate("pause", reason="fault injection")
        self.assertEqual(self.path.read_bytes(), original)
        backups = list(self.path.parent.glob("campaign.json.legacy-*.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)
        Service.load(self.path).mutate("pause", reason="recovery")
        self.assertEqual(Service.load(self.path).status()["mode"], "PAUSED")

    def test_tc_sm_007_to_009_read_only_commands_do_not_migrate_or_overwrite_existing_state(self):
        self._write_legacy_campaign()
        before_bytes = self.path.read_bytes()
        before_mtime = self.path.stat().st_mtime_ns
        command = [sys.executable, "-m", "qa_master", "--state", str(self.path)]
        for args in (("status",), ("check", "execution")):
            completed = subprocess.run(command + list(args), text=True, capture_output=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            json.loads(completed.stdout)
        self.assertEqual(self.path.read_bytes(), before_bytes)
        self.assertEqual(self.path.stat().st_mtime_ns, before_mtime)
        init = subprocess.run(command + ["init", "replacement"], text=True, capture_output=True, check=False)
        self.assertNotEqual(init.returncode, 0)
        self.assertEqual(self.path.read_bytes(), before_bytes)

    def test_tc_sm_001_next_material_questions_survive_reload_and_answer_refreshes_them(self):
        service = Service.initialize(self.path, "demo")
        service.mutate("answer", key="gitlab", value="group/repo")
        planned = service.mutate("plan", prompt="只生成用例")
        self.assertTrue(planned["questions"])
        after_plan = Service.load(self.path).status()
        self.assertEqual(after_plan["questions"], planned["questions"])
        service = Service.load(self.path)
        service.mutate("answer", key="requirements", value="没有")
        self.assertEqual(Service.load(self.path).status()["questions"], [])

    def test_tc_sm_008_rejects_malformed_task_contract_without_changing_current_bytes(self):
        Service.initialize(self.path, "demo")
        baseline = json.loads(self.path.read_text(encoding="utf-8"))
        invalid_contracts = [
            dict(baseline["task_contract"], schema_version="2"),
            dict(baseline["task_contract"], stages=["not-a-workflow-step"]),
            dict(baseline["task_contract"], unexpected="unrecognized"),
        ]
        for contract in invalid_contracts:
            with self.subTest(contract=contract):
                candidate = dict(baseline, task_contract=contract)
                self.path.write_text(json.dumps(candidate), encoding="utf-8")
                before = self.path.read_bytes()
                with self.assertRaises(ValueError):
                    Service.load(self.path)
                self.assertEqual(self.path.read_bytes(), before)

    def test_tc_sm_011_recursive_exact_ancestor_drift_blocks_completed_descendant(self):
        workflow = Workflow("demo")
        workflow.request(["design"])
        workflow.answer("source", "spec")
        artifacts = {"requirements": {"text": "v1"}}
        scopes = {"requirements": "demo"}
        workflow.complete_exact("requirements", "req", artifacts, scopes)
        workflow.complete_exact("review", "review", artifacts, scopes)
        workflow.approve_exact("requirements", "demo", artifacts["requirements"], "test-reviewer")
        workflow.complete_exact("baseline", "baseline", artifacts, scopes)
        workflow.complete_exact("design", "design", artifacts, scopes)
        artifacts["requirements"]["text"] = "v2"
        self.assertEqual(workflow.evaluate_exact("design", artifacts, scopes), "STALE")
        self.assertEqual(workflow.steps["design"].status, "PENDING")
        self.assertNotEqual(workflow.evaluate_exact("baseline", artifacts, scopes), "DONE")

    def test_tc_sm_002_migrated_done_steps_are_persisted_as_needs_revalidation(self):
        workflow = Workflow("demo")
        workflow.request(["execution"])
        for step in workflow.steps.values():
            step.status = "DONE"
            step.result_ref = "legacy-result"
            step.completion_binding = {"legacy": "binding"}
            step.execution_receipt = {"issuer": "legacy"}
        raw = asdict(workflow)
        self.path.write_text(json.dumps(raw), encoding="utf-8")
        service = Service.load(self.path)
        self.assertEqual(service.document["legacy_payload"], raw)
        self.assertTrue(all(step["status"] == "NEEDS_REVALIDATION" for step in service.document["steps"].values()))
        service.mutate("pause", reason="persist migration")
        persisted = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertTrue(all(step["status"] == "NEEDS_REVALIDATION" for step in persisted["steps"].values()))
        self.assertTrue(all(step["result_ref"] == "legacy-result" for step in persisted["steps"].values()))
        self.assertNotIn(Service.load(self.path).check("execution")["state"], ("READY", "DONE"))

    def test_tc_sm_013_legacy_secret_value_is_not_rendered_by_status(self):
        secret = "qa-master-independent-secret-marker"
        url_with_secret = "https://example.invalid/repo?access_token=" + secret
        self._write_legacy_campaign(known={
            "token": {"status": "PROVIDED", "value": secret},
            "gitlab": {"status": "PROVIDED", "value": url_with_secret},
            "requirements": {"status": "CONFIRMED_NONE", "value": None},
        })
        command = [sys.executable, "-m", "qa_master", "--state", str(self.path), "status"]
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn(secret, completed.stdout)
        projection = json.loads(completed.stdout)["known"]
        self.assertEqual(projection["requirements"], {"status": "CONFIRMED_NONE", "value": None})
        self.assertEqual(set(projection["token"]), {"status", "value"})
        self.assertNotEqual(projection["token"]["value"], secret)
        self.assertNotEqual(projection["gitlab"]["value"], url_with_secret)


if __name__ == "__main__":
    unittest.main()
