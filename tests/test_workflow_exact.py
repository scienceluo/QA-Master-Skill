import tempfile,unittest
from pathlib import Path
from qa_master.workflow import Workflow

class WorkflowExactApprovalTests(unittest.TestCase):
 def ready_baseline(self):
  w=Workflow('project-x');w.request(['baseline'])
  w.answer('source','spec-v1');w.complete('requirements','req.json')
  w.complete('review','review.json')
  return w
 def test_exact_approval(self):
  w=self.ready_baseline();artifact={'requirements':['R1']}
  w.approve_exact('requirements','project-x/release-a',artifact,'reviewer')
  self.assertEqual(w.evaluate_exact('baseline',{'requirements':artifact},{'requirements':'project-x/release-a'}),'READY')
  w.complete_exact('baseline','baseline.json',{'requirements':artifact},{'requirements':'project-x/release-a'})
  self.assertEqual(w.steps['baseline'].status,'DONE')
 def test_changed_document_blocks(self):
  w=self.ready_baseline();w.approve_exact('requirements','release-a',{'requirements':['R1']},'reviewer')
  self.assertEqual(w.evaluate_exact('baseline',{'requirements':{'requirements':['R2']}},{'requirements':'release-a'}),'WAITING_APPROVAL')
 def test_completed_baseline_becomes_stale_when_requirement_changes(self):
  w=self.ready_baseline();artifact={'requirements':['R1']};scopes={'requirements':'release-a'}
  w.approve_exact('requirements','release-a',artifact,'reviewer')
  w.complete_exact('baseline','baseline.json',{'requirements':artifact},scopes)
  self.assertEqual(w.evaluate_exact('baseline',{'requirements':{'requirements':['R2']}},scopes),'STALE')
  self.assertEqual(w.steps['baseline'].status,'PENDING')
  self.assertNotIn('requirements',w.approvals)
 def test_downstream_answer_and_approval_do_not_stale_completed_baseline(self):
  w=self.ready_baseline();artifact={'requirements':['R1']};scopes={'requirements':'release-a'}
  w.approve_exact('requirements','release-a',artifact,'reviewer')
  w.complete_exact('baseline','baseline.json',{'requirements':artifact},scopes)
  w.answer('plan_name','downstream-plan')
  w.approve('cases','cases-v2','downstream-scope')
  self.assertEqual(w.evaluate_exact('baseline',{'requirements':artifact},scopes),'DONE')
 def test_legacy_approval_fails_closed(self):
  w=self.ready_baseline();w.approve('requirements','v1','release-a')
  self.assertEqual(w.evaluate_exact('baseline',{'requirements':{'v':1}},{'requirements':'release-a'}),'WAITING_APPROVAL')
 def test_recovery_rechecks(self):
  w=self.ready_baseline();artifact={'requirements':['R1']}
  w.approve_exact('requirements','release-a',artifact,'reviewer')
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'state.json';w.complete_exact('baseline','baseline.json',{'requirements':artifact},{'requirements':'release-a'});w.save(path);recovered=Workflow.load(path)
   self.assertEqual(recovered.evaluate_exact('baseline',{'requirements':artifact},{'requirements':'release-a'}),'DONE')
   self.assertEqual(recovered.evaluate_exact('baseline',{'requirements':{'requirements':['R2']}},{'requirements':'release-a'}),'STALE')
   self.assertEqual(recovered.steps['baseline'].status,'PENDING')
 def test_denied_completion(self):
  w=self.ready_baseline();w.approve_exact('requirements','release-a',{'x':1},'reviewer')
  with self.assertRaises(PermissionError):w.complete_exact('baseline','ref',{'requirements':{'x':2}},{'requirements':'release-a'})
