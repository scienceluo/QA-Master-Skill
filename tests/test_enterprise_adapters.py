import json
import tempfile
import unittest
from pathlib import Path

from qa_master.jira_adapter import AdapterError, HttpResponse, JiraAdapter
from qa_master.sync_journal import OperationJournal, SynapseRTAdapter, SynapseRTProfile, WriteCoordinator
from qa_master.wiki_adapter import ConfluenceReader


class RecordingTransport:
    def __init__(self, result=None):
        self.calls, self.result = [], result or HttpResponse(200, {"ok": True})
    def __call__(self, method, url, headers, body=None):
        self.calls.append((method, url, headers, body))
        return self.result


class EnterpriseAdapterTests(unittest.TestCase):
    def test_jira_reads_documented_v2_paths(self):
        transport = RecordingTransport()
        jira = JiraAdapter("https://jira.example", "secret-token", transport=transport,create_reconciliation_resolver=lambda **kwargs: [])
        jira.project("QA")
        jira.issue("QA-7")
        self.assertEqual([call[1] for call in transport.calls], ["https://jira.example/rest/api/2/project/QA", "https://jira.example/rest/api/2/issue/QA-7"])

    def test_confluence_page_is_read_only_and_uses_v2_route(self):
        transport = RecordingTransport()
        reader = ConfluenceReader("https://wiki.example", "secret-token", transport=transport)
        reader.page("123", include_body=True)
        self.assertEqual(transport.calls[0][0], "GET")
        self.assertIn("https://wiki.example/wiki/api/v2/pages/123?", transport.calls[0][1])
        self.assertIn("body-format=storage", transport.calls[0][1])
        self.assertFalse(hasattr(reader, "update_page"))

    def test_jira_scope_tamper_performs_no_write(self):
        transport = RecordingTransport()
        jira = JiraAdapter("https://jira.example", "secret-token", transport=transport,create_reconciliation_resolver=lambda **kwargs: [])
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(PermissionError):
            jira.create_issue("QA", {"project": {"key": "QA"}, "summary": "x"}, coordinator=WriteCoordinator(OperationJournal(Path(directory)/"journal.json"),jira), idempotency_key="jira-1", verifier=lambda **kwargs: kwargs["target"] == "jira-project:OTHER:issue")
        self.assertEqual(transport.calls, [])

    def test_jira_write_is_journaled_and_readback_matched(self):
        def transport(method,url,headers,body=None):
            if method=="POST":return HttpResponse(201,{"key":"QA-1"})
            return HttpResponse(200,{"key":"QA-1","fields":{"summary":"x","project":{"key":"QA"}}})
        seen = {}
        jira = JiraAdapter("https://jira.example", "secret-token", transport=transport,create_reconciliation_resolver=lambda **kwargs: [])
        with tempfile.TemporaryDirectory() as directory:
            coordinator=WriteCoordinator(OperationJournal(Path(directory)/"journal.json"),jira)
            created=jira.create_issue("QA", {"summary": "x", "project": {"key": "QA"}}, coordinator=coordinator,idempotency_key="jira-1",verifier=lambda **kwargs: seen.update(kwargs) is None or True)
            verified=coordinator.reconcile("jira-1",matches=JiraAdapter.matches_readback)
        self.assertEqual(created["state"],"SUBMITTED")
        self.assertEqual(verified["state"],"VERIFIED")
        self.assertEqual(seen["action"], "jira.issue.create")
        self.assertEqual(seen["target"], "jira-project:QA:issue")
        self.assertEqual(seen["canonical_payload"], b'{"fields":{"project":{"key":"QA"},"summary":"x"}}')

    def test_jira_lost_response_restart_never_reposts(self):
        calls=[]
        def transport(method,url,headers,body=None):
            calls.append(method)
            if method=="POST":raise OSError("response lost")
            return HttpResponse(200,{})
        jira=JiraAdapter("https://jira.example","secret-token",transport=transport,create_reconciliation_resolver=lambda **kwargs: [])
        with tempfile.TemporaryDirectory() as directory:
            journal=OperationJournal(Path(directory)/"journal.json")
            first=jira.create_issue("QA",{"summary":"x","project":{"key":"QA"}},coordinator=WriteCoordinator(journal,jira),idempotency_key="jira-1",verifier=lambda **kwargs:True)
            resumed=jira.create_issue("QA",{"summary":"x","project":{"key":"QA"}},coordinator=WriteCoordinator(OperationJournal(Path(directory)/"journal.json"),jira),idempotency_key="jira-1",verifier=lambda **kwargs:True)
        self.assertEqual(first["state"],"UNKNOWN")
        self.assertEqual(resumed["state"],"UNKNOWN")
        self.assertEqual(calls,["POST"])

    def test_jira_lost_create_uses_one_trusted_resolver_candidate(self):
        def transport(method,url,headers,body=None):
            if method=="POST":raise OSError("response lost")
            return HttpResponse(200,{"key":"QA-9","fields":{"summary":"x","project":{"key":"QA"}}})
        jira=JiraAdapter("https://jira.example","secret-token",transport=transport,create_reconciliation_resolver=lambda **kwargs:["QA-9"])
        with tempfile.TemporaryDirectory() as directory:
            coordinator=WriteCoordinator(OperationJournal(Path(directory)/"journal.json"),jira)
            jira.create_issue("QA",{"summary":"x","project":{"key":"QA"}},coordinator=coordinator,idempotency_key="jira-1",verifier=lambda **kwargs:True)
            result=coordinator.reconcile("jira-1",matches=JiraAdapter.matches_readback)
        self.assertEqual(result["state"],"VERIFIED")

    def test_jira_readback_error_keeps_create_key_for_later_reconciliation(self):
        reads=[OSError("temporary"),HttpResponse(200,{"key":"QA-1","fields":{"summary":"x","project":{"key":"QA"}}})]
        def transport(method,url,headers,body=None):
            if method=="POST":return HttpResponse(201,{"key":"QA-1"})
            value=reads.pop(0)
            if isinstance(value,Exception):raise value
            return value
        jira=JiraAdapter("https://jira.example","secret-token",transport=transport,create_reconciliation_resolver=lambda **kwargs:[])
        with tempfile.TemporaryDirectory() as directory:
            coordinator=WriteCoordinator(OperationJournal(Path(directory)/"journal.json"),jira)
            coordinator.submit("jira-1",action="jira.issue.create",target="jira-project:QA:issue",payload={"fields":{"summary":"x","project":{"key":"QA"}}},verifier=lambda **kwargs:True)
            first=coordinator.reconcile("jira-1",matches=JiraAdapter.matches_readback)
            second=coordinator.reconcile("jira-1",matches=JiraAdapter.matches_readback)
        self.assertEqual(first["state"],"UNKNOWN")
        self.assertEqual(first["remote_result"],{"key":"QA-1"})
        self.assertEqual(second["state"],"VERIFIED")

    def test_jira_readback_accepts_enriched_submitted_objects_but_rejects_changed_values(self):
        payload={"fields":{"project":{"key":"QA"},"assignee":{"accountId":"u1"},"options":[{"id":"7"}],"summary":"x"}}
        enriched={"fields":{"project":{"id":"100","key":"QA","name":"QA"},"assignee":{"accountId":"u1","displayName":"User"},"options":[{"id":"7","value":"extra"}],"summary":"x"}}
        changed={"fields":{"project":{"id":"100","key":"OTHER"},"assignee":{"accountId":"u1"},"options":[{"id":"7"}],"summary":"x"}}
        jira=JiraAdapter("https://jira.example","secret-token")
        self.assertTrue(jira._issue_matches(payload,enriched))
        self.assertFalse(jira._issue_matches(payload,changed))

    def test_jira_lost_create_multiple_candidates_and_manual_recovery_require_approval(self):
        def transport(method,url,headers,body=None):
            if method=="POST":raise OSError("response lost")
            return HttpResponse(200,{"key":"QA-9","fields":{"summary":"x","project":{"key":"QA"}}})
        jira=JiraAdapter("https://jira.example","secret-token",transport=transport,create_reconciliation_resolver=lambda **kwargs:["QA-8","QA-9"])
        with tempfile.TemporaryDirectory() as directory:
            coordinator=WriteCoordinator(OperationJournal(Path(directory)/"journal.json"),jira)
            jira.create_issue("QA",{"summary":"x","project":{"key":"QA"}},coordinator=coordinator,idempotency_key="jira-1",verifier=lambda **kwargs:True)
            unresolved=coordinator.reconcile("jira-1",matches=JiraAdapter.matches_readback)
            self.assertEqual(unresolved["state"],"UNKNOWN")
            with self.assertRaises(PermissionError):
                coordinator.reconcile_manual("jira-1",candidate_key="QA-9",verifier=lambda **kwargs:False,matches=JiraAdapter.matches_readback)
            result=coordinator.reconcile_manual("jira-1",candidate_key="QA-9",verifier=lambda **kwargs:True,matches=JiraAdapter.matches_readback)
        self.assertEqual(result["state"],"VERIFIED")

    def test_transport_error_does_not_expose_token(self):
        def fail(*args):
            raise OSError("connection failed secret-token")
        jira = JiraAdapter("https://jira.example", "secret-token", transport=fail)
        with self.assertRaises(AdapterError) as raised:
            jira.project("QA")
        self.assertNotIn("secret-token", str(raised.exception))

    def test_profile_required_and_contract_is_explicit(self):
        with self.assertRaises(AdapterError):
            SynapseRTAdapter(None, "token")
        with self.assertRaises(ValueError):
            SynapseRTProfile("test", "https://synapse.example", {"plan.create": {"method": "POST", "path": "plans"}})


class FakeAdapter:
    def __init__(self, *, lose_response=False, observed=None):
        self.lose_response, self.observed, self.writes = lose_response, observed, 0
    def write(self, **kwargs):
        self.writes += 1
        if self.lose_response:
            raise OSError("response lost after service may have written")
        return {"id": "remote-1"}
    def readback(self, **kwargs):
        return self.observed


class JournalContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "journal.json"
        self.payload = {"name": "plan", "cases": ["C-1"]}
        self.approve = lambda **kwargs: kwargs["action"] == "synapse.plan.create" and kwargs["target"] == "test-project"
    def tearDown(self):
        self.temp.cleanup()

    def test_lost_write_response_survives_restart_without_retry(self):
        adapter = FakeAdapter(lose_response=True)
        first = WriteCoordinator(OperationJournal(self.path), adapter).submit("id-1", action="synapse.plan.create", target="test-project", payload=self.payload, verifier=self.approve)
        self.assertEqual(first["state"], "UNKNOWN")
        resumed = WriteCoordinator(OperationJournal(self.path), adapter).submit("id-1", action="synapse.plan.create", target="test-project", payload=self.payload, verifier=self.approve)
        self.assertEqual(resumed["state"], "UNKNOWN")
        self.assertEqual(adapter.writes, 1)

    def test_pre_call_claim_survives_crash_without_replay(self):
        journal=OperationJournal(self.path)
        journal.prepare("id-1", action="synapse.plan.create", target="test-project", payload=self.payload)
        journal.claim("id-1", "simulated-crash")
        adapter=FakeAdapter()
        resumed=WriteCoordinator(journal,adapter).submit("id-1", action="synapse.plan.create", target="test-project", payload=self.payload, verifier=self.approve)
        self.assertEqual(resumed["state"],"UNKNOWN")
        self.assertEqual(adapter.writes,0)

    def test_readback_mismatch_is_not_verified(self):
        adapter = FakeAdapter(observed={"name": "other"})
        coordinator = WriteCoordinator(OperationJournal(self.path), adapter)
        coordinator.submit("id-1", action="synapse.plan.create", target="test-project", payload=self.payload, verifier=self.approve)
        result = coordinator.reconcile("id-1", matches=lambda expected, observed: expected == observed)
        self.assertEqual(result["state"], "READBACK_MISMATCH")

    def test_same_key_payload_drift_is_rejected(self):
        journal = OperationJournal(self.path)
        journal.prepare("id-1", action="a", target="t", payload={"x": 1})
        with self.assertRaises(ValueError):
            journal.prepare("id-1", action="a", target="t", payload={"x": 2})

    def test_journal_contains_no_authorization_header(self):
        adapter = FakeAdapter()
        WriteCoordinator(OperationJournal(self.path), adapter).submit("id-1", action="synapse.plan.create", target="test-project", payload=self.payload, verifier=self.approve)
        persisted = self.path.read_text(encoding="utf-8")
        self.assertNotIn("Authorization", persisted)
        self.assertNotIn("token", persisted.lower())

    def test_journal_rejects_secret_like_payload_fields(self):
        with self.assertRaises(ValueError):
            OperationJournal(self.path).prepare("id-1", action="a", target="t", payload={"access_token": "never-persist"})
