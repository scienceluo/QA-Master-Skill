import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from qa_master.local_runner import MAX_STREAM_BYTES, RunPermit, TrustedExecutionReceipt, _binding_digest, run_local


class SyntheticTrustedExecutionProvider:
    """Synthetic fixture only; it is not production authorization."""
    def __init__(self, expected_manifest=None, expected_environment=None):
        self.expected_manifest = expected_manifest
        self.expected_environment = expected_environment
        self.last_binding = None

    def verify_execution(self, binding):
        self.last_binding = binding
        if binding["project"] != "demo" or binding["argv"] != [str(Path(sys.executable).resolve()), "-m", "unittest", "discover"]:
            return None
        if self.expected_manifest and binding["source_manifest_sha256"] != self.expected_manifest:
            return None
        if self.expected_environment is not None and binding["environment_bindings"] != self.expected_environment:
            return None
        return TrustedExecutionReceipt("synthetic-test", "receipt-1", _binding_digest(binding), "not-a-production-signature")


class ReplayReceiptProvider:
    """Returns an old receipt to prove changed execution scope is rejected."""
    def __init__(self, binding):
        self.receipt = TrustedExecutionReceipt("synthetic-test", "replayed", _binding_digest(binding), "not-a-production-signature")

    def verify_execution(self, binding):
        return self.receipt


class RunnerIsolationTests(unittest.TestCase):
    def _run(self, source, *, injected_env=None, timeout=60, output_dir=None, provider=None):
        self.directory = tempfile.TemporaryDirectory()
        self.evidence = tempfile.TemporaryDirectory()
        base = Path(self.directory.name).resolve()
        Path(base, "test_runner.py").write_text(source, encoding="utf-8")
        argv = [sys.executable, "-m", "unittest", "discover"]
        permit = RunPermit("demo", tuple(argv), str(base), "synthetic-reviewer", "v1")
        record = run_local("demo", argv, str(base), "v1", permit, output_dir or self.evidence.name, timeout,
                           trusted_execution_provider=provider or SyntheticTrustedExecutionProvider(), injected_env=injected_env)
        return record, Path(record["stdout_path"]).read_text(encoding="utf-8"), Path(record["stderr_path"]).read_text(encoding="utf-8"), base

    def tearDown(self):
        for name in ("directory", "evidence"):
            item = getattr(self, name, None)
            if item:
                item.cleanup()

    def test_parent_environment_is_not_inherited_and_injection_is_explicit(self):
        source = "import os,unittest\nclass T(unittest.TestCase):\n def test_env(self):\n  print(os.getenv('QA_PARENT_ONLY'), os.getenv('QA_INJECTED')); print(os.environ['PATH'])\n"
        with patch.dict(os.environ, {"QA_PARENT_ONLY": "parent-only"}, clear=False):
            record, stdout, _, base = self._run(source, injected_env={"QA_INJECTED": "allowed-value"})
        self.assertEqual(record["process_status"], "PROCESS_SUCCEEDED")
        self.assertIn("None allowed-value", stdout)
        self.assertNotIn("parent-only", stdout)
        self.assertNotIn(str(base), stdout)
        self.assertNotIn(os.pathsep + "." + os.pathsep, stdout)
        self.assertEqual(record["environment"], "SANITIZED_MINIMAL")

    def test_workdir_shadowed_python_is_not_launched(self):
        source = "import unittest\nclass T(unittest.TestCase):\n def test_ok(self): pass\n"
        self.directory = tempfile.TemporaryDirectory()
        self.evidence = tempfile.TemporaryDirectory()
        base = Path(self.directory.name).resolve()
        Path(base, "test_runner.py").write_text(source, encoding="utf-8")
        Path(base, "python.exe").write_text("not an interpreter", encoding="utf-8")
        argv = ["python", "-m", "unittest", "discover"]
        permit = RunPermit("demo", tuple(argv), str(base), "synthetic-reviewer", "v1")
        with patch("qa_master.local_runner.shutil.which", return_value=sys.executable):
            record = run_local("demo", argv, str(base), "v1", permit, self.evidence.name,
                               trusted_execution_provider=SyntheticTrustedExecutionProvider())
        self.assertEqual(record["process_status"], "PROCESS_SUCCEEDED")
        self.assertEqual(record["executed_argv"][0], str(Path(sys.executable).resolve()))
        self.assertNotIn(str(base), [Path(part).resolve().as_posix() for part in record["executed_argv"] if part])

    def test_pytest_addopts_is_not_inherited(self):
        source = "import os,unittest\nclass T(unittest.TestCase):\n def test_env(self):\n  print(os.getenv('PYTEST_ADDOPTS'))\n"
        with patch.dict(os.environ, {"PYTEST_ADDOPTS": "--unexpected-parent-option"}, clear=False):
            _, stdout, _, _ = self._run(source)
        self.assertIn("None", stdout)
        self.assertNotIn("unexpected-parent-option", stdout)

    def test_known_secret_values_are_redacted_before_persistence(self):
        source = "import unittest\nclass T(unittest.TestCase):\n def test_secret(self):\n  print('parent-secret-value')\n"
        with patch.dict(os.environ, {"QA_SECRET_TOKEN": "parent-secret-value"}, clear=False):
            _, stdout, _, _ = self._run(source)
        self.assertNotIn("parent-secret-value", stdout)
        self.assertIn("[REDACTED]", stdout)

    def test_sensitive_environment_injection_is_rejected(self):
        source = "import unittest\nclass T(unittest.TestCase):\n def test_ok(self): pass\n"
        with self.assertRaises(PermissionError):
            self._run(source, injected_env={"SERVICE_TOKEN": "do-not-pass-secrets"})

    def test_secret_command_argument_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as evidence:
            argv = [sys.executable, "-m", "unittest", "--token=do-not-record"]
            permit = RunPermit("demo", tuple(argv), str(Path(directory).resolve()), "synthetic-reviewer", "v1")
            with self.assertRaises(PermissionError):
                run_local("demo", argv, directory, "v1", permit, evidence,
                          trusted_execution_provider=SyntheticTrustedExecutionProvider())

    def test_output_is_bounded_while_process_completes(self):
        source = "import unittest\nclass T(unittest.TestCase):\n def test_output(self):\n  print('x' * 250000)\n"
        record, stdout, _, _ = self._run(source)
        self.assertEqual(record["process_status"], "PROCESS_SUCCEEDED")
        self.assertLessEqual(len(stdout.encode()), MAX_STREAM_BYTES)
        self.assertGreater(record["stdout_truncated_bytes"], 0)

    def test_timeout_terminates_through_isolation_path(self):
        source = "import time,unittest\nclass T(unittest.TestCase):\n def test_wait(self):\n  time.sleep(5)\n"
        from qa_master import local_runner
        with patch("qa_master.local_runner._terminate_process_tree", wraps=local_runner._terminate_process_tree) as terminate:
            record, _, _, _ = self._run(source, timeout=1)
        self.assertEqual(record["process_status"], "TIMEOUT")
        self.assertTrue(record["process_reaped"])
        terminate.assert_called_once()

    def test_workspace_evidence_child_is_rejected_before_creation(self):
        self.directory = tempfile.TemporaryDirectory()
        self.evidence = tempfile.TemporaryDirectory()
        base = Path(self.directory.name).resolve()
        nested = base / "evidence"
        argv = [sys.executable, "-m", "unittest", "discover"]
        permit = RunPermit("demo", tuple(argv), str(base), "synthetic-reviewer", "v1")
        with self.assertRaises(ValueError):
            run_local("demo", argv, str(base), "v1", permit, nested,
                      trusted_execution_provider=SyntheticTrustedExecutionProvider())
        self.assertFalse(nested.exists())

    def test_workspace_tamper_rejects_provider_expected_manifest(self):
        source = "import unittest\nclass T(unittest.TestCase):\n def test_ok(self): pass\n"
        provider = SyntheticTrustedExecutionProvider()
        record, _, _, base = self._run(source, provider=provider)
        self.assertEqual(record["process_status"], "PROCESS_SUCCEEDED")
        Path(base, "test_runner.py").write_text(source + "\n# changed", encoding="utf-8")
        argv = [sys.executable, "-m", "unittest", "discover"]
        permit = RunPermit("demo", tuple(argv), str(base), "synthetic-reviewer", "v1")
        with self.assertRaises(PermissionError):
            run_local("demo", argv, str(base), "v1", permit, self.evidence.name,
                      trusted_execution_provider=SyntheticTrustedExecutionProvider(record["source_manifest_sha256"]))

    def test_same_environment_name_with_different_value_rejects_receipt(self):
        source = "import unittest\nclass T(unittest.TestCase):\n def test_ok(self): pass\n"
        provider = SyntheticTrustedExecutionProvider()
        _, _, _, base = self._run(source, injected_env={"QA_TARGET": "staging"}, provider=provider)
        argv = [sys.executable, "-m", "unittest", "discover"]
        permit = RunPermit("demo", tuple(argv), str(base), "synthetic-reviewer", "v1")
        with self.assertRaises(PermissionError):
            run_local("demo", argv, str(base), "v1", permit, self.evidence.name, injected_env={"QA_TARGET": "production"},
                      trusted_execution_provider=SyntheticTrustedExecutionProvider(expected_environment=provider.last_binding["environment_bindings"]))

    def test_replayed_receipt_rejects_changed_output_path_or_timeout(self):
        source = "import unittest\nclass T(unittest.TestCase):\n def test_ok(self): pass\n"
        provider = SyntheticTrustedExecutionProvider()
        _, _, _, base = self._run(source, provider=provider)
        argv = [sys.executable, "-m", "unittest", "discover"]
        permit = RunPermit("demo", tuple(argv), str(base), "synthetic-reviewer", "v1")
        replay = ReplayReceiptProvider(provider.last_binding)
        with self.assertRaises(PermissionError):
            run_local("demo", argv, str(base), "v1", permit, Path(self.evidence.name).parent / "other-evidence",
                      trusted_execution_provider=replay)
        with self.assertRaises(PermissionError):
            run_local("demo", argv, str(base), "v1", permit, self.evidence.name, timeout=59,
                      trusted_execution_provider=replay)
