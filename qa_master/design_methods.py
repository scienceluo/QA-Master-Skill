"""Pure, deterministic finite test-design synthesis (CR-010).

The module deliberately accepts data only.  It neither resolves references nor
performs an execution; unresolved semantic information is represented by an
obligation instead of guessed test behaviour.
"""
from __future__ import annotations

from collections import Counter, deque
from hashlib import sha256
import itertools
import json
import re

from .core import DIMENSIONS

_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")
_SECRET = {"password", "token", "cookie", "private_key", "private-key", "privatekey"}
_SOURCE_KINDS = {"requirement", "risk", "contract", "model", "guard", "effect", "change", "defect", "other"}
_ORACLE_KINDS = {"valid", "invalid", "outcome", "transition", "denial", "effect"}


class DesignMethodError(ValueError):
    def __init__(self, code: str): self.code = code; super().__init__(code)


def _fail(code): raise DesignMethodError(code)
def _canon(value):
    try: return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError): _fail("INVALID_JSON_VALUE")
def _digest(value): return sha256(_canon(value)).hexdigest()
def _ident(value, prefix): return prefix + sha256(_canon(value)).hexdigest()[:20].upper()
def _exact(value, keys, code="INVALID_SCHEMA"):
    if not isinstance(value, dict) or set(value) != set(keys): _fail(code)
def _id(value, code="INVALID_ID"):
    if not isinstance(value, str) or not _ID.fullmatch(value): _fail(code)
    return value
def _scalar(v): return isinstance(v, (str, int, bool)) and not isinstance(v, float)
def _scalar_key(v):
    if isinstance(v, bool): return (0, int(v))
    if isinstance(v, int): return (1, v)
    if isinstance(v, str): return (2, v)
    _fail("INVALID_SCALAR")
def _sorted_unique(values, code="DUPLICATE_VALUE"):
    if not isinstance(values, list) or not values or any(not _scalar(x) for x in values): _fail("INVALID_SCALAR")
    result = sorted(values, key=_scalar_key)
    if any(_scalar_key(a) == _scalar_key(b) for a, b in zip(result, result[1:])): _fail(code)
    return result
def _refs(raw, kinds, code):
    if not isinstance(raw, list): _fail(code)
    result = {}
    for ref in raw:
        if not isinstance(ref, dict) or set(ref) not in ({"id","kind","locator"}, {"id","kind","locator","sha256"}): _fail(code)
        rid = _id(ref["id"]); kind = ref["kind"]; locator = ref["locator"]
        if (rid in result or kind not in kinds or not isinstance(locator, str) or len(locator)>512
                or not re.fullmatch(r"(?:[A-Za-z0-9][A-Za-z0-9_.-]*)(?:/[A-Za-z0-9][A-Za-z0-9_.-]*)*", locator)):
            _fail(code)
        if "sha256" in ref and (not isinstance(ref["sha256"], str) or not _HEX.fullmatch(ref["sha256"])): _fail(code)
        result[rid] = {k: ref[k] for k in sorted(ref)}
    return result
def _set_ids(raw, known, code="UNKNOWN_REFERENCE", allow_empty=False):
    if not isinstance(raw, list) or (not raw and not allow_empty): _fail("INVALID_REFERENCE_SET")
    if any(not isinstance(x, str) or x not in known for x in raw) or len(set(raw)) != len(raw): _fail(code)
    return sorted(raw)
def _no_secret(v):
    if isinstance(v, float): _fail("FLOAT_FORBIDDEN")
    if isinstance(v, dict):
        for k,x in v.items():
            if not isinstance(k,str) or k.casefold() in _SECRET: _fail("SECRET_FIELD_FORBIDDEN")
            _no_secret(x)
    elif isinstance(v, list):
        for x in v: _no_secret(x)
    elif not isinstance(v,(str,int,bool,type(None))): _fail("INVALID_JSON_VALUE")


def _load_bundle_json(payload: bytes | str) -> dict:
    def bad_constant(_): _fail("INVALID_JSON")
    def pairs(items):
        out={}
        for k,v in items:
            if k in out: _fail("DUPLICATE_JSON_KEY")
            out[k]=v
        return out
    try:
        if isinstance(payload, bytes): payload=payload.decode("utf-8")
        if not isinstance(payload,str): _fail("INVALID_JSON")
        result=json.loads(payload, object_pairs_hook=pairs, parse_constant=bad_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, DesignMethodError): raise
        _fail("INVALID_JSON")
    if not isinstance(result,dict): _fail("INVALID_BUNDLE")
    if "design_models" in result:
        _no_secret(result["design_models"])
        dm=result["design_models"]
        if isinstance(dm,dict) and isinstance(dm.get("models"),list):
            linked=set()
            for model in dm["models"]:
                if isinstance(model,dict) and isinstance(model.get("requirement_ids"),list):
                    linked.update(x for x in model["requirement_ids"] if isinstance(x,str))
            requirements=result.get("requirements")
            if isinstance(requirements,list):
                for requirement in requirements:
                    if isinstance(requirement,dict) and isinstance(requirement.get("id"),str) and requirement["id"] in linked:
                        _no_secret(requirement)
    return result


def load_bundle_json(payload: bytes | str) -> dict:
    try:
        return _load_bundle_json(payload)
    except DesignMethodError:
        raise
    except (TypeError, ValueError, RecursionError, UnicodeError):
        _fail("INVALID_JSON")


def _decimal(v, precision, scale):
    """Parse canonical decimal text into exact integer units of 10**-scale."""
    if not isinstance(v,str) or not re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?",v) or ("." in v and v.endswith("0")) or v == "-0":
        _fail("INVALID_DECIMAL")
    whole, _, fraction = v.lstrip("-").partition(".")
    digits = (whole + fraction).lstrip("0") or "0"
    if len(digits)>precision or len(fraction)>scale: _fail("INVALID_DECIMAL")
    units = int(whole + fraction) * 10 ** (scale-len(fraction))
    return -units if v.startswith("-") else units
def _number(v, typ, precision, scale):
    if typ=="integer":
        if not isinstance(v,int) or isinstance(v,bool) or len(str(abs(v)))>34: _fail("INVALID_INTEGER")
        return v
    return _decimal(v,precision,scale)
def _numeric_text(v, typ, scale=0):
    if typ == "integer" or not scale: return str(v)
    digits = str(abs(v)).zfill(scale+1)
    text = (digits[:-scale] + "." + digits[-scale:]).rstrip("0").rstrip(".")
    return ("-" if v < 0 else "") + text
def _coverage(name, denom, ready, **counts):
    fields={"state":"UNASSESSED" if not denom else "ASSESSED","denominator_name":name,"denominator":denom,"candidate_ready":ready,"oracle_missing":0,"gap":0,"overlap":0,"conflict":0,"unevaluable":0,"unreachable":0,"out_of_scope":0}
    fields.update(counts); fields["ratio"]={"numerator":ready,"denominator":denom} if denom else None
    return fields
def _candidate(model, refs, oracles, identity, method_data, oracle_ids):
    mid=model["id"]; msh=model["model_sha256"]
    cid=_ident({"model_sha256":msh,"candidate_identity":identity},"TC-MD-")
    reqs=model["requirement_ids"]
    priority=model["priority"]
    return {"id":cid,"title":model["title"],"priority":priority,"trace":reqs,"dimension":model["dimension"],"preconditions":"Review declared model preconditions","data":method_data,"steps":["Prepare the declared finite scenario","Collect evidence for the referenced oracle"],"expected":"Satisfy oracle " + ", ".join(oracle_ids),"model_id":mid,"method":model["method"],"source_refs":[refs[x] for x in model["source_refs"]],"oracle_refs":[oracles[x] for x in oracle_ids],"method_data":method_data,"approval":"DRAFT","evidence_state":"PENDING","validation_action":"NOT_EXECUTED"}
def _obligation(model, refs, oracles, code, subject, oracle_ids=(), status="PENDING"):
    oid=_ident({"model_sha256":model["model_sha256"],"code":code,"subject":subject},"OB-MD-")
    return {"id":oid,"code":code,"model_id":model["id"],"method":model["method"],"status":status,"requirement_ids":model["requirement_ids"],"source_refs":[refs[x] for x in model["source_refs"]],"oracle_refs":[oracles[x] for x in sorted(set(oracle_ids))],"subject":subject}


def _boundary(model, refs, oracles):
    s=model["spec"]; _exact(s, {"numeric_type","origin","step","lower","upper","oracle_by_class"} | ({"precision","scale"} if s.get("numeric_type")=="decimal" else set()))
    typ=s.get("numeric_type");
    if typ not in {"integer","decimal"}: _fail("BOUNDARY_MODEL_INCOMPLETE")
    precision=s.get("precision") if typ=="decimal" else 34; scale=s.get("scale") if typ=="decimal" else 0
    if typ=="decimal" and (not isinstance(precision,int) or isinstance(precision,bool) or not 1<=precision<=34): _fail("INVALID_DECIMAL")
    if typ=="decimal" and (not isinstance(scale,int) or isinstance(scale,bool) or not 0<=scale<=18): _fail("INVALID_DECIMAL")
    origin=_number(s["origin"],typ,precision,scale); step=_number(s["step"],typ,precision,scale)
    if step<=0: _fail("BOUNDARY_MODEL_INCOMPLETE")
    bounds=[]
    for key in ("lower","upper"):
        b=s[key]; _exact(b,{"value","inclusive"})
        if not isinstance(b["inclusive"],bool): _fail("BOUNDARY_MODEL_INCOMPLETE")
        bounds.append((_number(b["value"],typ,precision,scale),b["inclusive"]))
    lo,hi=bounds
    if lo[0]>hi[0] or any((x-origin)%step != 0 for x,_ in bounds): _fail("BOUNDARY_MODEL_INCOMPLETE")
    obc=s["oracle_by_class"]
    if not isinstance(obc,dict) or any(k not in {"IN_DOMAIN","LOWER_INVALID","UPPER_INVALID","BOTH_INVALID"} or not isinstance(v,str) or v not in oracles for k,v in obc.items()): _fail("UNKNOWN_REFERENCE")
    for cls, oracle in obc.items():
        kinds = {"valid"} if cls == "IN_DOMAIN" else {"invalid", "denial"}
        if oracles[oracle]["kind"] not in kinds: _fail("BOUNDARY_ORACLE_KIND_INVALID")
    raw=[lo[0]-step,lo[0],lo[0]+step,hi[0]-step,hi[0],hi[0]+step]
    candidates=[]; obligations=[]; rows=[]; counts=Counter(); classes=Counter()
    for point in sorted(set(raw)):
        value=_numeric_text(point,typ,scale)
        digits=value.lstrip("-").replace(".", "").lstrip("0") or "0"
        represented=len(digits)<=precision
        origins=sorted(name for name,bound in (("lower",lo[0]),("upper",hi[0])) if point in (bound-step,bound,bound+step))
        lower_ok=point>lo[0] or (point==lo[0] and lo[1])
        upper_ok=point<hi[0] or (point==hi[0] and hi[1])
        cls=("IN_DOMAIN" if lower_ok and upper_ok else "BOTH_INVALID" if not lower_ok and not upper_ok else "LOWER_INVALID" if not lower_ok else "UPPER_INVALID") if represented else None
        row={"value":value,"class":cls,"representable":represented,"origins":origins,"candidate_id":None,"obligation_ids":[]}
        data={"value":value,"class":cls,"originating_bound_positions":origins}
        if not represented:
            obligation=_obligation(model,refs,oracles,"BOUNDARY_NEIGHBOR_UNREPRESENTABLE",{"value":value})
            obligations.append(obligation); row["obligation_ids"].append(obligation["id"])
            counts["UNREPRESENTABLE"]+=1
        else:
            classes[cls]+=1
            oracle=obc.get(cls)
            if oracle is None:
                obligation=_obligation(model,refs,oracles,"BOUNDARY_ORACLE_MISSING",data)
                obligations.append(obligation); row["obligation_ids"].append(obligation["id"])
                counts["ORACLE_MISSING"]+=1
            else:
                case=_candidate(model,refs,oracles,data,data,[oracle])
                case["steps"]=["Set " + model["title"] + " to " + value,
                               "Perform the scenario referenced by " + ", ".join(model["requirement_ids"]),
                               "Collect evidence for oracle " + oracle]
                candidates.append(case); row["candidate_id"]=case["id"]
                counts["CANDIDATE_READY"]+=1
        rows.append(row)
    # Both endpoints lie on the grid; oracle readiness never changes emptiness.
    empty=(lo[0] + (0 if lo[1] else step)) > (hi[0] - (0 if hi[1] else step))
    if empty: obligations.append(_obligation(model,refs,oracles,"BOUNDARY_EMPTY_DOMAIN",{"lower":s["lower"],"upper":s["upper"]}))
    analysis={"requested_positions":6,"distinct_points":len(rows),"representable_points":sum(classes.values()),
              "unrepresentable":counts["UNREPRESENTABLE"],"in_domain":classes["IN_DOMAIN"],
              "lower_invalid":classes["LOWER_INVALID"],"upper_invalid":classes["UPPER_INVALID"],
              "both_invalid":classes["BOTH_INVALID"],"candidate_ready":len(candidates),
              "oracle_missing":counts["ORACLE_MISSING"],"points":rows,
              "classification_counts":{k:counts[k] for k in ("CANDIDATE_READY","ORACLE_MISSING","UNREPRESENTABLE")}}
    return candidates,obligations,_coverage("distinct_points",len(rows),len(candidates),oracle_missing=counts["ORACLE_MISSING"],gap=int(empty),out_of_scope=counts["UNREPRESENTABLE"]),analysis



def _constraint(node, assignment, domains, depth=1, budget=None):
    if depth>8: _fail("DECISION_CONSTRAINT_INVALID")
    if budget is not None:
        budget[0]+=1
        if budget[0]>128: _fail("DECISION_CONSTRAINT_INVALID")
    if not isinstance(node,dict) or not isinstance(node.get("op"),str): _fail("DECISION_CONSTRAINT_INVALID")
    op=node["op"]
    if op in {"eq","ne"}:
        _exact(node,{"op","condition","value"},"DECISION_CONSTRAINT_INVALID"); c=node["condition"]; v=node["value"]
        if c not in domains or not _scalar(v) or _scalar_key(v) not in {_scalar_key(x) for x in domains[c]}: _fail("DECISION_CONSTRAINT_INVALID")
        return (_scalar_key(assignment[c])==_scalar_key(v)) if op=="eq" else (_scalar_key(assignment[c])!=_scalar_key(v))
    if op in {"in","not_in"}:
        _exact(node,{"op","condition","values"},"DECISION_CONSTRAINT_INVALID"); c=node["condition"]; vals=_sorted_unique(node["values"])
        if c not in domains or any(_scalar_key(v) not in {_scalar_key(x) for x in domains[c]} for v in vals): _fail("DECISION_CONSTRAINT_INVALID")
        present=any(_scalar_key(assignment[c])==_scalar_key(x) for x in vals)
        return present if op=="in" else not present
    if op in {"all","any"}:
        _exact(node,{"op","items"},"DECISION_CONSTRAINT_INVALID")
        if not isinstance(node["items"],list) or not node["items"]: _fail("DECISION_CONSTRAINT_INVALID")
        vals=[_constraint(x,assignment,domains,depth+1,budget) for x in node["items"]]
        return all(vals) if op=="all" else any(vals)
    _fail("DECISION_CONSTRAINT_INVALID")

def _evaluate_constraint(node, assignment):
    """Evaluate an already validated AST without rebuilding its domain sets."""
    op=node["op"]
    if op in {"all","any"}:
        values=(_evaluate_constraint(child,assignment) for child in node["items"])
        return all(values) if op=="all" else any(values)
    value=_scalar_key(assignment[node["condition"]])
    if op in {"eq","ne"}:
        equal=value==_scalar_key(node["value"])
        return equal if op=="eq" else not equal
    present=any(value==_scalar_key(item) for item in node["values"])
    return present if op=="in" else not present


def _decision(model, refs, oracles):
    s=model["spec"]; _exact(s,{"conditions","constraints","rules"})
    if not isinstance(s["conditions"],list) or not s["conditions"]: _fail("DECISION_MODEL_INCOMPLETE")
    domains={}
    for c in s["conditions"]:
        _exact(c,{"id","values"}); cid=_id(c["id"])
        if cid in domains: _fail("DUPLICATE_ID")
        domains[cid]=_sorted_unique(c["values"])
    ids=sorted(domains); size=1
    for x in domains.values(): size*=len(x)
    if size>4096: _fail("DECISION_LIMIT_EXCEEDED")
    if not isinstance(s["constraints"],list) or not isinstance(s["rules"],list): _fail("DECISION_MODEL_INCOMPLETE")
    rules=[]; rids=set()
    for r in s["rules"]:
        _exact(r,{"id","when","outcome_id","source_refs","oracle_ref"}); rid=_id(r["id"])
        if rid in rids: _fail("DUPLICATE_ID")
        rids.add(rid); when=r["when"]
        if not isinstance(when,dict) or not isinstance(r["outcome_id"],str) or not r["outcome_id"]: _fail("DECISION_MODEL_INCOMPLETE")
        for k,v in when.items():
            if k not in domains or not _scalar(v) or _scalar_key(v) not in {_scalar_key(x) for x in domains[k]}: _fail("DECISION_MODEL_INCOMPLETE")
        sources=_set_ids(r["source_refs"],refs)
        oracle=r["oracle_ref"]
        if oracle is not None and (not isinstance(oracle,str) or oracle not in oracles): _fail("UNKNOWN_REFERENCE")
        if oracle is not None and oracles[oracle]["kind"] not in {"outcome","effect"}: _fail("DECISION_ORACLE_KIND_INVALID")
        rules.append({"id":rid,"when":dict(sorted(when.items())),"outcome_id":r["outcome_id"],"source_refs":sources,"oracle_ref":oracle})
    rules.sort(key=lambda x:x["id"])
    budget=[0]
    for constraint in s["constraints"]:
        _constraint(constraint,{k:domains[k][0] for k in domains},domains,budget=budget)
    counts={k:0 for k in ("UNIQUE_ORACLE_READY","UNIQUE_ORACLE_MISSING","OVERLAP_ORACLE_READY","OVERLAP_ORACLE_MISSING","CONFLICT","GAP")}
    candidates=[]; obligations=[]; rows=[]; excluded=0
    for values in itertools.product(*(domains[i] for i in ids)):
        assignment=dict(zip(ids,values))
        row={"values":assignment,"admissibility":"EXCLUDED","matched_rule_ids":[],"classification":"EXCLUDED","candidate_id":None,"obligation_ids":[]}
        if not all(_evaluate_constraint(c,assignment) for c in s["constraints"]):
            excluded+=1; rows.append(row); continue
        matched=[r for r in rules if all(_scalar_key(assignment[k])==_scalar_key(v) for k,v in r["when"].items())]
        outcomes={r["outcome_id"] for r in matched}; oracle_set={r["oracle_ref"] for r in matched}
        if not matched: cls="GAP"
        elif len(outcomes)>1 or len(oracle_set)>1: cls="CONFLICT"
        else: cls=("OVERLAP" if len(matched)>1 else "UNIQUE")+("_ORACLE_MISSING" if None in oracle_set else "_ORACLE_READY")
        counts[cls]+=1
        row.update(admissibility="ADMISSIBLE",matched_rule_ids=[r["id"] for r in matched],classification=cls)
        subject={"assignment":assignment}
        oracle_ids=sorted(x for x in oracle_set if x is not None)
        sources=sorted(set(model["source_refs"]).union(*(set(r["source_refs"]) for r in matched)))
        codes=[]
        if cls in {"GAP","CONFLICT"}: codes.append("DECISION_"+cls)
        if cls.startswith("OVERLAP"): codes.append("DECISION_OVERLAP")
        if cls.endswith("MISSING"): codes.append("DECISION_ORACLE_MISSING")
        for code in codes:
            obligation=_obligation(model,refs,oracles,code,subject,oracle_ids)
            obligation["source_refs"]=[refs[x] for x in sources]
            obligations.append(obligation); row["obligation_ids"].append(obligation["id"])
        if cls.endswith("READY"):
            data={"assignment":assignment,"outcome_id":next(iter(outcomes))}
            case=_candidate(model,refs,oracles,data,data,oracle_ids)
            case["source_refs"]=[refs[x] for x in sources]
            candidates.append(case); row["candidate_id"]=case["id"]
        row["obligation_ids"].sort(); rows.append(row)
    ready=counts["UNIQUE_ORACLE_READY"]+counts["OVERLAP_ORACLE_READY"]
    missing=counts["UNIQUE_ORACLE_MISSING"]+counts["OVERLAP_ORACLE_MISSING"]
    overlap=counts["OVERLAP_ORACLE_READY"]+counts["OVERLAP_ORACLE_MISSING"]
    analysis={"universe_size":size,"excluded":excluded,"constraint_unevaluable":0,"admissible":size-excluded,
              "unique":counts["UNIQUE_ORACLE_READY"]+counts["UNIQUE_ORACLE_MISSING"],"overlap":overlap,
              "conflict":counts["CONFLICT"],"gap":counts["GAP"],"unique_oracle_ready":counts["UNIQUE_ORACLE_READY"],
              "unique_oracle_missing":counts["UNIQUE_ORACLE_MISSING"],"overlap_oracle_ready":counts["OVERLAP_ORACLE_READY"],
              "overlap_oracle_missing":counts["OVERLAP_ORACLE_MISSING"],"oracle_ready":ready,"assignments":rows,"classification_counts":counts}
    return candidates,obligations,_coverage("admissible_assignments",size-excluded,ready,oracle_missing=missing,gap=counts["GAP"],overlap=overlap,conflict=counts["CONFLICT"],out_of_scope=excluded),analysis



def _state(model, refs, oracles):
    s=model["spec"]; _exact(s,{"states","initial_state","triggers","transitions","closed_world","closed_world_deny_oracle_ref"})
    if not isinstance(s["states"],list) or not 1<=len(s["states"])<=128: _fail("STATE_MODEL_INCOMPLETE")
    states={}
    for state in s["states"]:
        _exact(state,{"id","terminal","source_refs"}); sid=_id(state["id"])
        if sid in states or not isinstance(state["terminal"],bool): _fail("DUPLICATE_ID")
        states[sid]={"terminal":state["terminal"],"source_refs":_set_ids(state["source_refs"],refs)}
    initial=s["initial_state"]
    if initial not in states: _fail("STATE_INITIAL_INVALID")
    if not isinstance(s["triggers"],list) or any(not isinstance(x,str) or not _ID.fullmatch(x) for x in s["triggers"]) or len(set(s["triggers"]))!=len(s["triggers"]): _fail("INVALID_REFERENCE_SET")
    triggers=sorted(s["triggers"])
    if not isinstance(s["closed_world"],bool): _fail("STATE_MODEL_INCOMPLETE")
    deny=s["closed_world_deny_oracle_ref"]
    if s["closed_world"] and (not triggers or deny not in oracles): _fail("STATE_CLOSED_WORLD_INVALID")
    if s["closed_world"] and oracles[deny]["kind"] != "denial": _fail("STATE_CLOSED_WORLD_INVALID")
    if s["closed_world"] and len(states)*len(triggers)>4096: _fail("STATE_LIMIT_EXCEEDED")
    if not s["closed_world"] and deny is not None: _fail("STATE_CLOSED_WORLD_INVALID")
    if (not isinstance(s["transitions"],list) or len(s["transitions"])>512 or (not triggers and s["transitions"])): _fail("STATE_LIMIT_EXCEEDED")
    grouped={}; seen=set()
    for t in s["transitions"]:
        _exact(t,{"id","validity","from_state","to_state","trigger","guard_refs","effect_refs","source_refs","oracle_ref"})
        tid=_id(t["id"])
        if tid in seen: _fail("DUPLICATE_ID")
        seen.add(tid); valid=t["validity"]
        if valid not in {"valid","invalid"} or t["from_state"] not in states or t["trigger"] not in triggers: _fail("STATE_TRANSITION_INVALID")
        guards=_set_ids(t["guard_refs"],refs,allow_empty=True); effects=_set_ids(t["effect_refs"],refs,allow_empty=True); sources=_set_ids(t["source_refs"],refs)
        oracle=t["oracle_ref"]
        if oracle is not None and oracle not in oracles: _fail("UNKNOWN_REFERENCE")
        if any(refs[x]["kind"]!="guard" for x in guards) or any(refs[x]["kind"]!="effect" for x in effects): _fail("STATE_REFERENCE_KIND_INVALID")
        if oracle is not None and oracles[oracle]["kind"] not in ({"transition","effect"} if valid=="valid" else {"denial"}): _fail("STATE_ORACLE_KIND_INVALID")
        if valid=="valid":
            if t["to_state"] not in states or not effects or states[t["from_state"]]["terminal"]: _fail("STATE_TRANSITION_INVALID")
        elif t["to_state"] is not None: _fail("STATE_TRANSITION_INVALID")
        key=(t["from_state"],t["trigger"]); normal={"validity":valid,"guard_refs":guards,"to_state":t["to_state"],"effect_refs":effects,"source_refs":sources,"oracle_ref":oracle}
        grouped.setdefault(key,[]).append((tid,normal))
    candidates=[]; obligations=[]; edges=[]; explicit_pairs=set()
    for key, entries in sorted(grouped.items()):
        explicit_pairs.add(key[:2]); values={_digest(x[1]) for x in entries}
        subject={"from_state":key[0],"trigger":key[1]}
        if len(values)>1:
            obligations.append(_obligation(model,refs,oracles,"STATE_CONFLICT",subject)); continue
        t=entries[0][1]
        if len(entries)>1: obligations.append(_obligation(model,refs,oracles,"STATE_DUPLICATE",subject))
        if t["validity"]=="valid": edges.append((key[0],t["to_state"],key))
        if t["oracle_ref"] is None:
            obligations.append(_obligation(model,refs,oracles,"STATE_ORACLE_MISSING",subject)); continue
        data={**subject,"guard_refs":t["guard_refs"],"validity":t["validity"],"to_state":t["to_state"]}
        case=_candidate(model,refs,oracles,data,data,[t["oracle_ref"]])
        state_sources=set(states[key[0]]["source_refs"])
        if t["to_state"] is not None: state_sources.update(states[t["to_state"]]["source_refs"])
        case["source_refs"]=[refs[x] for x in sorted(set(model["source_refs"]) | state_sources | set(t["source_refs"]) | set(t["effect_refs"]) | set(t["guard_refs"]))]
        candidates.append(case)
    pairs=[]
    if s["closed_world"]:
        pairs=[(st,tr) for st in sorted(states) for tr in triggers if (st,tr) not in explicit_pairs]
        if len(pairs)>4096: _fail("STATE_LIMIT_EXCEEDED")
        for st,tr in pairs:
            data={"from_state":st,"trigger":tr,"guard_refs":[],"validity":"invalid","to_state":None}
            case=_candidate(model,refs,oracles,data,data,[deny])
            case["source_refs"]=[refs[x] for x in sorted(set(model["source_refs"]) | set(states[st]["source_refs"]))]
            candidates.append(case)
    adjacency={x:[] for x in states}
    for a,b,k in edges: adjacency[a].append((b,k))
    reached={initial}; todo=deque([initial])
    while todo:
        a=todo.popleft()
        for b,_ in adjacency[a]:
            if b not in reached: reached.add(b); todo.append(b)
    unreachable=sorted(set(states)-reached)
    for a,b,k in edges:
        if a not in reached: obligations.append(_obligation(model,refs,oracles,"STATE_UNREACHABLE_TRANSITION",{"from_state":a,"to_state":b,"trigger":k[1]}))
    for obligation in obligations:
        subject=obligation["subject"]; key=(subject["from_state"],subject["trigger"])
        source_ids=set(model["source_refs"]) | set(states[key[0]]["source_refs"])
        oracle_ids=set()
        for _, transition in grouped[key]:
            for field in ("source_refs","guard_refs","effect_refs"): source_ids.update(transition[field])
            if transition["to_state"] is not None: source_ids.update(states[transition["to_state"]]["source_refs"])
            if transition["oracle_ref"] is not None: oracle_ids.add(transition["oracle_ref"])
        obligation["source_refs"]=[refs[x] for x in sorted(source_ids)]
        obligation["oracle_refs"]=[oracles[x] for x in sorted(oracle_ids)]
    rows=[]; counts={k:0 for k in ("VALID_READY","VALID_ORACLE_MISSING","INVALID_READY","INVALID_ORACLE_MISSING","DUPLICATE_VALID_READY","DUPLICATE_VALID_ORACLE_MISSING","DUPLICATE_INVALID_READY","DUPLICATE_INVALID_ORACLE_MISSING","CONFLICT")}
    candidate_lookup={(x["method_data"].get("from_state"),x["method_data"].get("trigger")):x["id"] for x in candidates}
    obligation_lookup={}
    for x in obligations:
        subject=x.get("subject",{})
        if isinstance(subject,dict) and "from_state" in subject: obligation_lookup.setdefault((subject["from_state"],subject["trigger"]),[]).append(x["id"])
    all_keys=sorted(set(grouped) | set(pairs if s["closed_world"] else []))
    for key in all_keys:
        entries=grouped.get(key,[]); rec=sorted(x[0] for x in entries)
        if not entries:
            cls="INVALID_READY"
        elif len({_digest(x[1]) for x in entries})>1:
            cls="CONFLICT"
        else:
            value=entries[0][1]; base="VALID" if value["validity"]=="valid" else "INVALID"; ready=value["oracle_ref"] is not None
            cls=("DUPLICATE_" if len(entries)>1 else "")+base+("_READY" if ready else "_ORACLE_MISSING")
        counts[cls]+=1
        rows.append({"from_state":key[0],"trigger":key[1],"record_ids":rec,"classification":cls,"structurally_reachable":key[0] in reached,"candidate_id":candidate_lookup.get(key),"obligation_ids":sorted(obligation_lookup.get(key,[]))})
    ready=sum(v for k,v in counts.items() if k.endswith("_READY")); missing=sum(v for k,v in counts.items() if k.endswith("_ORACLE_MISSING")); duplicate=sum(v for k,v in counts.items() if k.startswith("DUPLICATE_"))
    unreachable_edges=sum(1 for a,_,_ in edges if a not in reached)
    coverage=_coverage("logical_transition_keys",len(all_keys),ready,unreachable=unreachable_edges,conflict=counts["CONFLICT"],oracle_missing=missing,overlap=duplicate)
    analysis={"state_count":len(states),"trigger_count":len(triggers),"explicit_records":len(s["transitions"]),"logical_keys":len(all_keys),"closed_world_added":len(pairs) if s["closed_world"] else 0,"reachable_states":sorted(reached),"unreachable_states":unreachable,"reachable_transitions":sum(1 for a,_,_ in edges if a in reached),"unreachable_transitions":unreachable_edges,"logical_rows":rows,"classification_counts":counts}
    return candidates,obligations,coverage,analysis

def _normalize_spec(spec):
    """Canonicalize only schema-declared sets; validation still rejects bad shapes."""
    if isinstance(spec, dict):
        result={k:_normalize_spec(v) for k,v in spec.items()}
        for key in ("conditions","rules","states","transitions"):
            if key in result and isinstance(result[key],list):
                result[key].sort(key=lambda x: _canon(x.get("id")) if isinstance(x,dict) else _canon(x))
        for key in ("source_refs","guard_refs","effect_refs","triggers"):
            if key in result and isinstance(result[key],list): result[key].sort(key=_canon)
        if "values" in result and isinstance(result["values"],list):
            result["values"].sort(key=_scalar_key)
        # all/any children and top-level constraints are unordered conjunctions/sets.
        for key in ("items","constraints"):
            if key in result and isinstance(result[key],list): result[key].sort(key=_canon)
        return result
    if isinstance(spec,list): return [_normalize_spec(v) for v in spec]
    return spec


def _used_references(spec, sources, oracles):
    # Traverse schema locations, never arbitrary rule condition names or values.
    records=[spec]
    for field in ("rules","states","transitions"):
        if field in spec:
            if not isinstance(spec[field],list): _fail("INVALID_SCHEMA")
            records.extend(spec[field])
    for record in records:
        if not isinstance(record,dict): _fail("INVALID_SCHEMA")
        for key in ("source_refs","guard_refs","effect_refs"):
            if key in record:
                item=record[key]
                if not isinstance(item,list) or any(not isinstance(x,str) for x in item): _fail("INVALID_REFERENCE_SET")
                sources.update(item)
        for key in ("oracle_ref","closed_world_deny_oracle_ref"):
            item=record.get(key)
            if item is not None:
                if not isinstance(item,str): _fail("UNKNOWN_REFERENCE")
                oracles.add(item)
    if "oracle_by_class" in spec:
        item=spec["oracle_by_class"]
        if not isinstance(item,dict) or any(not isinstance(x,str) for x in item.values()): _fail("UNKNOWN_REFERENCE")
        oracles.update(item.values())


def _model(raw, requirement_map, refs, oracles):
    _exact(raw,{"id","method","title","dimension","requirement_ids","source_refs","spec"})
    mid=_id(raw["id"]); method=raw["method"]
    if method not in {"boundary","decision_table","state_transition"}: _fail("UNKNOWN_METHOD")
    if not isinstance(raw["title"],str) or not raw["title"].strip() or raw["dimension"] not in DIMENSIONS or not isinstance(raw["spec"],dict): _fail("INVALID_MODEL")
    reqs=_set_ids(raw["requirement_ids"],requirement_map,"UNKNOWN_REQUIREMENT")
    for req in reqs: _no_secret(requirement_map[req])
    priority=next((p for p in ("P0","P1","P2","P3") if any(requirement_map[x].get("priority")==p for x in reqs)),"P2")
    result={"id":mid,"method":method,"title":raw["title"].strip(),"dimension":raw["dimension"],"requirement_ids":reqs,"source_refs":_set_ids(raw["source_refs"],refs),"spec":_normalize_spec(raw["spec"]),"priority":priority}
    source_ids=set(result["source_refs"]); oracle_ids=set()
    _used_references(result["spec"],source_ids,oracle_ids)
    if not source_ids.issubset(refs) or not oracle_ids.issubset(oracles): _fail("UNKNOWN_REFERENCE")
    result["model_sha256"]=_digest({"model":{k:result[k] for k in ("id","method","title","dimension","requirement_ids","source_refs","spec")},"sources":[refs[x] for x in sorted(source_ids)],"oracles":[oracles[x] for x in sorted(oracle_ids)],"requirements":[requirement_map[x] for x in reqs]})
    return result

def _design_methods(bundle: dict) -> dict:
    """Return the all-or-nothing DRAFT method projection for a campaign bundle."""
    if not isinstance(bundle,dict) or "design_models" not in bundle: _fail("DESIGN_MODELS_REQUIRED")
    _no_secret(bundle["design_models"]); dm=bundle["design_models"]
    _exact(dm,{"schema_version","source_refs","oracle_refs","models"})
    if dm["schema_version"] != 1 or isinstance(dm["schema_version"],bool): _fail("UNSUPPORTED_SCHEMA_VERSION")
    refs=_refs(dm["source_refs"],_SOURCE_KINDS,"INVALID_SOURCE_REF"); oracles=_refs(dm["oracle_refs"],_ORACLE_KINDS,"INVALID_ORACLE_REF")
    if not isinstance(dm["models"],list) or len(dm["models"])>100: _fail("MODEL_LIMIT_EXCEEDED")
    requirements=bundle.get("requirements")
    if not isinstance(requirements,list): _fail("REQUIREMENTS_REQUIRED")
    requirement_map={}
    for req in requirements:
        if not isinstance(req,dict) or not isinstance(req.get("id"),str) or not req["id"] or req["id"] in requirement_map: _fail("INVALID_REQUIREMENT")
        requirement_map[req["id"]]=req
    models=[]; seen=set()
    for raw in dm["models"]:
        model=_model(raw,requirement_map,refs,oracles)
        if model["id"] in seen: _fail("DUPLICATE_ID")
        seen.add(model["id"]); models.append(model)
    models.sort(key=lambda x:x["id"])
    all_cases=[]; all_obligations=[]; results=[]
    for model in models:
        engine={"boundary":_boundary,"decision_table":_decision,"state_transition":_state}[model["method"]]
        cases, obligations, coverage, analysis=engine(model,refs,oracles)
        cases.sort(key=lambda x:x["id"]); obligations.sort(key=lambda x:x["id"])
        results.append({"model_id":model["id"],"method":model["method"],"input_sha256":model["model_sha256"],"candidate_ids":[x["id"] for x in cases],"obligation_ids":[x["id"] for x in obligations],"coverage":coverage,"analysis":analysis})
        all_cases.extend(cases); all_obligations.extend(obligations)
    all_cases.sort(key=lambda x:x["id"]); all_obligations.sort(key=lambda x:x["id"])
    ids=[x["id"] for x in all_cases+all_obligations]
    if len(ids)!=len(set(ids)): _fail("DESIGN_ID_COLLISION")
    by=Counter(x["method"] for x in models)
    # Unreferenced legacy requirements do not affect method identities.
    normalized={"schema_version":1,"source_refs":[refs[x] for x in sorted(refs)],"oracle_refs":[oracles[x] for x in sorted(oracles)],"models":[{k:m[k] for k in ("id","method","title","dimension","requirement_ids","source_refs","spec")} for m in models]}
    linked=sorted({rid for m in models for rid in m["requirement_ids"]})
    return {"schema_version":1,"status":"DRAFT_UNAPPROVED","execution":"NOT_EXECUTED","input_sha256":_digest({"design_models":normalized,"requirements":[requirement_map[x] for x in linked]}),"model_results":results,"candidates":all_cases,"obligations":all_obligations,"summary":{"model_count":len(models),"candidate_count":len(all_cases),"obligation_count":len(all_obligations),"by_method":dict(sorted(by.items()))}}


def design_methods(bundle: dict) -> dict:
    """Produce an atomic draft, with stable value-free errors for malformed input."""
    try:
        return _design_methods(bundle)
    except DesignMethodError:
        raise
    except (TypeError, KeyError, ValueError, AttributeError, RecursionError, UnicodeError):
        _fail("INVALID_SCHEMA")
