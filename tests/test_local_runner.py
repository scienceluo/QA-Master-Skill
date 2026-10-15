import sys
import tempfile
import unittest
from pathlib import Path

from qa_master.local_runner import RunPermit, TrustedExecutionReceipt, _binding_digest, run_local


class SyntheticTrustedExecutionProvider:
    """Synthetic fixture only; it is not a production trust provider."""
    def verify_execution(self, binding):
        if binding["project"] != "demo" or binding["artifact_version"] != "v1":
            return None
        return TrustedExecutionReceipt("synthetic-test", "receipt-1", _binding_digest(binding), "not-a-production-signature")


class LocalRunnerTests(unittest.TestCase):
    def run_case(self, code, **kwargs):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as evidence:
            base = str(Path(directory).resolve())
            Path(directory, "test_dummy.py").write_text(code, encoding="utf-8")
            argv = [sys.executable, "-m", "unittest", "discover"]
            permit = RunPermit("demo", tuple(argv), base, "synthetic-reviewer", "v1")
            record = run_local("demo", argv, base, "v1", permit, evidence,
                               trusted_execution_provider=SyntheticTrustedExecutionProvider(), **kwargs)
            return record

    def test_success_with_system_python(self):
        record = self.run_case("import unittest\nclass T(unittest.TestCase):\n def test_a(self):self.assertTrue(True)\n")
        self.assertEqual(record["process_status"], "PROCESS_SUCCEEDED")

    def test_failure(self):
        record = self.run_case("import unittest\nclass T(unittest.TestCase):\n def test_a(self):self.assertTrue(False)\n")
        self.assertEqual(record["process_status"], "PROCESS_FAILED")

    def test_no_business_pass(self):
        self.assertEqual(self.run_case("")["business_result"], "NOT_ASSESSED")

    def test_missing_trusted_verifier_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as evidence:
            base = str(Path(directory).resolve())
            argv = [sys.executable, "-m", "unittest", "discover"]
            permit = RunPermit("demo", tuple(argv), base, "reviewer", "v1")
            with self.assertRaises(PermissionError):
                run_local("demo", argv, base, "v1", permit, evidence)

    def test_command_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            argv = [sys.executable, "-m", "unittest"]
            permit = RunPermit("demo", tuple(argv), str(Path(directory).resolve()), "reviewer", "v1")
            with self.assertRaises(PermissionError):
                run_local("demo", [sys.executable, "-m", "pytest"], directory, "v1", permit, directory + "-e",
                          trusted_execution_provider=SyntheticTrustedExecutionProvider())

    def test_shell_and_arbitrary_python_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            permit = RunPermit("demo", ("bash", "-c", "true"), str(Path(directory).resolve()), "reviewer", "v1")
            with self.assertRaises(PermissionError):
                run_local("demo", ["bash", "-c", "true"], directory, "v1", permit, directory + "-e",
                          trusted_execution_provider=SyntheticTrustedExecutionProvider())
            argv = [sys.executable, "-c", "print(1)"]
            permit = RunPermit("demo", tuple(argv), str(Path(directory).resolve()), "reviewer", "v1")
            with self.assertRaises(PermissionError):
                run_local("demo", argv, directory, "v1", permit, directory + "-e",
                          trusted_execution_provider=SyntheticTrustedExecutionProvider())

    def test_timeout_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            argv = [sys.executable, "-m", "unittest"]
            permit = RunPermit("demo", tuple(argv), str(Path(directory).resolve()), "reviewer", "v1")
            with self.assertRaises(ValueError):
                run_local("demo", argv, directory, "v1", permit, directory + "-e", timeout=0,
                          trusted_execution_provider=SyntheticTrustedExecutionProvider())

    def test_version_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            argv = [sys.executable, "-m", "unittest"]
            permit = RunPermit("demo", tuple(argv), str(Path(directory).resolve()), "reviewer", "v1")
            with self.assertRaises(PermissionError):
                permit.verify("demo", argv, str(Path(directory).resolve()), "v2")
