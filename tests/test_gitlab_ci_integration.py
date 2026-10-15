import io
import unittest
import zipfile

from qa_master.ci_artifacts import fetch_job_junit
from qa_master.ci_attestation import ExpectedRun, assess_ci_job
from qa_master.gitlab_adapter import GitLabReader
from qa_master.release_gate import assess_release

SHA="a" * 40

def junit_zip():
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,"w") as archive:
        archive.writestr("reports/junit.xml",'<testsuite><testcase classname="api" name="health"/></testsuite>')
    return stream.getvalue()

class GitLabCiIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        def transport(url,headers):
            self.calls.append((url,headers))
            if url.endswith("/protected_branches"):return [{"name":"main"}]
            if url.endswith("/protected_tags"):return []
            if "/jobs/2" in url:return {"id":2,"status":"success","ref":"main","tag":False,"pipeline":{"id":3},"commit":{"id":SHA},"environment":{"name":"staging"}}
            if "/pipelines/3" in url:return {"id":3,"sha":SHA,"ref":"main","status":"success"}
            return {"id":1,"path_with_namespace":"group/project","default_branch":"main","web_url":"https://git.example/group/project"}
        self.reader=GitLabReader("https://git.example","test-token",transport=transport)
        self.expected=ExpectedRun(1,2,3,SHA,"main","staging")

    def test_reader_metadata_artifact_binding_and_release_gate_remain_untrusted(self):
        report=assess_ci_job(self.reader,self.expected)
        self.assertTrue(report["metadata_matches"])
        bound=fetch_job_junit(self.reader,self.expected,{("api","health"):"TC-1"},junit_entry="reports/junit.xml",artifact_transport=lambda *args:junit_zip())
        self.assertFalse(bound["source_authenticated"])
        result=assess_release([{ "id":"TC-1"}],bound["runs"],defects=[],approved_case_ids={"TC-1"},evidence_verifier=lambda row:True)
        self.assertIn("UNVERIFIED_SOURCE:TC-1",result.reasons)
        self.assertTrue(any("protected_branches" in url for url,_ in self.calls))

    def test_protection_mismatch_rejects_before_artifact_download(self):
        original=self.reader.transport
        self.reader.transport=lambda url,headers: [] if url.endswith("/protected_branches") else original(url,headers)
        report=assess_ci_job(self.reader,self.expected)
        self.assertFalse(report["metadata_matches"])
        self.assertIn("PROTECTED_BRANCH_NOT_CONFIRMED",report["reasons"])
