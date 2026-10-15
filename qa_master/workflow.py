"""Legacy library workflow API; installed CLI uses application.CampaignApplicationService.

Retained for compatibility. Local records do not authenticate a human or host.
"""
from dataclasses import dataclass,field,asdict
from pathlib import Path
import json
@dataclass(frozen=True)
class VerifiedCompletionReceipt:
    """Non-secret audit metadata returned only by the trusted host verifier."""
    receipt_id:str
    issuer:str
    issued_at:str
    expires_at:str
    binding_sha256:str
    evidence_ref:str

@dataclass
class Step:
    id:str
    depends_on:list[str]=field(default_factory=list)
    required:list[str]=field(default_factory=list)
    approvals:list[str]=field(default_factory=list)
    side_effect:bool=False
    status:str='PENDING'
    result_ref:str|None=None
    completion_binding:dict|None=None
    execution_receipt:dict|None=None
STEPS={
 'requirements':Step('requirements',required=['source']),
 'review':Step('review',['requirements']),
 'baseline':Step('baseline',['review'],approvals=['requirements']),
 'design':Step('design',['baseline']),
 'case_review':Step('case_review',['design'],approvals=['cases']),
 'code_refinement':Step('code_refinement',['case_review'],required=['git_ref']),
 'test_plan':Step('test_plan',['case_review'],required=['jira_project','plan_name','cycle_name'],approvals=['test_plan'],side_effect=True),
 'execution':Step('execution',['case_review','test_plan'],required=['build_ref','environment'],approvals=['execution'],side_effect=True),
 'regression':Step('regression',['execution'],required=['fix_ref'],approvals=['regression'],side_effect=True),
 'report':Step('report',['execution'])
}
@dataclass
class Workflow:
    project:str
    steps:dict[str,Step]=field(default_factory=dict)
    answers:dict=field(default_factory=dict)
    approvals:dict=field(default_factory=dict)
    events:list=field(default_factory=list)
    revision:int=0
    def request(self,targets):
        def include(s):
            if s not in STEPS:raise ValueError('Unknown step')
            if s in self.steps:return
            definition=STEPS[s]
            for dep in definition.depends_on:include(dep)
            self.steps[s]=Step(s,list(definition.depends_on),list(definition.required),list(definition.approvals),definition.side_effect)
        for s in targets:include(s)
        self.events.append({'action':'request','targets':targets})
    def answer(self,name,value):
        val=value.strip() if isinstance(value,str) else value
        state='CONFIRMED_NONE' if val is None or (isinstance(val,str) and val.lower() in ('没有','无','none','no')) else 'PROVIDED'
        answer={'state':state,'value':None if state=='CONFIRMED_NONE' else val}
        if self.answers.get(name)!=answer:
            for step in list(self.steps):
                if name in self.steps[step].required:self.invalidate(step)
        self.answers[name]=answer
        self.events.append({'action':'answer','key':name,'state':state})
    def approve(self,kind,version,scope):
        if kind not in {a for s in STEPS.values() for a in s.approvals}:raise ValueError('Unknown approval')
        if not version or not scope:raise ValueError('Version and scope required')
        self.approvals[kind]={'version':version,'scope':scope}
        self.events.append({'action':'approve','kind':kind,'version':version,'scope':scope})
    def evaluate(self,step):
        x=self.steps[step]
        if x.status=='DONE':return 'DONE'
        if any(self.steps[d].status!='DONE' for d in x.depends_on):return 'PENDING'
        for req in x.required:
            if req not in self.answers:return 'WAITING_INPUT'
            if self.answers[req]['state']=='CONFIRMED_NONE':return 'BLOCKED'
        if any(a not in self.approvals for a in x.approvals):return 'WAITING_APPROVAL'
        return 'READY'
    def complete(self,step,result_ref):
        if step not in self.steps:raise ValueError('Unknown step')
        if self.steps[step].side_effect:
            raise PermissionError('Side-effecting steps require complete_exact and an authenticated external executor')
        if self.evaluate(step)!='READY':raise ValueError('Step not ready')
        if not result_ref:raise ValueError('Result/evidence reference required')
        self.steps[step].status='DONE';self.steps[step].result_ref=result_ref
        self.events.append({'action':'complete','step':step,'result_ref':result_ref})
    def next_actions(self):
        return [{'step':k,'state':self.evaluate(k)} for k in self.steps if self.steps[k].status!='DONE']
    def invalidate(self,step):
        if step not in self.steps:raise ValueError('Unknown step')
        affected={step}
        while True:
            old=len(affected)
            affected.update(k for k,v in self.steps.items() if any(d in affected for d in v.depends_on))
            if len(affected)==old:break
        for name in affected:
            prior=self.steps[name]
            if prior.result_ref is not None or prior.execution_receipt is not None:
                self.events.append({'action':'invalidated_completion','step':name,
                                    'result_ref':prior.result_ref,
                                    'completion_binding':prior.completion_binding,
                                    'execution_receipt':prior.execution_receipt})
            self.steps[name].status='PENDING';self.steps[name].result_ref=None
            self.steps[name].completion_binding=None
            self.steps[name].execution_receipt=None
            for approval in self.steps[name].approvals:self.approvals.pop(approval,None)
        self.events.append({'action':'invalidate','affected':sorted(affected)})
        return sorted(affected)
    def save(self,path):
        from .state_store import save_document
        persisted=save_document(path,asdict(self),expected_revision=self.revision)
        self.revision=persisted['revision']
    @classmethod
    def load(cls,path):
        from .state_store import load_document
        raw=load_document(path)
        raw['steps']={k:Step(**v) for k,v in raw['steps'].items()}
        return cls(**raw)

    def approve_exact(self,kind,scope,artifact,reviewer):
        """Explicit exact-artifact approval; record is persisted with workflow."""
        from .approval import approve_artifact,approval_record
        if kind not in {a for s in STEPS.values() for a in s.approvals}:raise ValueError('Unknown approval')
        record=approval_record(approve_artifact(kind=kind,project=self.project,scope=scope,
                                                 artifact=artifact,reviewer=reviewer))
        self.approvals[kind]=record
        self.events.append({'action':'approve_exact','kind':kind,'scope':scope,
                            'artifact_sha256':record['artifact_sha256']})
        return record

    def evaluate_exact(self,step,artifacts,scopes):
        """Fail closed on legacy version-only approvals and any stale artifact."""
        from .approval import check_approval
        # Validate bound ancestors first, including when this step is already DONE.
        # Unbound legacy-library completions retain their compatibility behavior;
        # the canonical application never accepts them as revalidated evidence.
        for dependency in self.steps[step].depends_on:
            ancestor=self.steps[dependency]
            if ancestor.status=='DONE' and ancestor.completion_binding is not None:
                if self.evaluate_exact(dependency,artifacts,scopes)=='STALE':
                    return 'STALE'
        if self.steps[step].status=='DONE':
            if self.steps[step].completion_binding != self._completion_binding(step,artifacts,scopes):
                self.invalidate(step)
                return 'STALE'
            return 'DONE'
        state=self.evaluate(step)
        if state!='READY':return state
        for kind in self.steps[step].approvals:
            if kind not in artifacts or kind not in scopes or not check_approval(
                self.approvals.get(kind),kind=kind,project=self.project,
                scope=scopes[kind],artifact=artifacts[kind]):
                return 'WAITING_APPROVAL'
        return 'READY'

    def _completion_binding(self,step,artifacts,scopes):
        from .approval import artifact_digest
        definition=self.steps[step]
        kinds=definition.approvals
        return {'artifacts_sha256':artifact_digest({k:artifacts.get(k) for k in kinds} if kinds else artifacts),
                'scopes_sha256':artifact_digest({k:scopes.get(k) for k in kinds} if kinds else scopes),
                'answers_sha256':artifact_digest({k:self.answers.get(k) for k in definition.required}),
                'approvals_sha256':artifact_digest({k:self.approvals.get(k) for k in kinds}),
                'dependencies_sha256':artifact_digest({k:{'result_ref':self.steps[k].result_ref,
                    'binding':self.steps[k].completion_binding,
                    'receipt':self.steps[k].execution_receipt} for k in definition.depends_on})}

    def complete_exact(self,step,result_ref,artifacts,scopes,*,receipt=None,verifier=None):
        if self.evaluate_exact(step,artifacts,scopes)!='READY':
            raise PermissionError('Exact artifact approval or step prerequisites missing')
        if not result_ref:raise ValueError('Result/evidence reference required')
        if self.steps[step].side_effect:
            from .approval import artifact_digest
            binding={'project':self.project,'step':step,'result_ref':result_ref,
                     'artifacts_sha256':artifact_digest(artifacts),'scopes':dict(scopes),
                     'answers_sha256':artifact_digest(self.answers),
                     'approvals_sha256':artifact_digest(self.approvals)}
            try:
                verified=verifier(receipt,binding) if callable(verifier) else None
                valid=(isinstance(verified,VerifiedCompletionReceipt) and
                       all(isinstance(v,str) and v.strip() for v in asdict(verified).values()) and
                       verified.binding_sha256==artifact_digest(binding) and verified.evidence_ref==result_ref)
            except Exception:valid=False
            if not valid:raise PermissionError('Typed trusted host execution receipt required')
            self.steps[step].execution_receipt=asdict(verified)
        self.steps[step].status='DONE';self.steps[step].result_ref=result_ref
        self.steps[step].completion_binding=self._completion_binding(step,artifacts,scopes)
        self.events.append({'action':'complete_exact','step':step,'result_ref':result_ref,
                            'execution_receipt':self.steps[step].execution_receipt})
