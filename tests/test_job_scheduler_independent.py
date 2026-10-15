"""Independent fake-port acceptance tests for DES-026; they never run a worker."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from qa_master.approval import artifact_digest
from qa_master.job_scheduler import (
    EvidenceMetadata,
    JobManifest,
    JobRepository,
    JobScheduler,
    NoNewObservation,
    ProcessMetadata,
    VerifiedJobObservation,
    VerifiedOperationAuthorization,
)
from qa_master.state_store import StateConflictError


def make_manifest(**changes):
    value = {
        "schema_version": 1, "job_key": "independent-job", "nonce": "n" * 16,
        "campaign_id": "campaign", "step_id": "step", "project": "project",
        "workflow_revision": 7, "target_id": "target", "execution_timeout_seconds": 100,
        "heartbeat_timeout_seconds": 10, "cancel_grace_seconds": 5,
        "evidence_sink_id": "sink", "retention_policy_id": "retention",
    }
    for name in ("build", "case_set", "command", "config", "environment", "resource_policy", "evidence_contract"):
        value[name + "_sha256"] = "a" * 64
    value.update(changes)
    return JobManifest.create(value)


class Auth:
    def __init__(self, clock, valid=True): self.clock, self.valid, self.calls = clock, valid, 0
    def verify(self, *, action, binding, proof):
        self.calls += 1
        if not self.valid or proof != "proof": return False
        return VerifiedOperationAuthorization("SYNTHETIC", "auth", artifact_digest(binding), 0, self.clock[0] + 1000)


class Verifier:
    def __init__(self, valid=True): self.valid, self.calls = valid, 0
    def verify(self, *, binding, observation):
        self.calls += 1
        return observation if self.valid else True


class Transport:
    def __init__(self, clock, manifest_digest):
        self.clock, self.digest = clock, manifest_digest
        self.dispatch_calls = self.cancel_calls = 0
        self.operation_id = None
        self.responses, self.raise_dispatch = [], False
        self.observed_cursors, self.reconcile_calls = [], []

    def response(self, kind, sequence, **more):
        return VerifiedJobObservation("SYNTHETIC", "obs-" + str(sequence), self.operation_id,
            self.digest, "worker", sequence, self.clock[0], kind, **more)

    def dispatch(self, *, manifest, operation_id):
        self.dispatch_calls += 1; self.operation_id = operation_id
        if self.raise_dispatch: raise OSError("synthetic dispatch lost")
        return self.response("DISPATCHED", 0)

    def observe(self, *, operation_id, after_sequence):
        self.observed_cursors.append(after_sequence)
        return self._next(operation_id, after_sequence)

    def reconcile(self, *, operation_id, uncertainty_phase, after_sequence):
        self.reconcile_calls.append((operation_id, uncertainty_phase, after_sequence))
        return self._next(operation_id, after_sequence)

    def _next(self, operation_id, after_sequence):
        if self.responses: return self.responses.pop(0)
        return NoNewObservation(operation_id, after_sequence)

    def request_cancel(self, *, operation_id, cancel_operation_id):
        self.cancel_calls += 1
        return self.response("CANCEL_ACCEPTED", 2, cancel_operation_id=cancel_operation_id)


class SchedulerAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "journal.json"
        self.clock = [100.0]
        self.manifest = make_manifest()
        self.auth, self.verifier = Auth(self.clock), Verifier()
        self.transport = Transport(self.clock, self.manifest.digest)
        self.scheduler = JobScheduler(JobRepository(self.path), transport=self.transport,
            authorization_verifier=self.auth, observation_verifier=self.verifier, clock=lambda: self.clock[0])
        self.job = self.scheduler.prepare(self.manifest, idempotency_key=self.manifest.job_key, expected_store_revision=0)

    def dispatch(self):
        self.job = self.scheduler.dispatch(self.job["job_id"], proof="proof", expected_job_revision=self.job["job_revision"])
        return self.job

    def observe(self):
        self.job = self.scheduler.observe(self.job["job_id"], expected_job_revision=self.job["job_revision"])
        return self.job

    def test_tc_js_001_canonical_manifest_rejects_drift_and_sensitive_shape(self):
        self.assertEqual(self.manifest.digest, JobManifest.create(asdict(self.manifest)).digest)
        for mutation in ({"token": "secret"}, {"command_sha256": "A" * 64}, {"nonce": True}, {"target_id": "https://host"}):
            with self.subTest(mutation=mutation):
                with self.assertRaises(ValueError): make_manifest(**mutation)

    def test_tc_js_002_prepare_is_idempotent_and_store_revision_is_usable(self):
        self.assertEqual(self.job, self.scheduler.prepare(self.manifest, idempotency_key="independent-job", expected_store_revision=0))
        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_DRIFT"):
            self.scheduler.prepare(make_manifest(command_sha256="b" * 64), idempotency_key="independent-job", expected_store_revision=1)
        other = make_manifest(job_key="other-job", nonce="o" * 16)
        next_job = self.scheduler.prepare(other, idempotency_key="other-job", expected_store_revision=self.job["store_revision"])
        self.assertEqual(next_job["store_revision"], self.job["store_revision"] + 1)
        self.assertEqual(JobScheduler(JobRepository(self.path)).get(self.job["job_id"])["store_revision"], next_job["store_revision"])

    def test_tc_js_003_default_deny_precedes_transport_and_mutation(self):
        before = self.path.read_bytes()
        bare = JobScheduler(JobRepository(self.path))
        with self.assertRaisesRegex(PermissionError, "PORT_UNAVAILABLE"):
            bare.dispatch(self.job["job_id"], proof="proof", expected_job_revision=self.job["job_revision"])
        self.assertEqual(before, self.path.read_bytes()); self.assertEqual(self.transport.dispatch_calls, 0)
        self.auth.valid = False
        with self.assertRaisesRegex(PermissionError, "AUTHORIZATION_REJECTED"): self.dispatch()
        self.assertEqual(before, self.path.read_bytes()); self.assertEqual(self.transport.dispatch_calls, 0)

    def test_tc_js_004_lost_dispatch_response_is_durable_unknown_without_retry(self):
        self.transport.raise_dispatch = True
        self.assertEqual((self.dispatch()["state"], self.job["uncertainty_phase"]), ("UNKNOWN", "DISPATCH"))
        original_operation = self.job["operation_id"]
        restarted = JobScheduler(JobRepository(self.path), transport=self.transport, authorization_verifier=self.auth, observation_verifier=self.verifier, clock=lambda: self.clock[0])
        same = restarted.dispatch(self.job["job_id"], proof="proof", expected_job_revision=self.job["job_revision"])
        self.assertEqual((self.transport.dispatch_calls, same["operation_id"]), (1, original_operation))

    def test_tc_js_005_concurrent_dispatch_has_one_irreversible_call(self):
        gate = threading.Barrier(2); original = self.auth.verify
        def blocked(**kwargs):
            result = original(**kwargs); gate.wait(timeout=3); return result
        self.auth.verify = blocked
        def call():
            try: return self.scheduler.dispatch(self.job["job_id"], proof="proof", expected_job_revision=1)
            except StateConflictError: return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(lambda _: call(), range(2)))
        self.assertEqual(self.transport.dispatch_calls, 1); self.assertEqual(results.count("conflict"), 1)

    def test_tc_js_006_sequence_cursor_gap_stale_and_replay_fail_closed(self):
        self.dispatch()
        self.transport.responses = [self.transport.response("RUNNING", 1)]
        self.observe(); before = self.path.read_bytes()
        self.transport.responses = [NoNewObservation(self.job["operation_id"], 1)]
        self.observe(); self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(self.transport.observed_cursors, [0, 1])
        self.transport.responses = [self.transport.response("RUNNING", 3)]
        with self.assertRaisesRegex(ValueError, "OBSERVATION_GAP"): self.observe()
        self.assertEqual(before, self.path.read_bytes())
        self.transport.responses = [replace(self.transport.response("RUNNING", 0), observation_id="old")]
        with self.assertRaisesRegex(ValueError, "OBSERVATION_STALE"): self.observe()
        self.assertEqual(before, self.path.read_bytes())

    def test_tc_js_007_timeout_boundaries_do_not_fabricate_process_results(self):
        self.dispatch(); self.transport.responses = [self.transport.response("RUNNING", 1)]; self.observe()
        self.clock[0] = 110
        self.job = self.scheduler.check_timeout(self.job["job_id"], expected_job_revision=self.job["job_revision"])
        self.assertEqual((self.job["state"], self.job["uncertainty_phase"]), ("UNKNOWN", "RUN")); self.assertIsNone(self.job["process"])
        equal_manifest = make_manifest(job_key="equal", nonce="e" * 16, execution_timeout_seconds=10, heartbeat_timeout_seconds=10)
        equal = self.scheduler.prepare(equal_manifest, idempotency_key="equal", expected_store_revision=self.job["store_revision"])
        self.transport.digest = equal_manifest.digest
        equal = self.scheduler.dispatch(equal["job_id"], proof="proof", expected_job_revision=equal["job_revision"])
        self.clock[0] = 110
        self.transport.responses = [self.transport.response("RUNNING", 1)]
        equal = self.scheduler.observe(equal["job_id"], expected_job_revision=equal["job_revision"])
        self.clock[0] = 120
        equal = self.scheduler.check_timeout(equal["job_id"], expected_job_revision=equal["job_revision"])
        self.assertEqual((equal["state"], equal["uncertainty_phase"]), ("UNKNOWN", "RUN"))
        earlier_manifest = make_manifest(job_key="earlier", nonce="r" * 16, execution_timeout_seconds=10, heartbeat_timeout_seconds=10)
        earlier = self.scheduler.prepare(earlier_manifest, idempotency_key="earlier", expected_store_revision=equal["store_revision"])
        self.transport.digest = earlier_manifest.digest
        earlier = self.scheduler.dispatch(earlier["job_id"], proof="proof", expected_job_revision=earlier["job_revision"])
        self.clock[0] = 125
        self.transport.responses = [self.transport.response("RUNNING", 1)]
        earlier = self.scheduler.observe(earlier["job_id"], expected_job_revision=earlier["job_revision"])
        self.clock[0] = 130
        earlier = self.scheduler.check_timeout(earlier["job_id"], expected_job_revision=earlier["job_revision"])
        self.assertEqual(earlier["state"], "CANCEL_DUE")

    def test_tc_js_008_cancel_ack_is_not_termination_and_grace_becomes_unknown(self):
        self.dispatch(); self.transport.responses = [self.transport.response("RUNNING", 1)]; self.observe()
        self.job = self.scheduler.request_cancel(self.job["job_id"], reason="operator-stop", proof="proof", expected_job_revision=self.job["job_revision"])
        self.assertEqual(self.job["state"], "CANCEL_REQUESTED"); self.assertIsNone(self.job["process"])
        self.clock[0] += 5
        self.job = self.scheduler.check_timeout(self.job["job_id"], expected_job_revision=self.job["job_revision"])
        self.assertEqual((self.job["state"], self.job["uncertainty_phase"]), ("UNKNOWN", "CANCEL"))
        self.assertEqual(self.transport.cancel_calls, 1)

    def test_tc_js_009_process_finish_never_becomes_business_pass(self):
        self.dispatch(); self.transport.responses = [self.transport.response("RUNNING", 1)]; self.observe()
        self.transport.responses = [self.transport.response("PROCESS_FINISHED", 2, process=ProcessMetadata("EXITED", 0))]
        self.observe()
        self.assertEqual((self.job["state"], self.job["business_result"], self.job["process"]["exit_code"]), ("PROCESS_FINISHED", "NOT_ASSESSED", 0))

    def test_tc_js_010_evidence_stops_at_available(self):
        self.test_tc_js_009_process_finish_never_becomes_business_pass()
        self.transport.responses = [self.transport.response("EVIDENCE_AVAILABLE", 3, evidence=EvidenceMetadata("artifact", "b" * 64, 3, "a" * 64))]
        self.observe()
        self.assertEqual((self.job["state"], self.job["business_result"]), ("EVIDENCE_AVAILABLE", "NOT_ASSESSED"))

    def test_tc_js_011_reconcile_authoritative_absence_only_for_unknown_dispatch(self):
        self.transport.raise_dispatch = True; self.dispatch(); self.transport.raise_dispatch = False
        self.transport.responses = [self.transport.response("ABSENT", 0, authoritative_absence=True)]
        self.job = self.scheduler.reconcile(self.job["job_id"], expected_job_revision=self.job["job_revision"])
        self.assertEqual((self.job["state"], self.transport.dispatch_calls), ("NOT_DISPATCHED", 1))
        self.assertEqual(self.transport.reconcile_calls[0][1:], ("DISPATCH", -1))

    def test_tc_js_012_corrupt_or_failed_persistence_never_calls_transport(self):
        before = self.path.read_bytes()
        with patch("qa_master.state_store.os.replace", side_effect=OSError("synthetic")):
            with self.assertRaises(OSError): self.dispatch()
        self.assertEqual((before, self.transport.dispatch_calls), (self.path.read_bytes(), 0))
        self.path.write_text("{bad", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "INVALID_JOURNAL"): self.scheduler.get(self.job["job_id"])
        self.assertEqual(self.path.read_text(encoding="utf-8"), "{bad")

    def test_tc_js_013_journal_redacts_proof_reason_and_transport_exception(self):
        self.dispatch(); self.transport.responses = [self.transport.response("RUNNING", 1)]; self.observe()
        self.transport.request_cancel = lambda **kw: {"raw": "raw-cancel-response-marker"}
        self.scheduler.observation_verifier = Verifier(valid=False)
        with self.assertRaisesRegex(PermissionError, "OBSERVATION_REJECTED"):
            self.scheduler.request_cancel(self.job["job_id"], reason="private-cancel-reason-marker", proof="proof", expected_job_revision=self.job["job_revision"])
        journal = self.path.read_bytes()
        for forbidden in (b"proof", b"private-cancel-reason-marker", b"raw-cancel-response-marker"):
            self.assertNotIn(forbidden, journal)

    def test_tc_js_003_each_required_port_and_expiry_deny_before_mutation(self):
        before = self.path.read_bytes()
        for kwargs in ({"transport": self.transport, "authorization_verifier": self.auth},
                       {"transport": self.transport, "observation_verifier": self.verifier},
                       {"authorization_verifier": self.auth, "observation_verifier": self.verifier}):
            with self.subTest(kwargs=sorted(kwargs)):
                scheduler = JobScheduler(JobRepository(self.path), clock=lambda: self.clock[0], **kwargs)
                with self.assertRaisesRegex(PermissionError, "PORT_UNAVAILABLE"):
                    scheduler.dispatch(self.job["job_id"], proof="proof", expected_job_revision=1)
                self.assertEqual(before, self.path.read_bytes())
        class Expired:
            def verify(_, **kw): return VerifiedOperationAuthorization("SYNTHETIC", "expired", artifact_digest(kw["binding"]), 0, 100)
        self.scheduler.authorization_verifier = Expired()
        with self.assertRaisesRegex(PermissionError, "AUTHORIZATION_REJECTED"): self.dispatch()
        self.assertEqual(before, self.path.read_bytes()); self.assertEqual(self.transport.dispatch_calls, 0)

    def test_tc_js_004_unverified_raw_response_keeps_unknown_and_redacts_payload(self):
        self.scheduler.observation_verifier = Verifier(valid=False)
        with self.assertRaisesRegex(PermissionError, "OBSERVATION_REJECTED"): self.dispatch()
        current = self.scheduler.get(self.job["job_id"])
        self.assertEqual((current["state"], current["uncertainty_phase"], self.transport.dispatch_calls), ("UNKNOWN", "DISPATCH", 1))
        self.assertNotIn(b"proof", self.path.read_bytes())
        again = self.scheduler.dispatch(current["job_id"], proof="proof", expected_job_revision=current["job_revision"])
        self.assertEqual((again["state"], self.transport.dispatch_calls), ("UNKNOWN", 1))

    def test_tc_js_004_post_io_cas_conflict_preserves_dispatch_unknown(self):
        original, calls = self.scheduler.repository.save, [0]
        def save(document, digest):
            calls[0] += 1
            if calls[0] == 2: raise StateConflictError("synthetic post-io conflict")
            return original(document, digest)
        with patch.object(self.scheduler.repository, "save", side_effect=save):
            with self.assertRaises(StateConflictError): self.dispatch()
        current = self.scheduler.get(self.job["job_id"])
        self.assertEqual((self.transport.dispatch_calls, current["state"], current["uncertainty_phase"]), (1, "UNKNOWN", "DISPATCH"))

    def test_tc_js_006_binding_drift_and_exact_replay_do_not_mutate(self):
        self.dispatch(); before = self.path.read_bytes()
        self.transport.responses = [replace(self.transport.response("RUNNING", 1), manifest_sha256="b" * 64)]
        with self.assertRaisesRegex(PermissionError, "OBSERVATION_REJECTED"): self.observe()
        self.assertEqual(before, self.path.read_bytes())
        self.transport.responses = [self.transport.response("RUNNING", 1)]; self.observe()
        before = self.path.read_bytes(); replay = VerifiedJobObservation(**self.job["last_observation"])
        self.transport.responses = [replay]; self.observe(); self.assertEqual(before, self.path.read_bytes())
        self.transport.responses = [replace(replay, observation_id="same-seq-drift")]
        with self.assertRaisesRegex(ValueError, "OBSERVATION_DRIFT"): self.observe()
        self.assertEqual(before, self.path.read_bytes())

    def test_tc_js_008_bad_cancel_ack_keeps_unknown_but_terminal_can_win_race(self):
        self.dispatch(); self.transport.responses = [self.transport.response("RUNNING", 1)]; self.observe()
        self.transport.request_cancel = lambda **kw: self.transport.response("CANCEL_ACCEPTED", 2, cancel_operation_id="wrong")
        with self.assertRaisesRegex(PermissionError, "OBSERVATION_REJECTED"):
            self.scheduler.request_cancel(self.job["job_id"], reason="stop", proof="proof", expected_job_revision=self.job["job_revision"])
        self.job = self.scheduler.get(self.job["job_id"])
        self.assertEqual((self.job["state"], self.job["uncertainty_phase"]), ("UNKNOWN", "CANCEL"))
        self.transport.responses = [self.transport.response("PROCESS_FINISHED", 2, process=ProcessMetadata("CANCELLED", None))]
        self.job = self.scheduler.reconcile(self.job["job_id"], expected_job_revision=self.job["job_revision"])
        self.assertEqual((self.job["state"], self.job["process"]["termination"]), ("PROCESS_FINISHED", "CANCELLED"))

    def test_tc_js_011_unknown_cancel_absence_stays_unknown(self):
        self.dispatch(); self.transport.responses = [self.transport.response("RUNNING", 1)]; self.observe()
        self.transport.request_cancel = lambda **kw: self.transport.response("ABSENT", 2, authoritative_absence=True)
        with self.assertRaisesRegex(ValueError, "INVALID_OBSERVATION_TRANSITION"):
            self.scheduler.request_cancel(self.job["job_id"], reason="stop", proof="proof", expected_job_revision=self.job["job_revision"])
        self.job = self.scheduler.get(self.job["job_id"])
        self.transport.responses = [self.transport.response("ABSENT", 2, authoritative_absence=True)]
        with self.assertRaisesRegex(ValueError, "INVALID_OBSERVATION_TRANSITION"):
            self.scheduler.reconcile(self.job["job_id"], expected_job_revision=self.job["job_revision"])
        self.assertEqual((self.scheduler.get(self.job["job_id"])["state"], self.transport.dispatch_calls), ("UNKNOWN", 1))

    def test_tc_js_012_nested_journal_corruption_is_read_only(self):
        document = json.loads(self.path.read_text(encoding="utf-8"))
        document["keys"]["corrupt-index"] = "missing"
        self.path.write_text(json.dumps(document), encoding="utf-8")
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "INVALID_JOURNAL"): self.scheduler.get(self.job["job_id"])
        self.assertEqual(before, self.path.read_bytes())

    def test_tc_js_012_distinct_prepare_race_has_one_winner_and_valid_journal(self):
        barrier, original = threading.Barrier(2), self.scheduler.repository.save
        def synchronized_save(document, digest):
            barrier.wait(timeout=3)
            return original(document, digest)
        def prepare(number):
            manifest = make_manifest(job_key="race-" + str(number), nonce=str(number) * 16)
            try:
                return self.scheduler.prepare(manifest, idempotency_key=manifest.job_key, expected_store_revision=self.job["store_revision"])
            except StateConflictError:
                return "conflict"
        with patch.object(self.scheduler.repository, "save", side_effect=synchronized_save):
            with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(prepare, (1, 2)))
        self.assertEqual(results.count("conflict"), 1)
        document, _ = self.scheduler.repository.load()
        self.assertEqual((len(document["jobs"]), len(document["keys"])), (2, 2))

