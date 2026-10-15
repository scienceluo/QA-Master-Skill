import tempfile
import unittest
from pathlib import Path

from qa_master.skill_registry import bundled_skill_root, discover_skills, select_skills


class SkillRegistryTests(unittest.TestCase):
    def test_package_resources_contain_canonical_guides(self):
        result = discover_skills()
        self.assertEqual(result["status"], "DISCOVERED")
        self.assertGreaterEqual(len(result["guides"]), 6)
        self.assertFalse([gap for gap in result["gaps"] if gap["code"] == "GUIDE_FILE_MISSING"])
        self.assertTrue(str(bundled_skill_root()))

    def test_api_design_returns_exact_existing_artifact(self):
        result = select_skills(intent="design", dimensions=["api"], risk="high")
        self.assertEqual(result["status"], "PLANNING_ONLY")
        self.assertEqual(result["execution"], "NOT_EXECUTED")
        self.assertEqual([guide["id"] for guide in result["selected"]], ["functional-api-design"])
        self.assertTrue(Path(result["selected"][0]["path"]).is_file())
        self.assertIn("api-contract-matrix", result["selected"][0]["artifacts"])

    def test_unknown_dimension_is_explicit_gap(self):
        result = select_skills(dimensions=["telepathy"])
        self.assertEqual(result["selected"], [])
        self.assertIn("UNKNOWN_DIMENSION", [gap["code"] for gap in result["gaps"]])

    def test_missing_required_file_is_reported_not_invented(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = discover_skills(root)
        self.assertEqual(result["guides"], [])
        self.assertIn("GUIDE_FILE_MISSING", [gap["code"] for gap in result["gaps"]])

    def test_invalid_metadata_cannot_be_selected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bad.md").write_text("---\nid: bad\ndimensions: imaginary\n---\n", encoding="utf-8")
            result = select_skills(dimensions=["functional"], root=root)
        self.assertEqual(result["selected"], [])
        self.assertIn("GUIDE_METADATA_INVALID", [gap["code"] for gap in result["gaps"]])

    def test_unmatched_request_remains_planning_only(self):
        result = select_skills(intent="execution", dimensions=["security"], risk="low")
        self.assertEqual(result["execution"], "NOT_EXECUTED")
        self.assertIn("NO_MATCHING_BUNDLED_GUIDE", [gap["code"] for gap in result["gaps"]])
