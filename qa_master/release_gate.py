"""Deterministic, fail-closed release assessment with evidence-backed runs."""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, asdict

VALID={'PASS','FAIL','BLOCKED','NOT_RUN','RUNNING','SKIPPED'}

@dataclass(frozen=True)
class ReleaseAssessment:
    decision: str
    reasons: tuple[str,...]
    counts: dict
    evaluated_cases: int
    evidence_coverage: float
    approval_required: bool = True
    def to_dict(self): return asdict(self)

def assess_release(cases, runs, defects=None, *, approved_case_ids=None, waivers=None, evidence_verifier=None, governance_verifier=None):
    """Never returns an automatic release authorization. All cases need auditable outcomes."""
    if not isinstance(cases,list) or not isinstance(runs,list): raise ValueError('Cases and runs must be lists')
    if not cases: return ReleaseAssessment('BLOCKED',('NO_TEST_CASES',),{},0,0.0)
    ids=[c.get('id') for c in cases if isinstance(c,dict)]
    if len(ids)!=len(cases) or any(not isinstance(i,str) or not i.strip() for i in ids) or len(set(ids))!=len(ids):
        raise ValueError('Cases require distinct nonempty IDs')
    known=set(ids); allowed=set(approved_case_ids or ())
    if not allowed.issubset(known): raise ValueError('Unknown approved case')
    by_case={}; reasons=[]; waivers=waivers or {}
    def governed(kind, record):
        try:
            return callable(governance_verifier) and governance_verifier(kind, record) is True
        except Exception:
            return False
    if not governed('release_scope', {'cases':cases, 'approved_case_ids':sorted(allowed),
                                     'runs':runs,'defects':defects,'waivers':waivers}):
        reasons.append('UNVERIFIED_RELEASE_SCOPE')
    if not isinstance(waivers,dict):raise ValueError('Waivers must be a mapping')
    for record in runs:
        if not isinstance(record,dict):raise ValueError('Invalid run')
        case_id=record.get('case_id');status=record.get('status')
        if case_id not in known:raise ValueError('Orphan test run')
        if case_id in by_case:raise ValueError('Duplicate case result; select an explicit final run')
        if status not in VALID:raise ValueError('Unknown test status')
        by_case[case_id]=record
    counts=Counter(); evidenced=0
    for case_id in ids:
        result=by_case.get(case_id)
        status=result['status'] if result else 'NOT_RUN'
        trusted=False
        if status in ('PASS','FAIL'):
            # Trust is supplied by an authenticated host, never by a JSON flag.
            try:
                trusted=(callable(evidence_verifier) and
                         result.get('provenance') not in ('UNVERIFIED_EXTERNAL_ARTIFACT','CI_ARTIFACT_FETCHED_NOT_ATTESTED') and
                         evidence_verifier(dict(result)) is True)
            except Exception:
                trusted=False
            if not trusted:reasons.append('UNVERIFIED_SOURCE:'+case_id)
        if status in ('PASS','FAIL') and not result.get('evidence'):
            reasons.append('MISSING_EVIDENCE:'+case_id)
            status='BLOCKED'
        if status=='SKIPPED':
            waiver=waivers.get(case_id)
            if (not isinstance(waiver,dict) or not all(waiver.get(k) for k in ('reason','approved_by','scope'))
                or not governed('waiver', {'case_id':case_id,'waiver':waiver})):
                reasons.append('UNAPPROVED_SKIP:'+case_id)
        if status!='PASS' and status!='SKIPPED':reasons.append(status+':'+case_id)
        if case_id not in allowed:reasons.append('CASE_NOT_APPROVED:'+case_id)
        if status=='PASS' and trusted:evidenced+=1
        counts[status]+=1
    if evidenced == 0: reasons.append('NO_EVIDENCED_PASS')
    if defects is None: reasons.append('DEFECT_STATUS_UNKNOWN')
    elif not isinstance(defects,list):raise ValueError('Defects must be a list')
    else:
        for issue in defects:
            if not isinstance(issue,dict) or not issue.get('id') or not issue.get('status'):
                raise ValueError('Defect must have ID and status')
            if issue['status'] not in ('CLOSED','RESOLVED_VERIFIED'):
                reasons.append('OPEN_DEFECT:'+str(issue['id']))
            elif not governed('defect_closure',dict(issue)):
                reasons.append('UNVERIFIED_DEFECT_CLOSURE:'+str(issue['id']))
    return ReleaseAssessment('BLOCKED' if reasons else 'READY_FOR_HUMAN_REVIEW',
        tuple(reasons),dict(counts),len(ids),round(evidenced/len(ids),4))
