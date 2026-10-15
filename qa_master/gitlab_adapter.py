"""Read-only GitLab REST v4 adapter; no implicit network requests."""
import json,base64
from urllib.parse import quote,urlsplit,urlencode
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from .http_transport import read_bytes

class GitLabError(RuntimeError): pass

class GitLabReader:
    def __init__(self,base_url,token=None,*,allow_http=False,transport=None,max_bytes=2_000_000):
        u=urlsplit(base_url)
        if u.scheme not in ({'http','https'} if allow_http else {'https'}) or not u.hostname or u.username or u.password or u.query or u.fragment or u.path not in ('','/'):
            raise ValueError('GitLab origin URL required (HTTPS by default)')
        if u.scheme=='http' and token:
            raise ValueError('Credentialed GitLab HTTP is forbidden')
        if not isinstance(max_bytes,int) or not 1<=max_bytes<=20_000_000:raise ValueError('Invalid size limit')
        self.origin=base_url.rstrip('/');self.token=token;self.transport=transport or self._network;self.max_bytes=max_bytes

    def _network(self,url,headers):
        try:
            return read_bytes(url,headers,limit=self.max_bytes)
        except (HTTPError,URLError,ValueError) as e:raise GitLabError('GitLab read failed: '+type(e).__name__) from None

    def _get(self,path,params=None):
        if not path.startswith('/') or '..' in path or '://' in path:raise ValueError('Unsafe API path')
        url=self.origin+'/api/v4'+path+('?' + urlencode(params) if params else '')
        headers={'Accept':'application/json','User-Agent':'QA-Master/1.0'}
        if self.token:headers['PRIVATE-TOKEN']=self.token
        try:
            data=self.transport(url,headers)
            if isinstance(data,bytes):
                if len(data)>self.max_bytes:raise GitLabError('Response exceeds limit')
                return json.loads(data.decode('utf-8'))
            if isinstance(data,str):return json.loads(data)
            return data
        except (ValueError,UnicodeError) as e:raise GitLabError('Invalid GitLab JSON') from e

    @staticmethod
    def _project_id(project):
        if not isinstance(project,(int,str)) or not str(project).strip():raise ValueError('Project required')
        return quote(str(project),safe='')

    def project(self,project):
        info=self._get('/projects/'+self._project_id(project))
        if not isinstance(info,dict):raise GitLabError('Invalid project metadata')
        return {key:info.get(key) for key in ('id','path_with_namespace','default_branch','web_url')}

    def tree(self,project,ref='HEAD',max_pages=10):
        if not isinstance(ref,str) or not ref or len(ref)>256 or not 1<=max_pages<=100:raise ValueError('Invalid ref or page limit')
        out=[]
        for page in range(1,max_pages+1):
            result=self._get('/projects/'+self._project_id(project)+'/repository/tree',{'ref':ref,'recursive':'true','per_page':100,'page':page})
            if not isinstance(result,list):raise GitLabError('Invalid tree')
            out.extend({'path':f.get('path'),'type':f.get('type'),'id':f.get('id')} for f in result if isinstance(f,dict))
            if len(result)<100:return out
        raise GitLabError('Tree pagination cap reached')

    def file(self,project,path,ref='HEAD'):
        if not isinstance(path,str) or not path.strip() or path.startswith('/') or '..' in path.split('/'):raise ValueError('Unsafe file path')
        if not isinstance(ref,str) or not ref or len(ref)>256:raise ValueError('Invalid ref')
        obj=self._get('/projects/'+self._project_id(project)+'/repository/files/'+quote(path,safe=''),{'ref':ref})
        if not isinstance(obj,dict) or obj.get('encoding')!='base64' or not isinstance(obj.get('content'),str):raise GitLabError('Invalid file encoding')
        try:
            raw=base64.b64decode(obj['content'],validate=True)
            if len(raw)>self.max_bytes:raise GitLabError('File exceeds limit')
            decoded=raw.decode('utf-8')
        except (ValueError,UnicodeError) as e:raise GitLabError('Cannot decode file') from e
        return {'path':obj.get('file_path') or path,'ref':ref,'blob_id':obj.get('blob_id'),'content':decoded,'provenance':'SOURCE_CODE_UNREVIEWED'}

    def job(self,project,job_id):
        if type(job_id) is not int or job_id < 1:raise ValueError('Positive job ID required')
        result=self._get('/projects/'+self._project_id(project)+'/jobs/'+str(job_id))
        if not isinstance(result,dict):raise GitLabError('Invalid GitLab job metadata')
        return result

    def pipeline(self,project,pipeline_id):
        if type(pipeline_id) is not int or pipeline_id < 1:raise ValueError('Positive pipeline ID required')
        result=self._get('/projects/'+self._project_id(project)+'/pipelines/'+str(pipeline_id))
        if not isinstance(result,dict):raise GitLabError('Invalid GitLab pipeline metadata')
        return result

    def protected_branches(self,project):
        result=self._get('/projects/'+self._project_id(project)+'/protected_branches')
        if not isinstance(result,list) or any(not isinstance(item,dict) or not isinstance(item.get('name'),str) for item in result):
            raise GitLabError('Invalid protected branch metadata')
        return result

    def protected_tags(self,project):
        result=self._get('/projects/'+self._project_id(project)+'/protected_tags')
        if not isinstance(result,list) or any(not isinstance(item,dict) or not isinstance(item.get('name'),str) for item in result):
            raise GitLabError('Invalid protected tag metadata')
        return result
