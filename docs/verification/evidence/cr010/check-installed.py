import json,sys,subprocess,hashlib
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from tests.test_design_methods_independent import corpus
base=Path('.qa-master/cr010-independent').resolve(); py=base/'venv/Scripts/python.exe'
b=corpus(); b['project']='Installed independent'; (base/'valid.json').write_text(json.dumps(b))
legacy=dict(b); del legacy['design_models']; (base/'legacy.json').write_text(json.dumps(legacy))
(base/'invalid.json').write_text('{"design_models":{"token":"MUST_NOT_ESCAPE"}}')
script="""import socket,subprocess,sys,json
from unittest.mock import patch
from qa_master.campaign_cli import main
import qa_master.design_methods as dm
assert 'site-packages' in dm.__file__,dm.__file__
with patch.object(socket,'socket',side_effect=AssertionError('NETWORK')),patch.object(subprocess,'Popen',side_effect=AssertionError('PROCESS')):
 sys.exit(main(sys.argv[1:]))
"""
results=[]
for name in ('valid','legacy','invalid'):
 out=base/(name+'-output.json')
 if name=='invalid':out.write_bytes(b'PRESERVE')
 p=subprocess.run([str(py),'-c',script,'--input',str(base/(name+'.json')),'--output',str(out)],cwd=base,capture_output=True,text=True)
 results.append({'case':name,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
 assert p.returncode==(2 if name=='invalid' else 0),results[-1]
 if name=='invalid':
  assert out.read_bytes()==b'PRESERVE';assert 'MUST_NOT_ESCAPE' not in p.stdout+p.stderr
 else:
  data=json.loads(out.read_text(encoding="utf-8"));assert data['workflow']['execution']=='NOT_AUTHORIZED'
  if name=='valid':
   assert data['method_design']['execution']=='NOT_EXECUTED'
   assert data['method_design']['status']=='DRAFT_UNAPPROVED'
   assert data['method_design']['summary']['model_count']==3
  else:assert 'method_design' not in data
(base/'installed-wheel-results.json').write_text(json.dumps(results,indent=2))
print(json.dumps({'installed_wheel_cases':3,'outcome':'PASS','network_process_sentinels':'enforced inside installed CLI process'}))

