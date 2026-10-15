import tempfile,unittest
from pathlib import Path
from qa_master.junit_ingest import ingest_junit,JUnitImportError
from qa_master.release_gate import assess_release
class JUnitTests(unittest.TestCase):
 def load(self,body,mapping=None):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'junit.xml';p.write_text(body,encoding='utf8')
   return ingest_junit(p,mapping if mapping is not None else {('a','ok'):'TC-1'})
 def test_pass(self):self.assertEqual(self.load('<testsuite><testcase classname="a" name="ok"/></testsuite>')['runs'][0]['status'],'PASS')
 def test_failure(self):self.assertEqual(self.load('<testsuite><testcase classname="a" name="ok"><failure/></testcase></testsuite>')['runs'][0]['status'],'FAIL')
 def test_error(self):self.assertEqual(self.load('<testsuite><testcase classname="a" name="ok"><error/></testcase></testsuite>')['runs'][0]['status'],'BLOCKED')
 def test_skip(self):self.assertEqual(self.load('<testsuite><testcase classname="a" name="ok"><skipped/></testcase></testsuite>')['runs'][0]['status'],'SKIPPED')
 def test_unverified(self):self.assertFalse(self.load('<testsuite><testcase classname="a" name="ok"/></testsuite>')['source_verified'])
 def test_unmapped(self):
  with self.assertRaises(JUnitImportError):self.load('<testsuite><testcase name="oops"/></testsuite>')
 def test_duplicate(self):
  with self.assertRaises(JUnitImportError):self.load('<testsuite><testcase classname="a" name="ok"/><testcase classname="a" name="ok"/></testsuite>')
 def test_conflicting(self):
  with self.assertRaises(JUnitImportError):self.load('<testsuite><testcase classname="a" name="ok"><skipped/><failure/></testcase></testsuite>')
 def test_doctype(self):
  with self.assertRaises(JUnitImportError):self.load('<!DOCTYPE testsuite><testsuite><testcase classname="a" name="ok"/></testsuite>')
 def test_utf16_doctype_is_rejected_before_parse(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'junit.xml';path.write_bytes('<!DOCTYPE testsuite><testsuite><testcase classname="a" name="ok"/></testsuite>'.encode('utf-16'))
   with self.assertRaises(JUnitImportError):ingest_junit(path,{('a','ok'):'TC-1'})
 def test_namespaced_failure_cannot_be_misclassified_as_pass(self):
  with self.assertRaises(JUnitImportError):self.load('<testsuite xmlns="urn:test"><testcase classname="a" name="ok"><failure/></testcase></testsuite>')
 def test_empty(self):
  with self.assertRaises(JUnitImportError):self.load('<testsuite/>')
 def test_bad_root(self):
  with self.assertRaises(JUnitImportError):self.load('<root><testcase classname="a" name="ok"/></root>')
 def test_bad_xml(self):
  with self.assertRaises(JUnitImportError):self.load('<testsuite>')
 def test_release_gate_blocks_failure(self):
  x=self.load('<testsuite><testcase classname="a" name="ok"><failure/></testcase></testsuite>')
  r=assess_release([{'id':'TC-1'}],x['runs'],defects=[],approved_case_ids={'TC-1'})
  self.assertEqual(r.decision,'BLOCKED')
 def test_evidence_digest(self):
  x=self.load('<testsuite><testcase classname="a" name="ok"/></testsuite>')
  self.assertIn(x['source_sha256'],x['runs'][0]['evidence'])

 def test_unverified_pass_blocks_release(self):
  x=self.load('<testsuite><testcase classname="a" name="ok"/></testsuite>')
  r=assess_release([{'id':'TC-1'}],x['runs'],defects=[],approved_case_ids={'TC-1'})
  self.assertIn('UNVERIFIED_SOURCE:TC-1',r.reasons)
