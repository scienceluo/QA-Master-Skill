import copy
import json
import unittest

from qa_master.design_methods import DesignMethodError, design_methods, load_bundle_json


def bundle():
    refs=[{"id":"SRC","kind":"requirement","locator":"docs/requirement"},{"id":"RULE","kind":"model","locator":"docs/rule"},{"id":"EFFECT","kind":"effect","locator":"docs/effect"}]
    ors=[{"id":"V","kind":"valid","locator":"oracles/v"},{"id":"I","kind":"invalid","locator":"oracles/i"},{"id":"O","kind":"outcome","locator":"oracles/o"},{"id":"T","kind":"transition","locator":"oracles/t"},{"id":"D","kind":"denial","locator":"oracles/d"}]
    return {"project":"p","requirements":[{"id":"REQ-1","priority":"P1"}],"design_models":{"schema_version":1,"source_refs":refs,"oracle_refs":ors,"models":[
      {"id":"B","method":"boundary","title":"B","dimension":"functional","requirement_ids":["REQ-1"],"source_refs":["SRC"],"spec":{"numeric_type":"decimal","precision":6,"scale":1,"origin":"0","step":"0.1","lower":{"value":"-0.1","inclusive":False},"upper":{"value":"0.1","inclusive":True},"oracle_by_class":{"IN_DOMAIN":"V","LOWER_INVALID":"I","UPPER_INVALID":"I","BOTH_INVALID":"I"}}},
      {"id":"Q","method":"decision_table","title":"Q","dimension":"functional","requirement_ids":["REQ-1"],"source_refs":["SRC"],"spec":{"conditions":[{"id":"a","values":[True,False]},{"id":"b","values":[1,2]}],"constraints":[],"rules":[{"id":"r1","when":{"a":True},"outcome_id":"yes","source_refs":["RULE"],"oracle_ref":"O"},{"id":"r2","when":{"a":True,"b":1},"outcome_id":"yes","source_refs":["RULE"],"oracle_ref":"O"}]}},
      {"id":"S","method":"state_transition","title":"S","dimension":"functional","requirement_ids":["REQ-1"],"source_refs":["SRC"],"spec":{"states":[{"id":"a","terminal":False,"source_refs":["SRC"]},{"id":"b","terminal":True,"source_refs":["SRC"]},{"id":"z","terminal":False,"source_refs":["SRC"]}],"initial_state":"a","triggers":["go"],"transitions":[{"id":"t","validity":"valid","from_state":"a","to_state":"b","trigger":"go","guard_refs":[],"effect_refs":["EFFECT"],"source_refs":["SRC"],"oracle_ref":"T"}],"closed_world":True,"closed_world_deny_oracle_ref":"D"}}
    ]}}


class DesignMethods(unittest.TestCase):
    def test_all_methods_are_draft_and_deterministic(self):
        a=bundle(); b=copy.deepcopy(a); b["design_models"]["models"].reverse(); b["design_models"]["source_refs"].reverse()
        x,y=design_methods(a),design_methods(b)
        self.assertEqual(json.dumps(x,sort_keys=True),json.dumps(y,sort_keys=True))
        self.assertEqual(x["status"],"DRAFT_UNAPPROVED"); self.assertEqual(x["execution"],"NOT_EXECUTED")
        self.assertEqual(x["summary"]["model_count"],3)
        self.assertIn("DECISION_OVERLAP",[z["code"] for z in x["obligations"]])
        self.assertIn("z",next(z for z in x["model_results"] if z["model_id"]=="S")["analysis"]["unreachable_states"])
        self.assertTrue(all(c["evidence_state"]=="PENDING" for c in x["candidates"]))

    def test_boundary_missing_oracle_is_obligation(self):
        x=bundle(); del x["design_models"]["models"][0]["spec"]["oracle_by_class"]["LOWER_INVALID"]
        result=design_methods(x)
        self.assertIn("BOUNDARY_ORACLE_MISSING",[z["code"] for z in result["obligations"]])
        self.assertNotIn("LOWER_INVALID",[z["method_data"]["class"] for z in result["candidates"] if z["model_id"]=="B"])

    def test_decision_gap_conflict_and_constraint(self):
        x=bundle(); spec=x["design_models"]["models"][1]["spec"]
        spec["rules"]=[{"id":"x","when":{"a":True},"outcome_id":"one","source_refs":["RULE"],"oracle_ref":"O"},{"id":"y","when":{"a":True},"outcome_id":"two","source_refs":["RULE"],"oracle_ref":"O"}]
        spec["constraints"]=[{"op":"eq","condition":"b","value":1}]
        r=design_methods(x); codes=[z["code"] for z in r["obligations"]]
        self.assertIn("DECISION_CONFLICT",codes); self.assertIn("DECISION_GAP",codes)
        q=next(z for z in r["model_results"] if z["model_id"]=="Q"); self.assertEqual(sum(q["analysis"]["classification_counts"].values()),q["coverage"]["denominator"])

    def test_state_closed_world_and_no_invalid_inference(self):
        x=bundle(); x["design_models"]["models"][2]["spec"]["closed_world"]=False; x["design_models"]["models"][2]["spec"]["closed_world_deny_oracle_ref"]=None
        r=design_methods(x); self.assertNotIn("STATE_CLOSED_WORLD_INVALID",[z["code"] for z in r["obligations"]])

    def test_loader_duplicate_nan_and_secret_are_rejected(self):
        for raw,code in [(b'{"a":1,"a":2}',"DUPLICATE_JSON_KEY"),(b'{"design_models":{"x":NaN}}',"INVALID_JSON"),(b'{"design_models":{"token":"secret"}}',"SECRET_FIELD_FORBIDDEN")]:
            with self.subTest(code=code):
                with self.assertRaisesRegex(DesignMethodError,"^"+code+"$"): load_bundle_json(raw)

    def test_structural_error_is_atomic(self):
        x=bundle(); x["design_models"]["models"][0]["spec"]["step"]="0"
        with self.assertRaisesRegex(DesignMethodError,"BOUNDARY_MODEL_INCOMPLETE"): design_methods(x)

    def test_floats_limits_and_unknown_links_reject(self):
        x=bundle(); x["design_models"]["models"][1]["spec"]["conditions"][0]["values"]=[1.0]
        with self.assertRaisesRegex(DesignMethodError,"FLOAT_FORBIDDEN"): design_methods(x)
        x=bundle(); x["design_models"]["models"][0]["source_refs"]=["NO"]
        with self.assertRaisesRegex(DesignMethodError,"UNKNOWN_REFERENCE"): design_methods(x)

    def test_boolean_and_integer_remain_distinct_in_constraints(self):
        x=bundle(); q=x["design_models"]["models"][1]["spec"]
        q["conditions"]=[{"id":"v","values":[True,1]}]
        q["constraints"]=[{"op":"eq","condition":"v","value":True}]
        q["rules"]=[{"id":"r","when":{"v":True},"outcome_id":"yes","source_refs":["RULE"],"oracle_ref":"O"}]
        result=design_methods(x); row=next(z for z in result["model_results"] if z["model_id"]=="Q")
        self.assertEqual(row["coverage"]["denominator"],1)

    def test_missing_oracle_valid_edge_is_structurally_reachable(self):
        x=bundle(); state=x["design_models"]["models"][2]["spec"]
        state["transitions"][0]["oracle_ref"]=None
        result=design_methods(x); row=next(z for z in result["model_results"] if z["model_id"]=="S")
        self.assertIn("b",row["analysis"]["reachable_states"])



class DesignMethodRegressions(unittest.TestCase):
    def single(self, index):
        value=bundle()
        value["design_models"]["models"]=[value["design_models"]["models"][index]]
        return value, value["design_models"]["models"][0]["spec"]

    def test_large_exact_boundaries_independent_of_decimal_context(self):
        import decimal
        for typ in ("integer", "decimal"):
            with self.subTest(typ=typ), decimal.localcontext() as context:
                context.prec=2
                value,spec=self.single(0)
                spec.update(numeric_type=typ,origin=0,step=1,
                            lower={"value":10**34-1,"inclusive":True},
                            upper={"value":10**34-1,"inclusive":True})
                if typ=="decimal":
                    spec.update(precision=34,scale=0,origin="0",step="1")
                    spec["lower"]["value"]=spec["upper"]["value"]="9"*34
                else:
                    del spec["precision"]; del spec["scale"]
                result=design_methods(value); analysis=result["model_results"][0]["analysis"]
                self.assertEqual(analysis["distinct_points"],3)
                self.assertEqual(analysis["unrepresentable"],1)
                self.assertEqual([r["value"] for r in analysis["points"]], [str(10**34-2),str(10**34-1),str(10**34)])
                self.assertEqual(sum(analysis["classification_counts"].values()),3)
                self.assertEqual(result["model_results"][0]["coverage"]["out_of_scope"],1)

    def test_decimal_neighbor_canonicalization_and_deduplication(self):
        value,spec=self.single(0)
        spec.update(precision=2,scale=2,step="0.01")
        spec["lower"]={"value":"0.99","inclusive":True}
        spec["upper"]={"value":"0.99","inclusive":True}
        result=design_methods(value); analysis=result["model_results"][0]["analysis"]
        self.assertEqual([r["value"] for r in analysis["points"]],["0.98","0.99","1"])
        self.assertEqual(analysis["unrepresentable"],0)
        self.assertEqual(analysis["points"][1]["origins"],["lower","upper"])

    def test_oracle_removal_does_not_empty_domain(self):
        value,spec=self.single(0)
        del spec["oracle_by_class"]["IN_DOMAIN"]
        result=design_methods(value)
        self.assertNotIn("BOUNDARY_EMPTY_DOMAIN",[o["code"] for o in result["obligations"]])
        self.assertGreater(result["model_results"][0]["analysis"]["in_domain"],0)
        self.assertEqual(result["model_results"][0]["coverage"]["gap"],0)

    def test_empty_grid_domain_is_reported(self):
        value,spec=self.single(0)
        spec["lower"]={"value":"0","inclusive":False}
        spec["upper"]={"value":"0.1","inclusive":False}
        result=design_methods(value)
        self.assertIn("BOUNDARY_EMPTY_DOMAIN",[o["code"] for o in result["obligations"]])
        self.assertEqual(result["model_results"][0]["coverage"]["gap"],1)

    def test_typed_matching_and_exclusion_ledger(self):
        value,spec=self.single(1)
        spec["conditions"]=[{"id":"v","values":[True,1,"1"]}]
        spec["rules"]=[{"id":str(i),"when":{"v":v},"outcome_id":str(i),"source_refs":["RULE"],"oracle_ref":"O"} for i,v in enumerate([True,1,"1"])]
        for constrained in (False,True):
            with self.subTest(constrained=constrained):
                spec["constraints"]=[{"op":"eq","condition":"v","value":True}] if constrained else []
                result=design_methods(value); analysis=result["model_results"][0]["analysis"]
                self.assertEqual(analysis["oracle_ready"],1 if constrained else 3)
                self.assertEqual(analysis["conflict"],0)
                self.assertEqual([r["classification"] for r in analysis["assignments"]], ["UNIQUE_ORACLE_READY"]+(["EXCLUDED"]*2 if constrained else ["UNIQUE_ORACLE_READY"]*2))
                self.assertEqual({r["candidate_id"] for r in analysis["assignments"] if r["candidate_id"]},{c["id"] for c in result["candidates"]})

    def test_divergent_oracles_are_conflict_and_null_overlap_missing(self):
        value,spec=self.single(1)
        spec["conditions"]=[{"id":"v","values":[1]}]
        value["design_models"]["oracle_refs"].append({"id":"O2","kind":"outcome","locator":"oracles/o2"})
        for pair,classification,codes in [(("O","O2"),"CONFLICT",["DECISION_CONFLICT"]),((None,None),"OVERLAP_ORACLE_MISSING",["DECISION_ORACLE_MISSING","DECISION_OVERLAP"]),(("O","O"),"OVERLAP_ORACLE_READY",["DECISION_OVERLAP"])]:
            with self.subTest(pair=pair):
                spec["rules"]=[{"id":str(i),"when":{},"outcome_id":"same","source_refs":["RULE"],"oracle_ref":o} for i,o in enumerate(pair)]
                result=design_methods(value); row=result["model_results"][0]["analysis"]["assignments"][0]
                self.assertEqual(row["classification"],classification)
                self.assertEqual(sorted(o["code"] for o in result["obligations"]),codes)
                self.assertEqual(set(row["obligation_ids"]),{o["id"] for o in result["obligations"]})
                self.assertEqual(len(result["candidates"]),int(classification.endswith("READY")))

    def test_complete_input_binding_and_unrelated_requirement_stability(self):
        original=bundle(); baseline=design_methods(original)
        for change in ("requirement","oracle","nested_source","title"):
            value=copy.deepcopy(original)
            if change=="requirement": value["requirements"][0]["text"]="changed requirement"
            elif change=="oracle": value["design_models"]["oracle_refs"][2]["locator"]="oracles/changed"
            elif change=="nested_source": value["design_models"]["source_refs"][1]["locator"]="docs/changed"
            else: value["design_models"]["models"][1]["title"]="Changed title"
            result=design_methods(value)
            self.assertNotEqual(baseline["input_sha256"],result["input_sha256"])
            self.assertNotEqual(baseline["model_results"][1]["candidate_ids"],result["model_results"][1]["candidate_ids"])
        original["requirements"].append({"id":"UNLINKED","float":1.5})
        self.assertEqual(design_methods(original),baseline)

    def test_nested_set_permutation_is_stable_and_nonmutating(self):
        value=bundle(); state=value["design_models"]["models"][2]["spec"]
        duplicate=copy.deepcopy(state["transitions"][0]); duplicate["id"]="duplicate"
        state["transitions"].append(duplicate)
        shuffled=copy.deepcopy(value)
        dm=shuffled["design_models"]
        dm["models"].reverse(); dm["source_refs"].reverse(); dm["oracle_refs"].reverse()
        for model in dm["models"]:
            spec=model["spec"]
            for key in ("conditions","rules","states","transitions","triggers"):
                if key in spec: spec[key].reverse()
            for condition in spec.get("conditions",[]): condition["values"].reverse()
        before=copy.deepcopy(shuffled)
        self.assertEqual(design_methods(value),design_methods(shuffled))
        self.assertEqual(shuffled,before)

    def test_kind_validation(self):
        for index,field,bad in [(0,"boundary","O"),(1,"decision","V"),(2,"transition","V"),(2,"guard","SRC"),(2,"effect","SRC"),(2,"denial","T")]:
            with self.subTest(field=field):
                value,spec=self.single(index)
                if field=="boundary": spec["oracle_by_class"]["IN_DOMAIN"]=bad
                elif field=="decision": spec["rules"][0]["oracle_ref"]=bad
                elif field=="transition": spec["transitions"][0]["oracle_ref"]=bad
                elif field=="guard": spec["transitions"][0]["guard_refs"]=[bad]
                elif field=="effect": spec["transitions"][0]["effect_refs"]=[bad]
                else: spec["closed_world_deny_oracle_ref"]=bad
                with self.assertRaises(DesignMethodError): design_methods(value)

    def test_closed_world_limit_counts_explicit_pairs_too(self):
        value,spec=self.single(2)
        spec["states"]=[{"id":str(i),"terminal":False,"source_refs":["SRC"]} for i in range(65)]
        spec["initial_state"]="0"; spec["triggers"]=[str(i) for i in range(64)]
        spec["transitions"]=[{"id":str(i),"validity":"invalid","from_state":str(i),"to_state":None,"trigger":"0","guard_refs":[],"effect_refs":[],"source_refs":["SRC"],"oracle_ref":"D"} for i in range(65)]
        with self.assertRaisesRegex(DesignMethodError,"STATE_LIMIT_EXCEEDED"): design_methods(value)

    def test_locator_opaque_words_and_linked_requirement_validation(self):
        value=bundle(); value["design_models"]["source_refs"][0]["locator"]="docs/tokenization"
        design_methods(value)
        for key,bad in (("number",1.5),("TOKEN","not-output")):
            broken=copy.deepcopy(value); broken["requirements"][0][key]=bad
            with self.assertRaises(DesignMethodError): design_methods(broken)

    def test_malformed_types_have_stable_value_free_errors(self):
        for key in ("id","method","dimension","source_refs","spec"):
            for bad in (None,[],{},False,17):
                value=bundle(); value["design_models"]["models"][0][key]=bad
                with self.subTest(key=key,bad=bad), self.assertRaises(DesignMethodError) as caught:
                    design_methods(value)
                self.assertEqual(str(caught.exception),caught.exception.code)

    def test_constraint_budget_is_model_wide_not_assignment_wide(self):
        value,spec=self.single(1)
        spec["conditions"]=[{"id":"v","values":list(range(4096))}]
        spec["rules"]=[]
        spec["constraints"]=[{"op":"ne","condition":"v","value":0} for _ in range(128)]
        result=design_methods(value)
        self.assertEqual(result["model_results"][0]["analysis"]["admissible"],4095)
        spec["constraints"].append({"op":"ne","condition":"v","value":0})
        with self.assertRaisesRegex(DesignMethodError,"DECISION_CONSTRAINT_INVALID"): design_methods(value)

    def test_condition_names_do_not_become_reference_fields(self):
        value,spec=self.single(1)
        spec["conditions"]=[{"id":"oracle_ref","values":["ordinary"]}]
        spec["rules"]=[{"id":"r","when":{"oracle_ref":"ordinary"},"outcome_id":"ok","source_refs":["RULE"],"oracle_ref":"O"}]
        self.assertEqual(len(design_methods(value)["candidates"]),1)

    def test_state_cases_and_conflicts_retain_all_affected_links(self):
        value,spec=self.single(2)
        refs=value["design_models"]["source_refs"]
        refs.extend([{"id":"FROM","kind":"model","locator":"docs/from"},{"id":"TO","kind":"model","locator":"docs/to"}])
        spec["states"][0]["source_refs"]=["FROM"]
        spec["states"][1]["source_refs"]=["TO"]
        result=design_methods(value)
        valid=next(c for c in result["candidates"] if c["method_data"]["validity"]=="valid")
        self.assertEqual({r["id"] for r in valid["source_refs"]},{"SRC","FROM","TO","EFFECT"})
        denial=next(c for c in result["candidates"] if c["method_data"]["from_state"]=="b")
        self.assertEqual({r["id"] for r in denial["source_refs"]},{"SRC","TO"})
        conflict=copy.deepcopy(spec["transitions"][0]); conflict.update(id="conflict",to_state="z")
        spec["transitions"].append(conflict)
        result=design_methods(value)
        obligation=next(o for o in result["obligations"] if o["code"]=="STATE_CONFLICT")
        self.assertEqual({r["id"] for r in obligation["source_refs"]},{"SRC","FROM","TO","EFFECT"})
        self.assertEqual([r["id"] for r in obligation["oracle_refs"]],["T"])
