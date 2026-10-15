import json
import tempfile
import threading
import unittest
from dataclasses import asdict
from pathlib import Path

from qa_master.core import Campaign, load as load_campaign, save as save_campaign
from qa_master.state_store import StateConflictError, save_document
from qa_master.workflow import Workflow


class StateStoreTests(unittest.TestCase):
    def test_campaign_save_load_revisions_and_rejects_stale_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "campaign.json"
            first = Campaign("demo")
            save_campaign(first, path)
            self.assertEqual(first.revision, 1)
            left, right = load_campaign(path), load_campaign(path)
            left.set_answer("requirements", "R1")
            save_campaign(left, path)
            self.assertEqual(left.revision, 2)
            right.set_answer("requirements", "R2")
            with self.assertRaises(StateConflictError):
                save_campaign(right, path)
            self.assertEqual(load_campaign(path).known["requirements"]["value"], "R1")

    def test_workflow_legacy_migrates_and_new_state_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workflow.json"
            legacy = Workflow("legacy")
            legacy.request(["requirements"])
            raw = asdict(legacy)
            raw.pop("revision")
            path.write_text(json.dumps(raw), encoding="utf-8")
            recovered = Workflow.load(path)
            self.assertEqual(recovered.revision, 0)
            recovered.save(path)
            self.assertEqual(recovered.revision, 1)
            fresh = Workflow("new")
            with self.assertRaises(StateConflictError):
                fresh.save(path)

    def test_concurrent_same_revision_has_one_winner_and_no_fixed_temp_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            save_document(path, {"value": "initial"}, expected_revision=0)
            barrier = threading.Barrier(2)
            outcomes = []

            def writer(value):
                barrier.wait()
                try:
                    save_document(path, {"value": value}, expected_revision=1)
                    outcomes.append("saved")
                except StateConflictError:
                    outcomes.append("conflict")

            threads = [threading.Thread(target=writer, args=(value,)) for value in ("left", "right")]
            for thread in threads: thread.start()
            for thread in threads: thread.join()
            self.assertCountEqual(outcomes, ["saved", "conflict"])
            self.assertFalse(list(Path(directory).glob(".qa-master-state-*.json")))
