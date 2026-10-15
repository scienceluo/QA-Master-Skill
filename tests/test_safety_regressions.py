"""Independent safety regressions. Synthetic callbacks prove only local control flow."""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError

from qa_master.api_codegen import generate_pytest
from qa_master.approval import artifact_digest
from qa_master.ci_artifacts import ArtifactError, fetch_job_junit
from qa_master.ci_attestation import ExpectedRun
from qa_master.enterprise import ReadOnlyConnector
from qa_master.gitlab_adapter import GitLabError, GitLabReader
from qa_master.http_transport import read_bytes
from qa_master.intent import plan_task
from qa_master.release_gate import assess_release
from qa_master.workflow import VerifiedCompletionReceipt, Workflow


SHA = "a" * 40
CASE = {"method": "GET", "path": "/health", "expected_statuses": [200], "approved": True}


class _Redirect(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(302)
        self.send_header("Location", "/redirect-target")
        self.end_headers()

    def log_message(self, format, *args):
        return


class _RedirectServer:
    def __enter__(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Redirect)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return "http://127.0.0.1:" + str(self.server.server_port)

    def __exit__(self, exc_type, exc, tb):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()


class _CiReader:
    token = None

    def __init__(self, origin):
        self.origin = origin

    def project(self, project):
        return {"id": 1}

    def job(self, project, job):
        return {"id": 2, "status": "success", "pipeline": {"id": 3}, "commit": {"id": SHA}, "environment": {"name": "staging"}}

    def pipeline(self, project, pipeline):
        return {"id": 3, "sha": SHA, "ref": "main", "status": "success", "ref_protected": True}


class SafetyRegressionTests(unittest.TestCase):
    def test_design_only_defaults_to_no_execution_and_no_external_writes(self):
        plan = plan_task("只生成测试用例")
        self.assertEqual(plan["stages"], ["design"])
        self.assertTrue(plan["no_execution"])
        self.assertTrue(plan["no_external_writes"])

    def test_design_only_cli_persists_denial_after_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            state = os.path.join(directory, "state.json")
            command = [sys.executable, "-m", "qa_master", "--state", state]
            for args in (("init", "demo"), ("answer", "gitlab", "group/repo")):
                result = subprocess.run(command + list(args), capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            planned = subprocess.run(command + ["plan", "只生成测试用例"], capture_output=True, text=True)
            self.assertEqual(planned.returncode, 0, planned.stderr)
            contract = json.loads(planned.stdout)["task_contract"]
            self.assertEqual(contract["authority"], "PLANNING_ONLY")
            self.assertFalse(contract["capabilities"]["execute"])
            self.assertFalse(contract["capabilities"]["external_write"])
            reloaded = subprocess.run(command + ["check", "execution"], capture_output=True, text=True)
            self.assertEqual(reloaded.returncode, 0, reloaded.stderr)
            self.assertEqual(json.loads(reloaded.stdout)["state"], "DENIED_BY_TASK_SCOPE")

    def test_release_without_host_verifier_fails_closed(self):
        assessment = assess_release([{"id": "TC-1"}], [{"case_id": "TC-1", "status": "PASS", "evidence": "artifact://1"}], defects=[], approved_case_ids={"TC-1"})
        self.assertEqual(assessment.decision, "BLOCKED")
        self.assertIn("UNVERIFIED_SOURCE:TC-1", assessment.reasons)
        self.assertIn("NO_EVIDENCED_PASS", assessment.reasons)

    def test_release_rejecting_host_verifier_fails_closed_for_arbitrary_provenance(self):
        assessment = assess_release(
            [{"id": "TC-1"}],
            [{"case_id": "TC-1", "status": "PASS", "evidence": "artifact://1", "provenance": "ARBITRARY_CALLER_STRING"}],
            defects=[], approved_case_ids={"TC-1"}, evidence_verifier=lambda record: False,
            governance_verifier=lambda kind, record: True,
        )
        self.assertEqual(assessment.decision, "BLOCKED")
        self.assertIn("UNVERIFIED_SOURCE:TC-1", assessment.reasons)

    def test_release_host_verifier_exception_fails_closed(self):
        def failing_host_verifier(record):
            raise RuntimeError("synthetic host failure")

        assessment = assess_release(
            [{"id": "TC-1"}],
            [{"case_id": "TC-1", "status": "PASS", "evidence": "artifact://1", "provenance": "HOST_DECLARED"}],
            defects=[], approved_case_ids={"TC-1"}, evidence_verifier=failing_host_verifier,
            governance_verifier=lambda kind, record: True,
        )
        self.assertEqual(assessment.decision, "BLOCKED")
        self.assertIn("UNVERIFIED_SOURCE:TC-1", assessment.reasons)

    def test_answer_change_invalidates_completed_side_effect_step_and_approval(self):
        workflow = Workflow("demo")
        workflow.request(["test_plan"])
        workflow.answer("source", "spec")
        workflow.complete("requirements", "req")
        workflow.complete("review", "review")
        workflow.approve("requirements", "r1", "demo")
        workflow.complete("baseline", "baseline")
        workflow.complete("design", "cases")
        workflow.approve("cases", "c1", "demo")
        workflow.complete("case_review", "case-review")
        for key in ("jira_project", "plan_name", "cycle_name"):
            workflow.answer(key, key + "-one")
        artifact = {"cases": ["TC-1"]}
        workflow.approve_exact("test_plan", "demo", artifact, "synthetic-reviewer")

        def synthetic_receipt_verifier(receipt, binding):
            # This checks local binding propagation only; it is not production authorization.
            if receipt != "synthetic-test-receipt" or binding["step"] != "test_plan" or binding["project"] != "demo":
                return None
            return VerifiedCompletionReceipt("fixture-plan-result", "synthetic-test-host",
                "2026-10-14T00:00:00Z", "2026-10-14T01:00:00Z", artifact_digest(binding), "plan-result")

        workflow.complete_exact("test_plan", "plan-result", {"test_plan": artifact}, {"test_plan": "demo"},
                                receipt="synthetic-test-receipt", verifier=synthetic_receipt_verifier)
        self.assertEqual(workflow.steps["test_plan"].status, "DONE")
        workflow.answer("plan_name", "plan_name-two")
        self.assertEqual(workflow.steps["test_plan"].status, "PENDING")
        self.assertNotIn("test_plan", workflow.approvals)

    def test_mutation_flags_require_exact_boolean_true(self):
        for value in ("true", 1, False, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                generate_pytest([dict(CASE, method="POST", allow_mutation=value)])

    def test_generated_api_test_without_host_fixture_never_calls_request(self):
        calls = []
        fake_pytest = SimpleNamespace(mark=SimpleNamespace(parametrize=lambda *args: lambda function: function))
        fake_requests = SimpleNamespace(request=lambda *args, **kwargs: calls.append((args, kwargs)))
        source = generate_pytest([CASE])
        namespace = {"__name__": "synthetic_generated_test", "__file__": "synthetic-generated.py"}
        with patch.dict(sys.modules, {"pytest": fake_pytest, "requests": fake_requests}):
            exec(source, namespace)
        with patch.dict(os.environ, {"QA_EXECUTION_APPROVED": "YES", "QA_TARGET_URL": "https://api.example"}, clear=False):
            with self.assertRaises(PermissionError):
                namespace["test_approved_api_scenario"](namespace["SCENARIOS"][0], lambda binding: False)
        self.assertEqual(calls, [])

    def test_local_redirect_server_is_rejected_by_all_read_paths(self):
        with _RedirectServer() as origin:
            with self.assertRaises(HTTPError):
                read_bytes(origin + "/raw", {}, limit=1024)
            with self.assertRaises(GitLabError):
                GitLabReader(origin, allow_http=True).project(1)
            with self.assertRaises(HTTPError):
                ReadOnlyConnector._http(origin + "/enterprise", {})
            with self.assertRaises(ArtifactError):
                fetch_job_junit(_CiReader(origin), ExpectedRun(1, 2, 3, SHA, "main", "staging"), {("a", "ok"): "TC-1"}, junit_entry="reports/result.xml")

