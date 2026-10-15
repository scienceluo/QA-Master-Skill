"""Independent DES-033 v2 oracle suite.  Do not run before TASK-036 claim."""
import copy
import json
import unittest

from qa_master.design_methods import DesignMethodError, design_methods, load_bundle_json


def corpus():
    src=[{"id":"SRC","kind":"requirement","locator":"refs/source"},{"id":"RULE","kind":"model","locator":"refs/rule"},{"id":"EFFECT","kind":"effect","locator":"refs/effect"}]
    ora=[{"id":"VALID","kind":"valid","locator":"oracle/valid"},{"id":"INVALID","kind":"invalid","locator":"oracle/invalid"},{"id":"OUT1","kind":"outcome","locator":"oracle/out1"},{"id":"OUT2","kind":"outcome","locator":"oracle/out2"},{"id":"TRANS","kind":"transition","locator":"oracle/trans"},{"id":"DENY","kind":"denial","locator":"oracle/deny"}]
    return {"requirements":[{"id":"REQ-ORACLE","priority":"P1"}],"design_models":{"schema_version":1,"source_refs":src,"oracle_refs":ora,"models":[
      {"id":"BOUND","method":"boundary","title":"Boundary","dimension":"functional","requirement_ids":["REQ-ORACLE"],"source_refs":["SRC"],"spec":{"numeric_type":"decimal","precision":34,"scale":1,"origin":"0","step":"0.1","lower":{"value":"-0.1","inclusive":False},"upper":{"value":"0.1","inclusive":True},"oracle_by_class":{"IN_DOMAIN":"VALID","LOWER_INVALID":"INVALID","UPPER_INVALID":"INVALID","BOTH_INVALID":"INVALID"}}},
      {"id":"DEC","method":"decision_table","title":"Decision","dimension":"functional","requirement_ids":["REQ-ORACLE"],"source_refs":["SRC"],"spec":{"conditions":[{"id":"flag","values":[False,True]},{"id":"count","values":[1,2]}],"constraints":[],"rules":[{"id":"A","when":{"flag":True},"outcome_id":"same","source_refs":["RULE"],"oracle_ref":"OUT1"},{"id":"B","when":{"flag":True,"count":1},"outcome_id":"same","source_refs":["RULE"],"oracle_ref":"OUT1"}]}},
      {"id":"STATE","method":"state_transition","title":"State","dimension":"functional","requirement_ids":["REQ-ORACLE"],"source_refs":["SRC"],"spec":{"states":[{"id":"new","terminal":False,"source_refs":["SRC"]},{"id":"done","terminal":True,"source_refs":["SRC"]},{"id":"orphan","terminal":False,"source_refs":["SRC"]}],"initial_state":"new","triggers":["finish"],"transitions":[{"id":"go","validity":"valid","from_state":"new","to_state":"done","trigger":"finish","guard_refs":[],"effect_refs":["EFFECT"],"source_refs":["SRC"],"oracle_ref":"TRANS"}],"closed_world":True,"closed_world_deny_oracle_ref":"DENY"}}
    ]}}


class IndependentDesignMethods(unittest.TestCase):
    def test_oracle_boundary_exact_decimal_and_metadata_binding(self):
        r=design_methods(corpus()); row=next(x for x in r["model_results"] if x["model_id"]=="BOUND")
        self.assertEqual(row["analysis"]["requested_positions"],6); self.assertLessEqual(row["analysis"]["distinct_points"],6)
        cases=[x for x in r["candidates"] if x["model_id"]=="BOUND"]
        self.assertEqual({x["method_data"]["value"] for x in cases},{"-0.2","-0.1","0","0.1","0.2"})
        self.assertEqual([x["id"] for x in cases],sorted(x["id"] for x in cases))
        self.assertTrue(all(x["trace"]==["REQ-ORACLE"] and x["source_refs"][0]["id"]=="SRC" for x in cases))

    def test_oracle_decision_ledger_and_typed_boolean_integer(self):
        b=corpus(); s=b["design_models"]["models"][1]["spec"]; s["conditions"]=[{"id":"typed","values":[True,1]}]; s["rules"]=[{"id":"r","when":{"typed":True},"outcome_id":"yes","source_refs":["RULE"],"oracle_ref":"OUT1"}]
        row=next(x for x in design_methods(b)["model_results"] if x["model_id"]=="DEC"); a=row["analysis"]
        self.assertEqual(a["universe_size"],2); self.assertEqual(a["universe_size"],a["excluded"]+a["constraint_unevaluable"]+a["admissible"])
        self.assertEqual(a["admissible"],a["unique"]+a["overlap"]+a["conflict"]+a["gap"])

    def test_oracle_same_outcome_divergent_oracle_is_conflict(self):
        b=corpus(); rules=b["design_models"]["models"][1]["spec"]["rules"]; rules[1]["oracle_ref"]="OUT2"
        r=design_methods(b); self.assertIn("DECISION_CONFLICT",[x["code"] for x in r["obligations"]])

    def test_oracle_state_reachability_is_structural_and_missing_oracle_not_case(self):
        b=corpus(); b["design_models"]["models"][2]["spec"]["transitions"][0]["oracle_ref"]=None
        row=next(x for x in design_methods(b)["model_results"] if x["model_id"]=="STATE")
        self.assertIn("done",row["analysis"]["reachable_states"]); self.assertIn("orphan",row["analysis"]["unreachable_states"])

    def test_permutations_and_loader_errors_are_deterministic_and_atomic(self):
        a=corpus(); b=copy.deepcopy(a); b["design_models"]["models"].reverse(); b["design_models"]["source_refs"].reverse()
        self.assertEqual(json.dumps(design_methods(a),sort_keys=True),json.dumps(design_methods(b),sort_keys=True))
        for raw,code in ((b'{"x":1,"x":2}',"DUPLICATE_JSON_KEY"),(b'{"design_models":{"token":"private"}}',"SECRET_FIELD_FORBIDDEN")):
            with self.subTest(code=code):
                with self.assertRaisesRegex(DesignMethodError,"^"+code+"$"): load_bundle_json(raw)

    def test_decimal_34_digit_and_noncanonical_or_kind_errors_are_atomic(self):
        b=corpus(); spec=b["design_models"]["models"][0]["spec"]
        spec.update({"precision":34,"scale":0,"origin":"0","step":"1","lower":{"value":"0","inclusive":True},"upper":{"value":"9999999999999999999999999999999999","inclusive":True}})
        self.assertLessEqual(next(x for x in design_methods(b)["model_results"] if x["model_id"]=="BOUND")["analysis"]["distinct_points"],6)
        for key,value in (("origin","1.0"),("step","-0")):
            x=corpus(); x["design_models"]["models"][0]["spec"][key]=value
            with self.subTest(key=key):
                with self.assertRaises(DesignMethodError): design_methods(x)
        x=corpus(); x["design_models"]["oracle_refs"][0]["kind"]="outcome"
        with self.assertRaisesRegex(DesignMethodError,"BOUNDARY_ORACLE_KIND_INVALID"): design_methods(x)

    def test_model_limit_and_malformed_nested_scalar_reject_before_result(self):
        x=corpus(); model=x["design_models"]["models"][0]
        x["design_models"]["models"]=[dict(model,id="M"+str(i)) for i in range(101)]
        with self.assertRaises(DesignMethodError): design_methods(x)
        x=corpus(); x["design_models"]["models"][1]["spec"]["conditions"][0]["values"]=[{"bad":1}]
        with self.assertRaises(DesignMethodError): design_methods(x)


class AcceptanceMatrix(unittest.TestCase):
    def single(self, index):
        b=corpus(); b['project']='Independent acceptance'; b['design_models']['models']=[b['design_models']['models'][index]]
        return b,b['design_models']['models'][0]['spec']

    def result(self,b):
        r=design_methods(b); return r,r['model_results'][0]['analysis'],r['model_results'][0]['coverage']

    def ledger(self,r,a,rows):
        cs={x['id'] for x in r['candidates']}; obs={x['id'] for x in r['obligations']}
        for row in a[rows]:
            if row['candidate_id']: self.assertIn(row['candidate_id'],cs)
            self.assertTrue(set(row['obligation_ids']) <= obs)
        self.assertEqual(len(cs),len(r['candidates']))
        self.assertEqual(r['execution'],'NOT_EXECUTED')
        for c in r['candidates']:
            self.assertEqual((c['approval'],c['evidence_state'],c['validation_action']),('DRAFT','PENDING','NOT_EXECUTED'))

    def test_tc_dm_101_boundary_exact_open_closed_and_origins(self):
        for left in (False,True):
            for right in (False,True):
                b,s=self.single(0); s.update(numeric_type='integer',origin=0,step=1,lower={'value':-1,'inclusive':left},upper={'value':1,'inclusive':right}); del s['precision']; del s['scale']
                r,a,c=self.result(b)
                self.assertEqual([(int(p['value']),p['class'],p['origins']) for p in a['points']], [(-2,'LOWER_INVALID',['lower']),(-1,'IN_DOMAIN' if left else 'LOWER_INVALID',['lower']),(0,'IN_DOMAIN',['lower','upper']),(1,'IN_DOMAIN' if right else 'UPPER_INVALID',['upper']),(2,'UPPER_INVALID',['upper'])])
                self.assertEqual((a['requested_positions'],a['distinct_points'],a['candidate_ready']),(6,5,5)); self.assertEqual(c['ratio'],{'numerator':5,'denominator':5}); self.ledger(r,a,'points')

    def test_tc_dm_102_empty_missing_and_34digit_exact(self):
        for typ in ('integer','decimal'):
            b,s=self.single(0); n=10**34-1
            s.update(numeric_type=typ,origin=0 if typ=='integer' else '0',step=1 if typ=='integer' else '1',lower={'value':n if typ=='integer' else str(n),'inclusive':True},upper={'value':n if typ=='integer' else str(n),'inclusive':True})
            if typ=='integer': del s['precision']; del s['scale']
            else: s['scale']=0
            r,a,c=self.result(b); self.assertEqual([str(p['value']) for p in a['points']],[str(n-1),str(n),str(n+1)]); self.assertEqual((a['unrepresentable'],a['in_domain'],c['out_of_scope']),(1,1,1))
            del s['oracle_by_class']['IN_DOMAIN']; r,a,c=self.result(b); self.assertEqual(c['gap'],0); self.assertEqual(a['oracle_missing'],1); self.assertEqual([o['code'] for o in r['obligations']].count('BOUNDARY_ORACLE_MISSING'),1); self.assertEqual(len(r['candidates']),1); self.assertEqual(len(r['obligations']),2)
            s['lower']['inclusive']=False; s['upper']['inclusive']=False
            r,a,c=self.result(b); self.assertEqual(c['gap'],1); self.assertEqual(a['both_invalid'],1)

    def test_tc_dm_103_decision_six_classes_and_ids(self):
        b,s=self.single(1); s['conditions']=[{'id':'x','values':list(range(6))}]; rules=[]
        for value,oracles in ((0,['OUT1']),(1,[None]),(2,['OUT1','OUT1']),(3,[None,None]),(4,['OUT1','OUT2'])):
            for i,oracle in enumerate(oracles): rules.append({'id':f'r{value}-{i}','when':{'x':value},'outcome_id':'same','source_refs':['RULE'],'oracle_ref':oracle})
        s['rules']=rules; r,a,c=self.result(b)
        keys=['UNIQUE_ORACLE_READY','UNIQUE_ORACLE_MISSING','OVERLAP_ORACLE_READY','OVERLAP_ORACLE_MISSING','CONFLICT','GAP']
        self.assertEqual([row['classification'] for row in a['assignments']],keys); self.assertEqual(a['classification_counts'],dict.fromkeys(keys,1)); self.assertEqual((c['candidate_ready'],c['oracle_missing'],c['overlap'],c['conflict'],c['gap']),(2,2,2,1,1)); self.ledger(r,a,'assignments')
        self.assertEqual([len(x['obligation_ids']) for x in a['assignments']],[0,1,1,2,1,1])

    def test_tc_dm_104_typed_constraints_all_operators(self):
        for op,expected in [('eq',[True]),('ne',[1,'1']),('in',[True]),('not_in',[1,'1']),('all',[True]),('any',[True])]:
            b,s=self.single(1); s['conditions']=[{'id':'x','values':['1',1,True]}]; s['rules']=[]
            leaf={'op':'eq','condition':'x','value':True}
            node={'op':op,'condition':'x',('values' if op in ('in','not_in') else 'value'):([True] if op in ('in','not_in') else True)} if op not in ('all','any') else {'op':op,'items':[leaf]}
            s['constraints']=[node]; r,a,c=self.result(b)
            self.assertEqual([(type(x['values']['x']).__name__,x['values']['x']) for x in a['assignments'] if x['admissibility']=='ADMISSIBLE'],[(type(x).__name__,x) for x in expected]); self.assertEqual(a['admissible'],len(expected)); self.ledger(r,a,'assignments')

    def test_tc_dm_105_ast_and_product_limits(self):
        b,s=self.single(1); s['conditions']=[{'id':'x','values':list(range(4096))}]; s['rules']=[]; s['constraints']=[{'op':'ne','condition':'x','value':0}]*128
        self.assertEqual(self.result(b)[1]['admissible'],4095)
        s['constraints'].append({'op':'ne','condition':'x','value':0})
        with self.assertRaisesRegex(DesignMethodError,'^DECISION_CONSTRAINT_INVALID$'): design_methods(b)
        s['constraints']=[]; s['conditions'][0]['values'].append(4096)
        with self.assertRaisesRegex(DesignMethodError,'^DECISION_LIMIT_EXCEEDED$'): design_methods(b)
        s['conditions'][0]['values']=[0]; node={'op':'eq','condition':'x','value':0}
        for _ in range(7): node={'op':'all','items':[node]}
        s['constraints']=[node]; self.assertEqual(self.result(b)[1]['admissible'],1)
        s['constraints']=[{'op':'all','items':[node]}]
        with self.assertRaisesRegex(DesignMethodError,'^DECISION_CONSTRAINT_INVALID$'): design_methods(b)

    def test_tc_dm_106_state_duplicate_conflict_unreachable(self):
        b,s=self.single(2); s['closed_world']=False; s['closed_world_deny_oracle_ref']=None
        t=s['transitions'][0]; s['transitions'].append(dict(t,id='copy'))
        r,a,c=self.result(b); self.assertEqual((c['denominator'],c['overlap'],c['candidate_ready']),(1,1,1)); self.assertEqual(a['logical_rows'][0]['classification'],'DUPLICATE_VALID_READY'); self.ledger(r,a,'logical_rows')
        s['transitions'][1]['oracle_ref']=None; r,a,c=self.result(b); self.assertEqual(c['conflict'],1); self.assertEqual(c['candidate_ready'],0); self.assertNotIn('done',a['reachable_states'])
        s['transitions']=[dict(t,oracle_ref=None),dict(t,id='orphan-go',from_state='orphan')]
        r,a,c=self.result(b); self.assertIn('done',a['reachable_states']); self.assertEqual((c['unreachable'],c['oracle_missing'],c['candidate_ready']),(1,1,1)); self.assertIn('STATE_UNREACHABLE_TRANSITION',[o['code'] for o in r['obligations']])

    def test_tc_dm_107_closedworld_terminal_and_limits(self):
        b,s=self.single(2); r,a,c=self.result(b); self.assertEqual((c['denominator'],a['closed_world_added']),(3,2)); self.assertEqual(next(x for x in a['logical_rows'] if x['from_state']=='done')['classification'],'INVALID_READY')
        s['states']=[{'id':f's{i}','terminal':True,'source_refs':['SRC']} for i in range(128)]; s['initial_state']='s0'; s['transitions']=[]; s['triggers']=[f'e{i}' for i in range(32)]
        self.assertEqual(self.result(b)[2]['denominator'],4096)
        s['triggers'].append('excess')
        with self.assertRaisesRegex(DesignMethodError,'^STATE_LIMIT_EXCEEDED$'): design_methods(b)
        s['triggers']=[]; s['closed_world']=False; s['closed_world_deny_oracle_ref']=None; self.assertEqual(self.result(b)[2]['state'],'UNASSESSED')
        s['states'].append({'id':'excess','terminal':True,'source_refs':['SRC']})
        with self.assertRaisesRegex(DesignMethodError,'^STATE_MODEL_INCOMPLETE$'): design_methods(b)
        b,s=self.single(2); s['transitions']=[dict(s['transitions'][0],id=f't{i}') for i in range(512)]; self.assertEqual(self.result(b)[1]['explicit_records'],512)
        s['transitions'].append(dict(s['transitions'][0],id='excess'))
        with self.assertRaisesRegex(DesignMethodError,'^STATE_LIMIT_EXCEEDED$'): design_methods(b)

    def test_tc_dm_108_models_binding_permutations(self):
        b,s=self.single(0); original=design_methods(b)
        for target in ('requirement','oracle','source'):
            x=copy.deepcopy(b)
            if target=='requirement': x['requirements'][0]['title']='changed'
            elif target=='oracle': x['design_models']['oracle_refs'][0]['locator']='changed/oracle'
            else: x['design_models']['source_refs'][0]['locator']='changed/source'
            new=design_methods(x); self.assertNotEqual(original['input_sha256'],new['input_sha256']); self.assertTrue({c['id'] for c in original['candidates']}.isdisjoint(c['id'] for c in new['candidates']))
        b=corpus(); x=copy.deepcopy(b)
        for key in ('models','source_refs','oracle_refs'): x['design_models'][key].reverse()
        for m in x['design_models']['models']:
            for key in ('conditions','rules','states','transitions','triggers'):
                if key in m['spec']: m['spec'][key].reverse()
            if 'conditions' in m['spec']:
                for condition in m['spec']['conditions']: condition['values'].reverse()
        self.assertEqual(design_methods(b),design_methods(x))
        b,s=self.single(0); m=b['design_models']['models'][0]; b['design_models']['models']=[dict(m,id=f'm{i}') for i in range(100)]; self.assertEqual(design_methods(b)['summary']['model_count'],100)
        b['design_models']['models'].append(dict(m,id='extra'))
        with self.assertRaisesRegex(DesignMethodError,'^MODEL_LIMIT_EXCEEDED$'): design_methods(b)

    def test_tc_dm_109_rejections_and_no_side_effects(self):
        from unittest.mock import patch
        import socket,subprocess
        b=corpus()
        with patch.object(socket,'socket',side_effect=AssertionError('network')),patch.object(subprocess,'Popen',side_effect=AssertionError('process')):
            self.assertEqual(design_methods(b)['execution'],'NOT_EXECUTED')
        for raw in (b'\xff',b'{',b'{"x":NaN}',b'{"x":Infinity}',b'{"x":1,"x":2}'):
            with self.subTest(raw=raw),self.assertRaises(DesignMethodError): load_bundle_json(raw)
        for val in ('1.0','-0','01','1e0','+1','NaN',True,1.2,[],{}):
            x,s=self.single(0); s['step']=val
            with self.subTest(val=val),self.assertRaises(DesignMethodError): design_methods(x)
        for locator in ('/root','../x','a/../b','https://x','C:/x','a\\b','a?x','a#x','a b'):
            x=corpus(); x['design_models']['source_refs'][0]['locator']=locator
            with self.subTest(locator=locator),self.assertRaises(DesignMethodError): design_methods(x)
        for index,key,value in [(0,'oracle_by_class',{'IN_DOMAIN':'OUT1'}),(1,'rules',[{'id':'r','when':{},'outcome_id':'x','source_refs':['SRC'],'oracle_ref':'VALID'}])]:
            x,s=self.single(index); s[key]=value
            with self.assertRaises(DesignMethodError): design_methods(x)
        for key,value in [('guard_refs',['EFFECT']),('effect_refs',['SRC']),('oracle_ref','VALID')]:
            x,s=self.single(2); s['transitions'][0][key]=value
            with self.assertRaises(DesignMethodError): design_methods(x)
        for key,val in [('password','secret'),('float',1.2)]:
            x=corpus(); x['requirements'][0][key]=val
            with self.assertRaises(DesignMethodError): design_methods(x)

    def test_tc_dm_110_state_self_invalid_empty_and_metameric_rules(self):
        b,s=self.single(2); s.update(closed_world=False,closed_world_deny_oracle_ref=None)
        s['transitions'][0]['to_state']='new'; r,a,c=self.result(b); self.assertEqual(a['reachable_states'],['new']); self.assertEqual(c['candidate_ready'],1)
        s['transitions'][0].update(validity='invalid',to_state=None,oracle_ref='DENY'); r,a,c=self.result(b); self.assertEqual(c['denominator'],1); self.assertEqual(a['logical_rows'][0]['classification'],'INVALID_READY')
        s['transitions']=[]; s['triggers']=[]; s['states']=[{'id':'new','terminal':True,'source_refs':['SRC']}]; r,a,c=self.result(b); self.assertEqual(c['ratio'],None); self.assertEqual(c['denominator'],0)
        b,s=self.single(1); before=self.result(b); s['rules']=[]; after=self.result(b); self.assertGreaterEqual(after[2]['gap'],before[2]['gap']); self.assertEqual(after[2]['candidate_ready'],0)
        s['constraints']=[{'op':'eq','condition':'flag','value':True},{'op':'eq','condition':'flag','value':False}]; r,a,c=self.result(b); self.assertEqual((c['state'],c['ratio'],a['excluded']),('UNASSESSED',None,4))

    def test_tc_dm_111_fresh_process_bytes_and_legacy_atomic(self):
        import subprocess,sys,tempfile
        from pathlib import Path
        from qa_master.campaign_cli import prepare_campaign,write_campaign
        b=corpus(); b['project']='Acceptance'; raw=json.dumps(b)
        code="import sys,json;from qa_master.design_methods import design_methods,load_bundle_json;print(json.dumps(design_methods(load_bundle_json(sys.stdin.buffer.read())),sort_keys=True,separators=(',',':'),ensure_ascii=False))"
        one=subprocess.run([sys.executable,'-c',code],input=raw,text=True,capture_output=True,check=True)
        two=subprocess.run([sys.executable,'-c',code],input=raw,text=True,capture_output=True,check=True)
        self.assertEqual(one.stdout.encode(),two.stdout.encode())
        legacy=copy.deepcopy(b); del legacy['design_models']; baseline=prepare_campaign(legacy); enabled=prepare_campaign(b)
        self.assertNotIn('method_design',baseline)
        for key in baseline:
            if key!='input_sha256': self.assertEqual(baseline[key],enabled[key])
        with tempfile.TemporaryDirectory() as td:
            inp=Path(td)/'in.json'; out=Path(td)/'out.json'; out.write_bytes(b'PRESERVE')
            for payload in (b'{"x":1,"x":2}',b'{"design_models":{"token":"DO_NOT_LEAK"}}',json.dumps(dict(b,design_models={'bad':True})).encode()):
                inp.write_bytes(payload)
                result=subprocess.run([sys.executable,'-m','qa_master.campaign_cli','--input',str(inp),'--output',str(out)],capture_output=True,text=True)
                self.assertEqual(result.returncode,2); self.assertEqual(out.read_bytes(),b'PRESERVE'); self.assertNotIn('DO_NOT_LEAK',result.stdout+result.stderr); self.assertEqual(json.loads(result.stdout)['status'],'REJECTED'); self.assertFalse(list(Path(td).glob('.qa-master-*')))
