"""Protected enterprise integration primitives: read-only API and dry-run plans."""
from __future__ import annotations
from dataclasses import dataclass
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import json,os,re
from .http_transport import read_bytes
class IntegrationError(RuntimeError):pass
@dataclass(frozen=True)
class Target:
    name:str
    base_url:str
    token_env:str
    def __post_init__(self):
        u=urlsplit(self.base_url)
        if u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment:raise ValueError('Trusted HTTPS origin required')
        if not re.fullmatch(r'[A-Z_][A-Z0-9_]*',self.token_env):raise ValueError('Invalid token variable')
class ReadOnlyConnector:
    def __init__(self,target,transport=None):
        self.target=target
        self.transport=transport or self._http
    @staticmethod
    def _http(url,headers):
        return json.loads(read_bytes(url,headers,limit=2_000_000))
    def read(self,path):
        if not isinstance(path,str) or not path.startswith('/') or path.startswith('//') or '://' in path or '..' in path.split('/') or '#' in path:raise ValueError('Unsafe path')
        token=os.environ.get(self.target.token_env)
        if not token:raise IntegrationError('Missing credential environment variable')
        try:return self.transport(self.target.base_url.rstrip('/')+path,{'Authorization':'Bearer '+token,'Accept':'application/json'})
        except (OSError,ValueError) as e:raise IntegrationError('Read failed: '+type(e).__name__) from None
@dataclass(frozen=True)
class WriteAuthorization:
    project:str
    action:str
    resource:str
    approved_by:str
    artifact_version:str
    def validate(self,project,action,resource,artifact_version):
        if not all((self.project,self.action,self.resource,self.approved_by,self.artifact_version)):raise PermissionError('Incomplete approval')
        if (project,action,resource,artifact_version)!=(self.project,self.action,self.resource,self.artifact_version):raise PermissionError('Approval scope mismatch')
        return True
def build_synapsert_plan(*,project,plan,cycle,case_ids,assignee,approval=None):
    if not all(isinstance(x,str) and x.strip() for x in (project,plan,cycle,assignee)):raise ValueError('Project, plan, cycle and bug assignee required')
    if not case_ids or len(set(case_ids))!=len(case_ids) or not all(isinstance(x,str) and x.strip() for x in case_ids):raise ValueError('Nonempty unique case IDs required')
    from .approval import artifact_digest
    envelope={'schema_version':1,'action':'synapsert.plan','project':project,
              'plan':plan,'cycle':cycle,'case_ids':sorted(case_ids),'assignee':assignee}
    resource='synapsert.plan:'+artifact_digest(envelope)
    version=artifact_digest(envelope)
    verified=approval.validate(project,'synapsert.plan',resource,version) if approval else False
    return {'mode':'DRY_RUN_ONLY','project':project,'plan':plan,'cycle':cycle,'case_ids':list(case_ids),'assignee':assignee,
            'approval_verified':False,'scope_assertion_matches':verified,
            'writes_performed':0,'resource':resource,'case_version':version,'authorization_envelope':envelope}
def validate_machine(host,transport,credential_env):
    if not isinstance(host,str) or not re.fullmatch(r'[A-Za-z0-9.-]{1,253}',host):raise ValueError('Invalid hostname')
    if transport not in ('ssh','winrm','runner'):raise ValueError('Unsupported transport')
    if not re.fullmatch(r'[A-Z_][A-Z0-9_]*',credential_env):raise ValueError('Invalid credential variable')
    return {'host':host,'transport':transport,'credential_env':credential_env,'state':'NOT_CONNECTED'}
