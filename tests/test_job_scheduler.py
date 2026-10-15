"""Synthetic host ports test control flow only; no process or network runs."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from pathlib import Path
import tempfile
import json
import threading
import unittest
from unittest.mock import patch

from qa_master.approval import artifact_digest
from qa_master.job_scheduler import (JobManifest, JobRepository, JobScheduler,
    VerifiedOperationAuthorization, VerifiedJobObservation, ProcessMetadata, EvidenceMetadata, NoNewObservation)
from qa_master.state_store import StateConflictError


def manifest(**changes):
    data = dict(schema_version=1, job_key='job-1', nonce='n' * 16, campaign_id='campaign',
                step_id='execution', project='demo', workflow_revision=2,
                target_id='fixture-target', execution_timeout_seconds=100,
                heartbeat_timeout_seconds=10, cancel_grace_seconds=5,
                evidence_sink_id='fixture-sink', retention_policy_id='fixture-retention')
    for key in ('build', 'case_set', 'command', 'config', 'environment', 'resource_policy', 'evidence_contract'):
        data[key + '_sha256'] = 'a' * 64
    return JobManifest.create(dict(data, **changes))


class SyntheticAuthorization:
    def verify(self, *, action, binding, proof):
        if proof != 'synthetic-only':
            return False
        return VerifiedOperationAuthorization('SYNTHETIC', 'authorization', artifact_digest(binding), 0, 10000)


class SyntheticObservationVerifier:
    def verify(self, *, binding, observation):
        return observation


class SyntheticTransport:
    def __init__(self, clock):
        self.clock = clock
        self.dispatches = self.cancels = 0
        self.operation_id = None
        self.digest = manifest().digest
        self.sequence = 0
        self.next_kind = 'RUNNING'
        self.fail_dispatch = False

    def message(self, kind, **metadata):
        result = VerifiedJobObservation('SYNTHETIC', 'obs-' + str(self.sequence),
                  self.operation_id, self.digest, 'worker-1', self.sequence, self.clock[0], kind, **metadata)
        self.sequence += 1
        return result

    def dispatch(self, *, manifest, operation_id):
        self.dispatches += 1; self.operation_id = operation_id
        if self.fail_dispatch:
            raise RuntimeError('private-error-marker')
        return self.message('DISPATCHED')

    def observe(self, *, operation_id, after_sequence):
        if self.next_kind == 'PROCESS_FINISHED':
            return self.message(self.next_kind, process=ProcessMetadata('EXITED', 0))
        if self.next_kind == 'EVIDENCE_AVAILABLE':
            return self.message(self.next_kind, evidence=EvidenceMetadata('artifact-1', 'b'*64, 100, 'a'*64))
        return self.message(self.next_kind)

    def request_cancel(self, *, operation_id, cancel_operation_id):
        self.cancels += 1
        return self.message('CANCEL_ACCEPTED', cancel_operation_id=cancel_operation_id)

    def reconcile(self, *, operation_id, uncertainty_phase, after_sequence):
        if self.next_kind == 'ABSENT':
            return self.message('ABSENT', authoritative_absence=True)
        return self.observe(operation_id=operation_id, after_sequence=after_sequence)


class JobSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'jobs.json'
        self.clock = [100.0]
        self.transport = SyntheticTransport(self.clock)
        self.scheduler = JobScheduler(JobRepository(self.path), transport=self.transport,
            authorization_verifier=SyntheticAuthorization(), observation_verifier=SyntheticObservationVerifier(),
            clock=lambda: self.clock[0])
        self.job = self.scheduler.prepare(manifest(), idempotency_key='job-1', expected_store_revision=0)

    def dispatch(self):
        self.job = self.scheduler.dispatch(self.job['job_id'], proof='synthetic-only', expected_job_revision=self.job['revision'])
        return self.job

    def observe(self):
        self.job = self.scheduler.observe(self.job['job_id'], expected_job_revision=self.job['revision'])
        return self.job

    def test_manifest_strict_and_prepare_idempotent(self):
        self.assertEqual(manifest().digest, JobManifest.create(asdict(manifest())).digest)
        with self.assertRaises(ValueError): manifest(schema_version=True)
        with self.assertRaises(ValueError): manifest(token='secret')
        with self.assertRaises(ValueError): manifest(target_id='https://example.com')
        self.assertEqual(self.job, self.scheduler.prepare(manifest(), idempotency_key='job-1', expected_store_revision=0))
        with self.assertRaises(ValueError):
            self.scheduler.prepare(manifest(command_sha256='b'*64), idempotency_key='job-1', expected_store_revision=1)

    def test_missing_ports_and_untrusted_authorization_do_not_mutate(self):
        original = self.path.read_bytes()
        bare = JobScheduler(JobRepository(self.path))
        with self.assertRaises(PermissionError): bare.dispatch(self.job['job_id'], proof=True, expected_job_revision=1)
        with self.assertRaises(PermissionError): self.scheduler.dispatch(self.job['job_id'], proof=True, expected_job_revision=1)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.transport.dispatches, 0)

    def test_process_and_evidence_do_not_make_business_verdict(self):
        self.assertEqual(self.dispatch()['state'], 'DISPATCHED')
        self.assertEqual(self.observe()['state'], 'RUNNING')
        self.transport.next_kind = 'PROCESS_FINISHED'
        self.assertEqual(self.observe()['state'], 'PROCESS_FINISHED')
        self.transport.next_kind = 'EVIDENCE_AVAILABLE'
        self.assertEqual(self.observe()['state'], 'EVIDENCE_AVAILABLE')
        self.assertEqual(self.job['business_result'], 'NOT_ASSESSED')
        self.assertEqual(self.job['process']['exit_code'], 0)

    def test_response_loss_restart_and_reconcile_never_redispatch(self):
        self.transport.fail_dispatch = True
        self.assertEqual(self.dispatch()['state'], 'UNKNOWN')
        self.dispatch(); self.assertEqual(self.transport.dispatches, 1)
        self.assertNotIn(b'private-error-marker', self.path.read_bytes())
        reloaded = JobScheduler(JobRepository(self.path), transport=self.transport,
            authorization_verifier=SyntheticAuthorization(), observation_verifier=SyntheticObservationVerifier(), clock=lambda: self.clock[0])
        self.transport.next_kind = 'ABSENT'
        final = reloaded.reconcile(self.job['job_id'], expected_job_revision=self.job['revision'])
        self.assertEqual(final['state'], 'NOT_DISPATCHED')
        reloaded.dispatch(final['job_id'], proof='synthetic-only', expected_job_revision=final['revision'])
        self.assertEqual(self.transport.dispatches, 1)

    def test_cancellation_needs_fresh_proof_and_ack_is_not_termination(self):
        self.dispatch(); self.observe()
        with self.assertRaises(PermissionError):
            self.scheduler.request_cancel(self.job['job_id'], reason='stop', proof=False, expected_job_revision=self.job['revision'])
        self.job = self.scheduler.request_cancel(self.job['job_id'], reason='private-reason-marker', proof='synthetic-only', expected_job_revision=self.job['revision'])
        self.assertEqual(self.job['state'], 'CANCEL_REQUESTED')
        self.assertIsNone(self.job['process'])
        self.assertNotIn(b'private-reason-marker', self.path.read_bytes())
        self.clock[0] += 5
        self.job = self.scheduler.check_timeout(self.job['job_id'], expected_job_revision=self.job['revision'])
        self.assertEqual((self.job['state'], self.job['uncertainty_phase']), ('UNKNOWN', 'CANCEL'))
        self.scheduler.request_cancel(self.job['job_id'], reason='stop', proof='synthetic-only', expected_job_revision=self.job['revision'])
        self.assertEqual(self.transport.cancels, 1)

    def test_heartbeat_and_execution_deadlines_are_not_process_results(self):
        self.dispatch(); self.observe()
        self.clock[0] += 10
        self.job = self.scheduler.check_timeout(self.job['job_id'], expected_job_revision=self.job['revision'])
        self.assertEqual((self.job['state'], self.job['uncertainty_phase']), ('UNKNOWN', 'RUN'))
        self.assertIsNone(self.job['process'])
        self.job = self.scheduler.reconcile(self.job['job_id'], expected_job_revision=self.job['revision'])
        self.clock[0] = 200
        result = self.scheduler.check_timeout(self.job['job_id'], expected_job_revision=self.job['revision'])
        self.assertEqual((result['state'], result['uncertainty_phase']), ('UNKNOWN', 'RUN'))
        self.assertEqual(result['business_result'], 'NOT_ASSESSED')

    def test_bad_observation_keeps_unknown_reservation(self):
        self.scheduler.observation_verifier = type('Bad', (), {'verify': lambda *a, **k: True})()
        with self.assertRaises(PermissionError): self.dispatch()
        current = self.scheduler.get(self.job['job_id'])
        self.assertEqual(current['state'], 'UNKNOWN')
        self.assertEqual(self.transport.dispatches, 1)

    def test_sequence_gap_and_changed_binding_are_rejected(self):
        self.dispatch()
        self.transport.sequence = 10
        original = self.path.read_bytes()
        with self.assertRaises(ValueError): self.observe()
        self.assertEqual(self.path.read_bytes(), original)
        self.transport.sequence = 1; self.transport.digest = 'b'*64
        with self.assertRaises(PermissionError): self.observe()
        self.assertEqual(self.path.read_bytes(), original)

    def test_exact_last_replay_does_not_refresh_heartbeat(self):
        self.dispatch(); self.observe()
        record = self.job['last_observation']
        prior = self.path.read_bytes()
        self.transport.observe = lambda **k: VerifiedJobObservation(**record)
        self.clock[0] += 1
        self.observe()
        self.assertEqual(self.path.read_bytes(), prior)

    def test_concurrent_dispatch_has_one_transport_winner(self):
        barrier = threading.Barrier(2)
        original = self.scheduler.authorization_verifier.verify
        def verify(**kw):
            result = original(**kw); barrier.wait(timeout=5); return result
        self.scheduler.authorization_verifier.verify = verify
        def send():
            try: return self.scheduler.dispatch(self.job['job_id'], proof='synthetic-only', expected_job_revision=1)
            except StateConflictError: return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: send(), range(2)))
        self.assertEqual(self.transport.dispatches, 1)
        self.assertEqual(results.count('conflict'), 1)

    def test_reservation_failure_prevents_transport_and_keeps_old_bytes(self):
        original = self.path.read_bytes()
        with patch('qa_master.state_store.os.replace', side_effect=OSError('synthetic-write-failure')):
            with self.assertRaises(OSError): self.dispatch()
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.transport.dispatches, 0)

    def test_corrupt_journal_is_not_replaced(self):
        self.path.write_text('{bad', encoding='utf-8')
        with self.assertRaises(ValueError): self.dispatch()
        self.assertEqual(self.path.read_text(), '{bad')
        self.assertEqual(self.transport.dispatches, 0)

    def test_nonce_cannot_be_reused_under_a_new_key(self):
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'NONCE_REUSE'):
            self.scheduler.prepare(manifest(job_key='job-2'), idempotency_key='job-2', expected_store_revision=1)
        self.assertEqual(self.path.read_bytes(), before)

    def test_expired_authorization_never_dispatches(self):
        def expired(**kw):
            return VerifiedOperationAuthorization('SYNTHETIC', 'expired', artifact_digest(kw['binding']), 0, 100)
        self.scheduler.authorization_verifier.verify = expired
        before = self.path.read_bytes()
        with self.assertRaises(PermissionError): self.dispatch()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.transport.dispatches, 0)

    def test_execution_deadline_and_equal_running_deadlines(self):
        self.dispatch()
        self.clock[0] = 200
        result = self.scheduler.check_timeout(self.job['job_id'], expected_job_revision=self.job['revision'])
        self.assertEqual(result['state'], 'CANCEL_DUE')
        self.assertIsNone(result['process'])

    def test_equal_deadlines_choose_heartbeat(self):
        self.dispatch()
        self.clock[0] = 190
        self.observe()
        self.clock[0] = 200
        result = self.scheduler.check_timeout(self.job['job_id'], expected_job_revision=self.job['revision'])
        self.assertEqual((result['state'], result['uncertainty_phase']), ('UNKNOWN', 'RUN'))

    def test_remote_clock_skew_is_audit_only(self):
        self.dispatch()
        observation = replace(self.transport.message('RUNNING'), observed_at=999999)
        self.transport.observe = lambda **kw: observation
        result = self.observe()
        self.assertEqual(result['last_received_at'], 100)
        self.assertEqual(result['last_observation']['observed_at'], 999999)

    def test_snapshot_supplies_cross_job_store_revision(self):
        self.dispatch()
        result = self.scheduler.prepare(manifest(job_key='job-2', nonce='m'*16),
            idempotency_key='job-2', expected_store_revision=self.job['store_revision'])
        self.assertEqual(result['job_revision'], 1)
        self.assertEqual(result['store_revision'], self.job['store_revision'] + 1)
        self.assertEqual(self.scheduler.get(self.job['job_id'])['store_revision'], result['store_revision'])

    def test_nested_unknown_fields_rejected_without_rewriting(self):
        self.dispatch(); self.observe()
        self.transport.next_kind = 'PROCESS_FINISHED'; self.observe()
        self.transport.next_kind = 'EVIDENCE_AVAILABLE'; self.observe()
        original = json.loads(self.path.read_text())
        from copy import deepcopy
        for field in ('events', 'authorization', 'last_observation', 'process', 'evidence'):
            with self.subTest(field=field):
                document = deepcopy(original)
                nested = document['jobs'][self.job['job_id']][field]
                if field == 'events': nested = nested[0]
                nested['token'] = 'private-corruption-marker'
                self.path.write_text(json.dumps(document))
                before = self.path.read_bytes()
                with self.assertRaisesRegex(ValueError, '^INVALID_JOURNAL$'):
                    self.scheduler.get(self.job['job_id'])
                self.assertEqual(before, self.path.read_bytes())

    def test_cursor_no_new_does_not_refresh_heartbeat(self):
        self.dispatch(); self.observe()
        calls = []
        def no_new(**kw):
            calls.append(kw)
            return NoNewObservation(**kw)
        self.transport.observe = no_new
        before = self.path.read_bytes()
        self.clock[0] += 5
        self.observe()
        self.assertEqual(calls[0]['after_sequence'], 1)
        self.assertEqual(before, self.path.read_bytes())

    def test_unknown_observation_kind_and_unreachable_unknown_rejected(self):
        original = json.loads(self.path.read_text())
        job = original['jobs'][self.job['job_id']]
        job.update(state='UNKNOWN', uncertainty_phase='RUN')
        job['events'][0]['state'] = 'UNKNOWN'
        self.path.write_text(json.dumps(original))
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, '^INVALID_JOURNAL$'):
            self.scheduler.get(self.job['job_id'])
        self.assertEqual(before, self.path.read_bytes())

    def test_unknown_kind_and_false_authoritative_absence_are_rejected(self):
        self.transport.fail_dispatch = True
        self.dispatch()
        self.transport.next_kind = 'ABSENT'
        self.job = self.scheduler.reconcile(self.job['job_id'], expected_job_revision=self.job['revision'])
        original = self.path.read_text()
        for change in ({'kind': 'INJECTED'}, {'authoritative_absence': False}):
            with self.subTest(change=change):
                document = json.loads(original)
                document['jobs'][self.job['job_id']]['last_observation'].update(change)
                self.path.write_text(json.dumps(document))
                before = self.path.read_bytes()
                with self.assertRaisesRegex(ValueError, '^INVALID_JOURNAL$'):
                    self.scheduler.get(self.job['job_id'])
                self.assertEqual(before, self.path.read_bytes())

    def test_cancel_uncertainty_cannot_be_relabelled_run(self):
        self.dispatch(); self.observe()
        self.job = self.scheduler.request_cancel(self.job['job_id'], reason='stop', proof='synthetic-only', expected_job_revision=self.job['revision'])
        self.clock[0] += 5
        self.job = self.scheduler.check_timeout(self.job['job_id'], expected_job_revision=self.job['revision'])
        document = json.loads(self.path.read_text())
        document['jobs'][self.job['job_id']]['uncertainty_phase'] = 'RUN'
        self.path.write_text(json.dumps(document))
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, '^INVALID_JOURNAL$'):
            self.scheduler.get(self.job['job_id'])
        self.assertEqual(before, self.path.read_bytes())

    def test_concurrent_cursor_reads_are_replayable_after_cas_loss(self):
        self.dispatch()
        record = self.transport.message('RUNNING')
        barrier = threading.Barrier(2)
        cursors = []
        def stable_read(**kw):
            cursors.append(kw['after_sequence'])
            barrier.wait(timeout=5)
            return record
        self.transport.observe = stable_read
        def poll():
            try: return self.scheduler.observe(self.job['job_id'], expected_job_revision=self.job['revision'])
            except StateConflictError: return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: poll(), range(2)))
        self.assertEqual(cursors, [0, 0])
        self.assertEqual(results.count('conflict'), 1)
        self.job = self.scheduler.get(self.job['job_id'])
        next_record = self.transport.message('RUNNING')
        self.transport.observe = lambda **kw: next_record if kw['after_sequence'] == 1 else record
        self.assertEqual(self.observe()['observation_sequence'], 2)

