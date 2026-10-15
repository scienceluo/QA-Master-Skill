import tempfile,unittest
from pathlib import Path
from qa_master.approval import artifact_digest
from qa_master.workflow import VerifiedCompletionReceipt, Workflow

def synthetic_receipt_verifier(receipt,binding):
 # Test-only host fixture. It is not a production approval or authenticated receipt.
 if not (receipt=='synthetic-test-receipt' and binding['project']=='project' and
         binding['step']=='test_plan' and binding['result_ref']=='dry-run-result'):
  return None
 return VerifiedCompletionReceipt('fixture-dry-run','synthetic-test-host',
  '2026-10-14T00:00:00Z','2026-10-14T01:00:00Z',artifact_digest(binding),'dry-run-result')

class SideEffectGateTests(unittest.TestCase):
 def ready_plan(self):
  w=Workflow('project')
  w.request(['test_plan'])
  w.answer('source','spec')
  w.complete('requirements','req')
  w.complete('review','review')
  w.approve('requirements','r1','project')
  w.complete('baseline','baseline')
  w.complete('design','cases')
  w.approve('cases','c1','project')
  w.complete('case_review','review-cases')
  for k in ('jira_project','plan_name','cycle_name'):w.answer(k,k)
  w.approve('test_plan','old','project')
  return w
 def test_legacy_completion_denied(self):
  w=self.ready_plan()
  with self.assertRaises(PermissionError):w.complete('test_plan','created')
 def test_legacy_approval_denied_by_exact(self):
  w=self.ready_plan()
  self.assertEqual(w.evaluate_exact('test_plan',{'test_plan':{'cases':['A']}},{'test_plan':'project'}),'WAITING_APPROVAL')
 def test_exact_completion(self):
  w=self.ready_plan()
  doc={'cases':['A']}
  w.approve_exact('test_plan','project',doc,'approver')
  w.complete_exact('test_plan','dry-run-result',{'test_plan':doc},{'test_plan':'project'},
                   receipt='synthetic-test-receipt',verifier=synthetic_receipt_verifier)
  self.assertEqual(w.steps['test_plan'].status,'DONE')
 def test_modified_artifact_denied(self):
  w=self.ready_plan()
  w.approve_exact('test_plan','project',{'cases':['A']},'approver')
  with self.assertRaises(PermissionError):
   w.complete_exact('test_plan','result',{'test_plan':{'cases':['B']}},{'test_plan':'project'})
 def test_completed_plan_becomes_stale_when_case_artifact_changes(self):
  w=self.ready_plan();doc={'cases':['A']}
  w.approve_exact('test_plan','project',doc,'approver')
  w.complete_exact('test_plan','dry-run-result',{'test_plan':doc},{'test_plan':'project'},
                   receipt='synthetic-test-receipt',verifier=synthetic_receipt_verifier)
  self.assertEqual(w.evaluate_exact('test_plan',{'test_plan':{'cases':['B']}},{'test_plan':'project'}),'STALE')
  self.assertEqual(w.steps['test_plan'].status,'PENDING')
  self.assertNotIn('test_plan',w.approvals)
 def test_no_evidence_denied(self):
  w=self.ready_plan();doc={'cases':['A']}
  w.approve_exact('test_plan','project',doc,'approver')
  with self.assertRaises(ValueError):w.complete_exact('test_plan','',{'test_plan':doc},{'test_plan':'project'})
 def test_boolean_verifier_result_is_denied(self):
  w=self.ready_plan();doc={'cases':['A']}
  w.approve_exact('test_plan','project',doc,'approver')
  with self.assertRaises(PermissionError):
   w.complete_exact('test_plan','dry-run-result',{'test_plan':doc},{'test_plan':'project'},
                    receipt='synthetic-test-receipt',verifier=lambda receipt,binding:True)
 def test_receipt_with_wrong_binding_hash_is_denied(self):
  w=self.ready_plan();doc={'cases':['A']}
  w.approve_exact('test_plan','project',doc,'approver')
  def wrong_hash(receipt,binding):
   return VerifiedCompletionReceipt('fixture-bad','synthetic-test-host','2026-10-14T00:00:00Z',
    '2026-10-14T01:00:00Z','0'*64,'dry-run-result')
  with self.assertRaises(PermissionError):
   w.complete_exact('test_plan','dry-run-result',{'test_plan':doc},{'test_plan':'project'},
                    receipt='synthetic-test-receipt',verifier=wrong_hash)
 def test_verified_receipt_survives_save_reload(self):
  w=self.ready_plan();doc={'cases':['A']}
  w.approve_exact('test_plan','project',doc,'approver')
  w.complete_exact('test_plan','dry-run-result',{'test_plan':doc},{'test_plan':'project'},
                   receipt='synthetic-test-receipt',verifier=synthetic_receipt_verifier)
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'workflow.json';w.save(path);reloaded=Workflow.load(path)
   stored=reloaded.steps['test_plan'].execution_receipt
   self.assertEqual(stored['receipt_id'],'fixture-dry-run')
   self.assertEqual(stored['evidence_ref'],'dry-run-result')
   self.assertEqual(reloaded.evaluate_exact('test_plan',{'test_plan':doc},{'test_plan':'project'}),'DONE')
