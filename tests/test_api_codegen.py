import ast
import unittest
import types
from unittest.mock import patch, Mock
from qa_master.api_codegen import generate_pytest, validate_scenarios
GOOD={"method":"GET","path":"/health","expected_statuses":[200],"approved":True}
class ApiCodegenTests(unittest.TestCase):
    def test_credentialed_http_never_sends_request(self):
        fake_pytest=types.SimpleNamespace(mark=types.SimpleNamespace(parametrize=lambda *args:lambda f:f))
        fake_requests=types.SimpleNamespace(request=Mock())
        namespace={'__file__':'synthetic_generated_test.py'}
        with patch.dict('sys.modules',{'pytest':fake_pytest,'requests':fake_requests}):
            exec(compile(generate_pytest([GOOD]),'synthetic_generated_test.py','exec',optimize=1),namespace)
        with patch.dict('os.environ',{'QA_EXECUTION_APPROVED':'YES','QA_TARGET_URL':'http://example.test','QA_API_TOKEN':'synthetic-only'},clear=True):
            with self.assertRaisesRegex(PermissionError,'Credentials require HTTPS'):
                namespace['test_approved_api_scenario'](namespace['SCENARIOS'][0],lambda binding:True)
        fake_requests.request.assert_not_called()
    def test_optimized_source_keeps_authorization_guards(self):
        fake_pytest=types.SimpleNamespace(mark=types.SimpleNamespace(parametrize=lambda *args:lambda f:f))
        fake_requests=types.SimpleNamespace(request=Mock())
        for scenario,env,authorizer in (
            (GOOD,{},lambda _:True),
            (GOOD,{'QA_EXECUTION_APPROVED':'YES','QA_TARGET_URL':'https://example.test'},lambda _:False),
            (dict(GOOD,method='POST',allow_mutation=True),{'QA_EXECUTION_APPROVED':'YES','QA_TARGET_URL':'https://example.test'},lambda _:True),
        ):
            namespace={'__file__':'synthetic_generated_test.py'}
            with patch.dict('sys.modules',{'pytest':fake_pytest,'requests':fake_requests}):
                exec(compile(generate_pytest([scenario]),'generated.py','exec',optimize=1),namespace)
            with patch.dict('os.environ',env,clear=True):
                with self.assertRaises(PermissionError):
                    namespace['test_approved_api_scenario'](namespace['SCENARIOS'][0],authorizer)
        fake_requests.request.assert_not_called()
    def test_valid(self):
        ast.parse(generate_pytest([GOOD]))
    def test_requires_execution_approval(self):
        self.assertIn("QA_EXECUTION_APPROVED",generate_pytest([GOOD]))
    def test_requires_target(self):
        self.assertIn("QA_TARGET_URL",generate_pytest([GOOD]))
    def test_requires_mutation_approval(self):
        self.assertIn("QA_MUTATION_APPROVED",generate_pytest([dict(GOOD,method="POST",allow_mutation=True)]))
    def test_missing_cases(self):
        with self.assertRaises(ValueError):generate_pytest([])
    def test_case_unapproved(self):
        with self.assertRaises(ValueError):generate_pytest([dict(GOOD,approved=False)])
    def test_no_expected_status(self):
        with self.assertRaises(ValueError):generate_pytest([dict(GOOD,expected_statuses=[])])
    def test_str_status(self):
        with self.assertRaises(ValueError):generate_pytest([dict(GOOD,expected_statuses=["200"])])
    def test_unresolved_parameters(self):
        with self.assertRaises(ValueError):generate_pytest([dict(GOOD,path="/users/{id}")])
    def test_path_traversal(self):
        with self.assertRaises(ValueError):generate_pytest([dict(GOOD,path="/../admin")])
    def test_absolute_url(self):
        with self.assertRaises(ValueError):generate_pytest([dict(GOOD,path="https://example.com/api")])
    def test_mutation_disallowed(self):
        with self.assertRaises(ValueError):generate_pytest([dict(GOOD,method="DELETE")])
    def test_explicit_mutation(self):
        ast.parse(generate_pytest([dict(GOOD,method="POST",allow_mutation=True,json_body={"a":1})]))
    def test_body_validation(self):
        with self.assertRaises(ValueError):validate_scenarios([dict(GOOD,json_body="bad")])
    def test_json_oracle(self):
        self.assertIn("response.json()",generate_pytest([dict(GOOD,expected_json={"ok":True})]))
    def test_multiple_cases(self):
        self.assertEqual(len(validate_scenarios([GOOD,dict(GOOD,path="/ready")])),2)
