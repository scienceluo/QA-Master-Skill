"""Bind imported JUnit to a recorded run. Manifest content is NOT authentication."""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from .junit_ingest import ingest_junit
HASH=re.compile(r'^[0-9a-f]{64}$')
@dataclass(frozen=True)
class RunManifest:
    project:str
    build_ref:str
    environment:str
    run_id:str
    junit_sha256:str
    approved_case_ids:tuple[str,...]
    trust_source:str='UNVERIFIED_MANIFEST'
    def validate(self):
        if any(not isinstance(v,str) or not v.strip() for v in (self.project,self.build_ref,self.environment,self.run_id)):
            raise ValueError('Missing run identity or scope')
        if not isinstance(self.junit_sha256,str) or not HASH.fullmatch(self.junit_sha256):
            raise ValueError('Invalid JUnit SHA-256')
        if not self.approved_case_ids or any(not isinstance(v,str) or not v for v in self.approved_case_ids) or len(set(self.approved_case_ids))!=len(self.approved_case_ids):
            raise ValueError('Invalid approved case set')
def _run_signature(report):
    if not isinstance(report,dict) or not isinstance(report.get('runs'),list):
        raise ValueError('Invalid imported JUnit report')
    try:
        return tuple((row['case_id'],row['status'],row['raw_outcome'],row['evidence']) for row in report['runs'])
    except (KeyError,TypeError) as exc:
        raise ValueError('Invalid imported JUnit run') from exc

def bind_junit(ingested:dict,manifest:RunManifest,junit_path:str,*,case_map,verified_source=False)->dict:
    """Reparse the raw JUnit input; never trust a caller-mutated parsed report."""
    manifest.validate()
    raw=Path(junit_path).read_bytes()
    digest=sha256(raw).hexdigest()
    if digest!=manifest.junit_sha256 or digest!=ingested.get('source_sha256'):
        raise ValueError('JUnit artifact digest mismatch')
    reparsed=ingest_junit(junit_path,case_map,max_bytes=len(raw))
    if _run_signature(ingested)!=_run_signature(reparsed):
        raise ValueError('Imported JUnit results do not match raw artifact')
    runs=reparsed['runs']
    allowed=set(manifest.approved_case_ids)
    if len({r.get('case_id') for r in runs})!=len(runs) or any(r.get('case_id') not in allowed for r in runs):
        raise ValueError('Case set mismatch')
    results=[]
    for item in runs:
        row=dict(item)
        row.update({'project':manifest.project,'build_ref':manifest.build_ref,
                    'environment':manifest.environment,'run_id':manifest.run_id,
                    'provenance':'UNVERIFIED_EXTERNAL_ARTIFACT'})
        results.append(row)
    return {'runs':results,'manifest_validated':True,'source_authenticated':False,
            'verification_needed':'Authenticate CI manifest via provider API and protected identity'}
