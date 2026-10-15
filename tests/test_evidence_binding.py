import hashlib,tempfile,unittest
from pathlib import Path
from dataclasses import replace
from qa_master.junit_ingest import ingest_junit
from qa_master.evidence_binding import RunManifest,bind_junit
from qa_master.release_gate import assess_release
XML=b'<testsuite><testcase classname="t" name="ok"/></testsuite>'
class BindingTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.path=Path(self.temp.name)/'result.xml';self.path.write_bytes(XML)
  self.report=ingest_junit(self.path,{('t','ok'):'TC1'})
  self.manifest=RunManifest('demo','sha123','staging','run42',hashlib.sha256(XML).hexdigest(),('TC1',))
 def test_bind(self):
  r=bind_junit(self.report,self.manifest,str(self.path),case_map={('t','ok'):'TC1'})
  self.assertTrue(r['manifest_validated']);self.assertFalse(r['source_authenticated'])
 def test_mismatch_content(self):
  self.path.write_bytes(XML+b' ')
  with self.assertRaises(ValueError):bind_junit(self.report,self.manifest,str(self.path),case_map={('t','ok'):'TC1'})
 def test_mismatch_manifest(self):
  with self.assertRaises(ValueError):bind_junit(self.report,replace(self.manifest,junit_sha256='0'*64),str(self.path),case_map={('t','ok'):'TC1'})
 def test_mismatch_case(self):
  with self.assertRaises(ValueError):bind_junit(self.report,replace(self.manifest,approved_case_ids=('OTHER',)),str(self.path),case_map={('t','ok'):'TC1'})
 def test_bad_scope(self):
  with self.assertRaises(ValueError):bind_junit(self.report,replace(self.manifest,project=''),str(self.path),case_map={('t','ok'):'TC1'})
 def test_invalid_hash(self):
  with self.assertRaises(ValueError):bind_junit(self.report,replace(self.manifest,junit_sha256='abc'),str(self.path),case_map={('t','ok'):'TC1'})
 def test_duplicate_case(self):
  with self.assertRaises(ValueError):bind_junit(self.report,replace(self.manifest,approved_case_ids=('TC1','TC1')),str(self.path),case_map={('t','ok'):'TC1'})
 def test_caller_boolean_not_trust(self):
  self.assertFalse(bind_junit(self.report,self.manifest,str(self.path),case_map={('t','ok'):'TC1'},verified_source=True)['source_authenticated'])
 def test_release_still_blocked(self):
  runs=bind_junit(self.report,self.manifest,str(self.path),case_map={('t','ok'):'TC1'})['runs']
  assessment=assess_release([{'id':'TC1'}],runs,defects=[],approved_case_ids={'TC1'})
  self.assertIn('UNVERIFIED_SOURCE:TC1',assessment.reasons)
 def test_mutated_caller_status_is_rejected_after_raw_reparse(self):
  self.report['runs'][0]['status']='PASS' if self.report['runs'][0]['status']!='PASS' else 'FAIL'
  with self.assertRaises(ValueError):bind_junit(self.report,self.manifest,str(self.path),case_map={('t','ok'):'TC1'})
