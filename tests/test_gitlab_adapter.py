import base64,unittest
from urllib.parse import parse_qs,urlsplit
from qa_master.gitlab_adapter import GitLabReader,GitLabError
class GitLabAdapterTests(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        def fake(url,headers):
            self.calls.append((url,headers))
            if '/repository/tree' in url:return []
            if '/repository/files/' in url:return {'encoding':'base64','content':base64.b64encode(b'def a(): pass').decode(),'file_path':'src/a.py','blob_id':'abc'}
            return {'id':1,'path_with_namespace':'group/repo','default_branch':'main','web_url':'https://git.example/group/repo'}
        self.c=GitLabReader('https://git.example','fake-secret',transport=fake)
    def test_project(self):self.assertEqual(self.c.project('group/repo')['id'],1)
    def test_encode_project(self):
        self.c.project('group/repo');self.assertIn('group%2Frepo',self.calls[0][0])
    def test_header(self):
        self.c.project(1);self.assertEqual(self.calls[0][1]['PRIVATE-TOKEN'],'fake-secret')
    def test_tree(self):self.assertEqual(self.c.tree(1),[])
    def test_tree_ref(self):
        self.c.tree(1,'release/x');self.assertEqual(parse_qs(urlsplit(self.calls[0][0]).query)['ref'],['release/x'])
    def test_file(self):self.assertEqual(self.c.file(1,'src/a.py')['content'],'def a(): pass')
    def test_unreviewed(self):self.assertEqual(self.c.file(1,'src/a.py')['provenance'],'SOURCE_CODE_UNREVIEWED')
    def test_http_rejected(self):
        with self.assertRaises(ValueError):GitLabReader('http://git.example')
    def test_http_explicit_optin_without_credential(self):self.assertEqual(GitLabReader('http://git.example',allow_http=True).origin,'http://git.example')
    def test_http_explicit_optin_rejects_credential(self):
        with self.assertRaises(ValueError):GitLabReader('http://git.example','fake-secret',allow_http=True)
    def test_url_credentials_rejected(self):
        with self.assertRaises(ValueError):GitLabReader('https://u:pass@git.example')
    def test_url_path_rejected(self):
        with self.assertRaises(ValueError):GitLabReader('https://git.example/team/project')
    def test_path_traversal_rejected(self):
        with self.assertRaises(ValueError):self.c.file(1,'../x')
    def test_size_limit(self):
        c=GitLabReader('https://git.example',transport=self.c.transport,max_bytes=2)
        with self.assertRaises(GitLabError):c.file(1,'src/a.py')
    def test_invalid_json(self):
        c=GitLabReader('https://git.example',transport=lambda url,headers:b'bad')
        with self.assertRaises(GitLabError):c.project(1)
    def test_page_cap(self):
        c=GitLabReader('https://git.example',transport=lambda url,headers:[{'path':'x','type':'blob'}]*100)
        with self.assertRaises(GitLabError):c.tree(1,max_pages=1)
