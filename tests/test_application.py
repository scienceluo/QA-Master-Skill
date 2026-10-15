"""TASK-020 unit checks; independent acceptance is recorded separately."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from qa_master.application import CampaignApplicationService as Service, migrate
from qa_master.core import Campaign
from qa_master.state_store import StateConflictError
from qa_master.workflow import Workflow


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'state.json'

    def legacy(self):
        campaign = Campaign('中文项目')
        campaign.set_answer('gitlab', 'group/repo')
        campaign.set_answer('requirements', '没有')
        campaign.approve('execution', 'v1')
        campaign.artifacts = {'old': {'nested': [1, 2]}}
        campaign.run_ids = ['old-run']
        campaign.questions = {'requirements': 'answered'}
        raw = asdict(campaign)
        raw.pop('revision')
        raw['extension'] = {'preserve': True}
        self.path.write_text(json.dumps(raw), encoding='utf-8')
        return raw

    def test_legacy_projection_is_deterministic_readonly_and_complete(self):
        raw = self.legacy()
        before = self.path.read_bytes(), self.path.stat().st_mtime_ns
        first, second = Service.load(self.path), Service.load(self.path)
        self.assertEqual(first.document, second.document)
        self.assertEqual(first.document['legacy_payload'], raw)
        self.assertEqual(first.document['legacy_assertions'][0]['assurance'], 'UNVERIFIED_LEGACY')
        first.status(); first.check('execution')
        self.assertEqual(before, (self.path.read_bytes(), self.path.stat().st_mtime_ns))
        self.assertEqual(list(self.path.parent.glob('*.legacy-*')), [])

    def test_first_mutation_backups_exact_bytes_and_migration_is_idempotent(self):
        self.legacy()
        before = self.path.read_bytes()
        service = Service.load(self.path)
        service.mutate('plan', prompt='只生成用例，不执行测试')
        self.assertEqual(service.document['revision'], 1)
        backups = list(self.path.parent.glob('*.legacy-*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), before)
        reloaded = Service.load(self.path)
        self.assertEqual(service.document, reloaded.document)
        self.assertFalse(reloaded.needs_migration)
        reloaded.mutate('answer', key='environment', value='local')
        self.assertEqual(len(list(self.path.parent.glob('*.legacy-*'))), 1)

    def test_init_never_overwrites_revisionless_file(self):
        self.legacy()
        before = self.path.read_bytes()
        with self.assertRaises(StateConflictError):
            Service.initialize(self.path, 'new')
        self.assertEqual(self.path.read_bytes(), before)

    def test_cas_and_same_revision_content_changes_are_rejected(self):
        self.legacy()
        one, two = Service.load(self.path), Service.load(self.path)
        one.mutate('answer', key='build', value='b1')
        with self.assertRaises(StateConflictError):
            two.mutate('pause', reason='wait')
        three = Service.load(self.path)
        modified = json.loads(self.path.read_text(encoding='utf-8'))
        modified['project'] = 'changed without revision'
        self.path.write_text(json.dumps(modified))
        with self.assertRaises(StateConflictError):
            three.mutate('pause', reason='wait')

    def test_pause_reload_rejects_progress_and_resume_preserves_scope(self):
        service = Service.initialize(self.path, 'demo')
        service.mutate('plan', prompt='只生成测试用例')
        service.mutate('pause', reason='waiting')
        before = self.path.read_bytes()
        service = Service.load(self.path)
        for command, payload in [('answer', {'key': 'source', 'value': 'doc'}),
                                 ('approve', {'kind': 'execution', 'version': 'v1'}),
                                 ('plan', {'prompt': '执行测试'})]:
            with self.assertRaisesRegex(PermissionError, 'CAMPAIGN_PAUSED'):
                service.mutate(command, **payload)
        self.assertEqual(self.path.read_bytes(), before)
        service.mutate('resume')
        service.mutate('plan', prompt='执行测试')
        self.assertEqual(service.check('execution')['state'], 'DENIED_BY_TASK_SCOPE')
        self.assertFalse(service.status()['execution_authorized'])

    def test_unknown_ambiguous_and_invalid_inputs_unchanged(self):
        samples = [[], {}, {'schema_name': 'qa-master.campaign', 'schema_version': 999},
                   {'name': 'x', 'known': {}, 'history': [], 'project': 'x'},
                   {'name': 'x', 'known': {}, 'history': [], 'revision': True}]
        for sample in samples:
            self.path.write_text(json.dumps(sample))
            before = self.path.read_bytes()
            with self.assertRaises(ValueError):
                Service.load(self.path)
            self.assertEqual(self.path.read_bytes(), before)

    def test_legacy_workflow_metadata_is_preserved_but_not_authorized(self):
        workflow = Workflow('demo')
        workflow.request(['execution'])
        workflow.approvals = {'execution': {'version': 'v1', 'scope': 'demo'}}
        for step in workflow.steps.values():
            step.status = 'DONE'; step.result_ref = 'old-result'
            step.completion_binding = {'old': 'binding'}
            step.execution_receipt = {'issuer': 'untrusted-old-fixture'}
        raw = asdict(workflow)
        self.path.write_text(json.dumps(raw))
        service = Service.load(self.path)
        self.assertEqual(service.document['legacy_payload'], raw)
        for key, step in service.document['steps'].items():
            expected = dict(raw['steps'][key], status='NEEDS_REVALIDATION')
            self.assertEqual(step, expected)
        self.assertNotIn(service.check('execution')['state'], ('READY', 'DONE'))
        self.assertEqual(service.document['approvals'], {})

    def test_atomic_failure_keeps_original_and_recoverable_backup(self):
        self.legacy()
        original = self.path.read_bytes()
        service = Service.load(self.path)
        with patch('qa_master.state_store.os.replace', side_effect=OSError('injected')):
            with self.assertRaises(OSError):
                service.mutate('pause', reason='wait')
        self.assertEqual(self.path.read_bytes(), original)
        self.assertTrue(Service.load(self.path).needs_migration)
        self.assertEqual(list(self.path.parent.glob('*.legacy-*'))[0].read_bytes(), original)
        self.assertEqual(list(self.path.parent.glob('.qa-master-state-*')), [])

    def test_legacy_approval_is_record_only(self):
        service = Service.initialize(self.path, 'demo')
        result = service.mutate('approve', kind='execution', version='v1')
        self.assertEqual(result['state'], 'RECORDED_UNVERIFIED')
        self.assertEqual(service.document['approvals'], {})

    def test_status_does_not_echo_saved_answer_values(self):
        service = Service.initialize(self.path, 'demo')
        for key in ('token', 'gitlab', 'arbitrary'):
            service.mutate('answer', key=key, value='private-fixture-value')
        service.mutate('answer', key='requirements', value='没有')
        status = Service.load(self.path).status()
        self.assertNotIn('private-fixture-value', json.dumps(status))
        self.assertEqual(status['known']['gitlab']['value'], '[stored]')
        self.assertIsNone(status['known']['requirements']['value'])
        self.assertEqual(service.document['answers']['token']['value'], 'private-fixture-value')

    def test_questions_persist_and_refresh_after_answer(self):
        service = Service.initialize(self.path, 'demo')
        output = service.mutate('plan', prompt='只生成测试用例')
        self.assertEqual(Service.load(self.path).status()['questions'], output['questions'])
        service.mutate('answer', key='gitlab', value='group/repo')
        self.assertIn('正式需求', service.status()['questions'][0])
        service.mutate('answer', key='requirements', value='没有')
        self.assertEqual(Service.load(self.path).status()['questions'], [])

    def test_contract_requires_exact_schema_and_stage_members(self):
        document = Service.initialize(self.path, 'demo').document
        for change in ('missing-version', 'bad-stage', 'extra', 'numeric-false'):
            bad = deepcopy(document)
            contract = bad['task_contract']
            if change == 'missing-version': contract.pop('schema_version')
            if change == 'bad-stage': contract['stages'] = [123]
            if change == 'extra': contract['override'] = True
            if change == 'numeric-false': contract['capabilities']['execute'] = 0
            self.path.write_text(json.dumps(bad), encoding='utf-8')
            with self.assertRaises(ValueError): Service.load(self.path)

    def test_recursive_exact_ancestor_change_invalidates_completed_descendant(self):
        workflow = Workflow('demo'); workflow.request(['design'])
        workflow.answer('source', 'doc')
        artifacts = {'requirements': {'text': 'v1'}}
        scopes = {'requirements': 'demo'}
        workflow.complete_exact('requirements', 'req', artifacts, scopes)
        workflow.complete_exact('review', 'review', artifacts, scopes)
        workflow.approve_exact('requirements', 'demo', artifacts['requirements'], 'local-reviewer')
        workflow.complete_exact('baseline', 'baseline', artifacts, scopes)
        workflow.complete_exact('design', 'cases', artifacts, scopes)
        artifacts['requirements']['text'] = 'changed'
        self.assertEqual(workflow.evaluate_exact('design', artifacts, scopes), 'STALE')
        self.assertEqual(workflow.steps['design'].status, 'PENDING')
        self.assertTrue(any(event['action'] == 'invalidated_completion' for event in workflow.events))

