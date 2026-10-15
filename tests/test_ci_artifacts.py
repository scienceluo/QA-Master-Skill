import io,unittest,zipfile
from unittest.mock import patch
from qa_master.ci_artifacts import fetch_job_junit,ArtifactError
from qa_master.ci_attestation import ExpectedRun
SHA='a'*40
XML=b'<testsuite><testcase classname="a" name="ok"/></testsuite>'
class Reader:
 origin='https://git.example'
 token='test-token'
 def project(self,p):return {'id':1}
 def job(self,p,j):return {'id':2,'status':'success','ref':'main','tag':False,'pipeline':{'id':3},'commit':{'id':SHA},'environment':{'name':'staging'}}
 def pipeline(self,p,i):return {'id':3,'sha':SHA,'ref':'main','status':'success'}
 def protected_branches(self,p):return [{'name':'main'}]
 def protected_tags(self,p):return []
def zipped(filename='reports/result.xml',content=XML):
 b=io.BytesIO()
 with zipfile.ZipFile(b,'w') as z:z.writestr(filename,content)
 return b.getvalue()
class ArtifactTests(unittest.TestCase):
 def run_artifact(self,blob=None,**kwargs):
  return fetch_job_junit(Reader(),ExpectedRun(1,2,3,SHA,'main','staging'),{('a','ok'):'TC-1'},junit_entry=kwargs.pop('junit_entry','reports/result.xml'),artifact_transport=lambda *args: zipped() if blob is None else blob,**kwargs)
 def test_read_and_bind(self):
  v=self.run_artifact();self.assertEqual(v['runs'][0]['status'],'PASS');self.assertFalse(v['source_authenticated'])
 def test_injected_transport_is_not_claimed_as_job_api_download(self):
  v=self.run_artifact()
  self.assertFalse(v['artifact_downloaded_from_job_api']);self.assertEqual(v['transport_kind'],'injected')
  self.assertEqual(v['manifest_origin'],'OBSERVED_ARTIFACT_NOT_APPROVED_BASELINE');self.assertFalse(v['raw_artifact_retained'])
 def test_builtin_transport_is_identified_without_trusting_artifact(self):
  with patch('qa_master.ci_artifacts.read_bytes',return_value=zipped()):
   v=fetch_job_junit(Reader(),ExpectedRun(1,2,3,SHA,'main','staging'),{('a','ok'):'TC-1'},junit_entry='reports/result.xml')
  self.assertTrue(v['artifact_downloaded_from_job_api']);self.assertEqual(v['transport_kind'],'builtin_https')
  self.assertEqual(v['manifest_origin'],'OBSERVED_ARTIFACT_NOT_APPROVED_BASELINE');self.assertFalse(v['source_authenticated'])
 def test_zip_hash(self):self.assertEqual(len(self.run_artifact()['archive_sha256']),64)
 def test_not_trusted(self):self.assertEqual(self.run_artifact()['runs'][0]['provenance'],'UNVERIFIED_EXTERNAL_ARTIFACT')
 def test_wrong_entry(self):
  with self.assertRaises(ArtifactError):self.run_artifact(blob=zipped('else.xml'))
 def test_bad_zip(self):
  with self.assertRaises(ArtifactError):self.run_artifact(blob=b'nothing')
 def test_large_zip(self):
  with self.assertRaises(ArtifactError):self.run_artifact(blob=zipped(),max_zip_bytes=5)
 def test_large_xml(self):
  with self.assertRaises(ArtifactError):self.run_artifact(max_xml_bytes=5)
 def test_entry_traversal(self):
  with self.assertRaises(ArtifactError):self.run_artifact(junit_entry='../escape.xml')
 def test_unmapped(self):
  with self.assertRaises(ValueError):fetch_job_junit(Reader(),ExpectedRun(1,2,3,SHA,'main','staging'),{},junit_entry='reports/result.xml',artifact_transport=lambda *args:zipped())
 def test_bad_metadata(self):
  with self.assertRaises(ArtifactError):fetch_job_junit(Reader(),ExpectedRun(1,2,3,'b'*40,'main','staging'),{('a','ok'):'TC-1'},junit_entry='reports/result.xml',artifact_transport=lambda *args:zipped())
