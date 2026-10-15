import os,unittest
from unittest.mock import patch
from qa_master.enterprise import Target,ReadOnlyConnector,IntegrationError,WriteAuthorization,build_synapsert_plan,validate_machine
class EnterpriseTests(unittest.TestCase):
 def test_https(self):self.assertEqual(Target('jira','https://jira.example','JIRA_TOKEN').name,'jira')
 def test_http_rejected(self):
  with self.assertRaises(ValueError):Target('jira','http://jira.example','JIRA_TOKEN')
 def test_password_in_url_rejected(self):
  with self.assertRaises(ValueError):Target('jira','https://me:pass@jira.example','JIRA_TOKEN')
 def test_invalid_env_name(self):
  with self.assertRaises(ValueError):Target('jira','https://jira.example','bad-key')
 def test_missing_secret(self):
  with patch.dict(os.environ,{},clear=True):
   with self.assertRaises(IntegrationError):ReadOnlyConnector(Target('jira','https://jira.example','JIRA_TOKEN')).read('/api')
 def test_read_only(self):
  with patch.dict(os.environ,{'JIRA_TOKEN':'temporary'}):
   out=ReadOnlyConnector(Target('jira','https://jira.example','JIRA_TOKEN'),transport=lambda url,headers:{'url':url,'auth':headers['Authorization']}).read('/rest/api/2/project')
  self.assertEqual(out['url'],'https://jira.example/rest/api/2/project')
 def test_traversal(self):
  with self.assertRaises(ValueError):ReadOnlyConnector(Target('jira','https://jira.example','JIRA_TOKEN')).read('/../secret')
 def test_scope_exact(self):
  a=WriteAuthorization('CSE','synapsert.plan','CSE/P/C','owner','A,B')
  self.assertTrue(a.validate('CSE','synapsert.plan','CSE/P/C','A,B'))
 def test_scope_mismatch(self):
  a=WriteAuthorization('CSE','synapsert.plan','CSE/P/C','owner','A,B')
  with self.assertRaises(PermissionError):a.validate('OTHER','synapsert.plan','CSE/P/C','A,B')
 def test_plan_dry_run(self):
  p=build_synapsert_plan(project='CSE',plan='P',cycle='C',case_ids=['A','B'],assignee='dev')
  self.assertEqual(p['writes_performed'],0)
 def test_plan_needs_assignee(self):
  with self.assertRaises(ValueError):build_synapsert_plan(project='CSE',plan='P',cycle='C',case_ids=['A'],assignee='')
 def test_duplicate_cases(self):
  with self.assertRaises(ValueError):build_synapsert_plan(project='CSE',plan='P',cycle='C',case_ids=['A','A'],assignee='dev')
 def test_approved_plan_still_dry_run(self):
  draft=build_synapsert_plan(project='CSE',plan='P',cycle='C',case_ids=['A','B'],assignee='dev')
  a=WriteAuthorization('CSE','synapsert.plan',draft['resource'],'owner',draft['case_version'])
  p=build_synapsert_plan(project='CSE',plan='P',cycle='C',case_ids=['A','B'],assignee='dev',approval=a)
  self.assertFalse(p['approval_verified']);self.assertTrue(p['scope_assertion_matches']);self.assertEqual(p['mode'],'DRY_RUN_ONLY')
  with self.assertRaises(PermissionError):
   build_synapsert_plan(project='CSE',plan='P',cycle='C',case_ids=['A','B'],assignee='other',approval=a)
 def test_delimited_case_sets_are_distinct(self):
  first=build_synapsert_plan(project='P',plan='P',cycle='C',case_ids=['A','B,C'],assignee='dev')
  other=build_synapsert_plan(project='P',plan='P',cycle='C',case_ids=['A,B','C'],assignee='dev')
  self.assertNotEqual(first['case_version'],other['case_version'])
 def test_machine_ssh(self):self.assertEqual(validate_machine('10.1.2.3','ssh','SSH_KEY')['state'],'NOT_CONNECTED')
 def test_machine_invalid(self):
  with self.assertRaises(ValueError):validate_machine('https://host','ssh','SSH_KEY')
