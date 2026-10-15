"""One-command offline campaign draft. Never executes tests or approves requirements."""
from __future__ import annotations
import argparse,hashlib,json,os,tempfile
from pathlib import Path
from .quality import analyze_requirements,review_cases
from .coverage_design import design_matrix
from .design_methods import DesignMethodError, design_methods, load_bundle_json

def prepare_campaign(bundle):
    if not isinstance(bundle,dict):raise ValueError("Expected JSON object")
    project=bundle.get("project");requirements=bundle.get("requirements")
    if not isinstance(project,str) or not project.strip():raise ValueError("Project required")
    if not isinstance(requirements,list) or len(requirements)>10000 or not all(isinstance(r,dict) for r in requirements):
        raise ValueError("requirements must be <=10000 objects")
    method_design = design_methods(bundle) if 'design_models' in bundle else None
    requirements_review=analyze_requirements(requirements)
    design=design_matrix(requirements,applicable=bundle.get("applicability"))
    approved={str(r["id"]) for r in requirements if r.get("approved") is True and r.get("id")}
    case_review=review_cases(design["cases"],approved)
    digest=hashlib.sha256(json.dumps(bundle,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    report = {"schema_version":1,"project":project.strip(),"input_sha256":digest,
            "requirement_review":requirements_review,"test_cases":design["cases"],
            "coverage":design["coverage"],"case_review":case_review,
            "unresolved":{"requirement_blockers":[f for f in requirements_review["findings"] if f["severity"]=="BLOCKER"],
                          "design_gaps":design["gaps"]},
            "workflow":{"requirements_review":"WAITING_HUMAN_APPROVAL",
                        "test_design":"DRAFT_ONLY","execution":"NOT_AUTHORIZED","synapsert":"NOT_WRITTEN"},
            "formal_baseline_approved":False}
    if method_design is not None:
        report['method_design'] = method_design
    return report

def write_campaign(bundle_path,output_path):
    source=Path(bundle_path).resolve(strict=True);destination=Path(output_path).resolve()
    if destination==source:raise ValueError("Output must not overwrite input")
    if source.stat().st_size>5_000_000:raise ValueError("Input too large")
    payload=source.read_bytes()
    if len(payload)>5_000_000:raise ValueError("Input too large")
    result=prepare_campaign(load_bundle_json(payload))
    destination.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=".qa-master-",suffix=".json",dir=destination.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as out:
            json.dump(result,out,ensure_ascii=False,indent=2);out.write("\n")
        os.replace(tmp,destination)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return result

def main(argv=None):
    p=argparse.ArgumentParser(description="Generate offline QA design and review draft")
    p.add_argument("--input",required=True);p.add_argument("--output",required=True)
    a=p.parse_args(argv)
    try:
        report=write_campaign(a.input,a.output)
    except DesignMethodError as error:
        print(json.dumps({'status':'REJECTED','error':error.code},ensure_ascii=True))
        return 2
    except (ValueError,TypeError,KeyError):
        print(json.dumps({'status':'REJECTED','error':'INVALID_CAMPAIGN_INPUT'},ensure_ascii=True))
        return 2
    except OSError:
        print(json.dumps({'status':'REJECTED','error':'CAMPAIGN_IO_ERROR'},ensure_ascii=True))
        return 2
    summary={"project":report["project"],"cases":len(report["test_cases"]),
      "requirement_findings":len(report["requirement_review"]["findings"]),
      "unresolved_design":len(report["unresolved"]["design_gaps"]),"status":"DRAFT_UNAPPROVED",
      "output":a.output}
    if 'method_design' in report:
        summary.update(method_candidates=report['method_design']['summary']['candidate_count'],
                       method_obligations=report['method_design']['summary']['obligation_count'],
                       execution='NOT_AUTHORIZED')
    print(json.dumps(summary,ensure_ascii=True))
    return 0
if __name__=="__main__":raise SystemExit(main())
