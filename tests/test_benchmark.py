import json
import subprocess
import sys
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path

from qa_master.benchmark import BenchmarkError, RUBRIC_DIMENSIONS, evaluate_pair, load_scenarios


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "benchmarks" / "scenarios.json"
INITIAL_MANIFEST = ROOT / "benchmarks" / "manifest.json"


def submission(participant, scenario_hash, scenario_ids, *, model="model-x", settings=None):
    settings = {"temperature": 0} if settings is None else settings
    rubric = {
        dimension: {"score": 3, "rationale": f"human rationale for {dimension}", "evidence_ref": "review://local/1"}
        for dimension in RUBRIC_DIMENSIONS
    }
    return {
        "schema_version": 1,
        "participant_id": participant,
        "participant_version": "1.0-test",
        "model": model,
        "settings": settings,
        "scenario_set_sha256": scenario_hash,
        "responses": [
            {"scenario_id": scenario_id, "behavioral_output": f"actual response for {scenario_id}", "rubric": rubric}
            for scenario_id in scenario_ids
        ],
    }


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.scenarios, self.scenario_hash = load_scenarios(SCENARIOS)
        self.identifiers = [scenario["id"] for scenario in self.scenarios]

    def write_pair(self, directory, left=None, right=None):
        left_path = Path(directory) / "left.json"
        right_path = Path(directory) / "right.json"
        left_path.write_text(json.dumps(left or submission("qa-master", self.scenario_hash, self.identifiers)), encoding="utf-8")
        right_path.write_text(json.dumps(right or submission("comparison-target", self.scenario_hash, self.identifiers)), encoding="utf-8")
        return left_path, right_path

    def test_original_scenario_set_and_initial_manifest_are_not_executed(self):
        self.assertGreaterEqual(len(self.scenarios), 12)
        titles = {scenario["title"] for scenario in self.scenarios}
        self.assertEqual(len(titles), len(self.scenarios))
        initial = json.loads(INITIAL_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(initial["scenario_set_sha256"], self.scenario_hash)
        self.assertEqual(initial["measurement_status"], "NOT_EXECUTED")
        self.assertEqual(initial["claim_status"], "NOT_ASSERTED")
        self.assertEqual(len(initial["participants"]), 2)
        for participant in initial["participants"]:
            self.assertEqual(len(participant["responses"]), len(self.scenarios))
            self.assertTrue(all(row["status"] == "NOT_EXECUTED" and row["behavioral_output"] is None for row in participant["responses"]))

    def test_complete_pair_preserves_actual_outputs_and_never_claims_superiority(self):
        with tempfile.TemporaryDirectory() as directory:
            left, right = self.write_pair(directory)
            result = evaluate_pair(SCENARIOS, left, right, model="model-x", settings={"temperature": 0})
            self.assertEqual(result["measurement_status"], "MEASURED_PAIRED_SUBMITTED_UNVERIFIED")
            self.assertEqual(result["claim_status"], "HUMAN_REVIEW_REQUIRED")
            self.assertIn("No superiority assertion", result["claim"])
            self.assertEqual(result["participants"][0]["artifact_sha256"], sha256(left.read_bytes()).hexdigest())
            self.assertEqual(len(result["participants"][1]["responses"]), len(self.scenarios))

    def test_rejects_input_model_settings_and_dimension_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            bad_hash = submission("qa-master", "0" * 64, self.identifiers)
            left, right = self.write_pair(directory, left=bad_hash)
            with self.assertRaises(BenchmarkError):
                evaluate_pair(SCENARIOS, left, right, model="model-x", settings={"temperature": 0})
            wrong_model = submission("qa-master", self.scenario_hash, self.identifiers, model="other")
            left, right = self.write_pair(directory, left=wrong_model)
            with self.assertRaises(BenchmarkError):
                evaluate_pair(SCENARIOS, left, right, model="model-x", settings={"temperature": 0})
            wrong_settings = submission("qa-master", self.scenario_hash, self.identifiers, settings={"temperature": 1})
            left, right = self.write_pair(directory, left=wrong_settings)
            with self.assertRaises(BenchmarkError):
                evaluate_pair(SCENARIOS, left, right, model="model-x", settings={"temperature": 0})
            incomplete = submission("qa-master", self.scenario_hash, self.identifiers)
            del incomplete["responses"][0]["rubric"]["coverage"]
            left, right = self.write_pair(directory, left=incomplete)
            with self.assertRaises(BenchmarkError):
                evaluate_pair(SCENARIOS, left, right, model="model-x", settings={"temperature": 0})

    def test_rejects_missing_or_duplicate_side_and_cli_writes_result(self):
        with tempfile.TemporaryDirectory() as directory:
            duplicate = submission("qa-master", self.scenario_hash, self.identifiers)
            left, right = self.write_pair(directory, right=duplicate)
            with self.assertRaises(BenchmarkError):
                evaluate_pair(SCENARIOS, left, right, model="model-x", settings={"temperature": 0})
            result_path = Path(directory) / "result.json"
            good_left, good_right = self.write_pair(directory)
            command = [
                sys.executable, "-m", "qa_master.benchmark", "--scenarios", str(SCENARIOS),
                "--left", str(good_left), "--right", str(good_right), "--model", "model-x",
                "--settings", '{"temperature": 0}', "--output", str(result_path),
            ]
            process = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(json.loads(result_path.read_text(encoding="utf-8"))["claim_status"], "HUMAN_REVIEW_REQUIRED")
            process = subprocess.run(command[:-6], capture_output=True, text=True, check=False)
            self.assertNotEqual(process.returncode, 0)
