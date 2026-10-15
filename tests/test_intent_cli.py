import json,subprocess,sys,tempfile,unittest
import os
from pathlib import Path
class IntentCliTests(unittest.TestCase):
 def test_chinese_json_survives_ascii_output_pipe(self):
  with tempfile.TemporaryDirectory() as d:
   base=[sys.executable,'-m','qa_master','--state',str(Path(d)/'state.json')]
   env=dict(os.environ,PYTHONIOENCODING='ascii')
   initialized=subprocess.run(base+['init','中文项目'],env=env,capture_output=True,text=True)
   self.assertEqual(initialized.returncode,0,initialized.stderr)
   self.assertEqual(json.loads(initialized.stdout)['project'],'中文项目')
   plan=subprocess.run(base+['plan','只生成用例，不执行测试'],env=env,capture_output=True,text=True)
   self.assertEqual(plan.returncode,0,plan.stderr)
   self.assertTrue(json.loads(plan.stdout)['no_execution'])
 def test_conversational_plan_with_saved_state(self):
  with tempfile.TemporaryDirectory() as d:
   state=Path(d)/'campaign.json'
   command=[sys.executable,'-m','qa_master','--state',str(state)]
   for args in (['init','example'],['answer','gitlab','mygroup/repo']):
    p=subprocess.run(command+args,capture_output=True,text=True)
    self.assertEqual(p.returncode,0,p.stderr)
   plan=subprocess.run(command+['plan','只生成用例，不执行测试'],capture_output=True,text=True)
   self.assertEqual(plan.returncode,0,plan.stderr)
   data=json.loads(plan.stdout)
   self.assertEqual(data['stages'],['design'])
   self.assertTrue(data['no_execution'])
   self.assertIn('正式需求',data['questions'][0])
 def test_no_repeated_requirement_question(self):
  with tempfile.TemporaryDirectory() as d:
   state=Path(d)/'campaign.json'
   base=[sys.executable,'-m','qa_master','--state',str(state)]
   for args in (['init','example'],['answer','gitlab','mygroup/repo'],['answer','requirements','没有']):
    p=subprocess.run(base+args,capture_output=True,text=True)
    self.assertEqual(p.returncode,0,p.stderr)
   p=subprocess.run(base+['plan','只生成用例'],capture_output=True,text=True)
   self.assertEqual(json.loads(p.stdout)['questions'],[])
