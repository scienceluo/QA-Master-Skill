"""Reconciliation-first local job core (DES-026).

No transport, authorization provider, worker, or evidence verifier is bundled.
Injected ports are trusted host dependencies, not identities established here.
The local journal must be protected by the host; it is not a signed audit store.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import time
from uuid import uuid4

from .approval import artifact_digest
from .state_store import StateConflictError, save_document

_ID = re.compile(r'^[A-Za-z0-9_.:-]{1,200}$')
_SHA = re.compile(r'^[0-9a-f]{64}$')
STATES = {'PREPARED', 'UNKNOWN', 'DISPATCHED', 'RUNNING', 'CANCEL_DUE',
          'CANCEL_REQUESTED', 'PROCESS_FINISHED', 'EVIDENCE_AVAILABLE', 'NOT_DISPATCHED'}
JOB_FIELDS = {'job_id', 'manifest', 'manifest_sha256', 'revision', 'state', 'operation_id',
              'cancel_operation_id', 'authorization', 'cancel_authorization', 'uncertainty_phase',
              'last_confirmed_state', 'observation_sequence', 'last_observation', 'worker_job_id',
              'prepared_at', 'updated_at', 'dispatched_at', 'last_received_at',
              'cancel_requested_at', 'process', 'evidence', 'business_result', 'events'}


def _identifier(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError('INVALID_IDENTIFIER')


def _integer(value, low=0, high=2**63-1):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('INVALID_INTEGER')


def _timestamp(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError('INVALID_TIME')


def _sha(value):
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ValueError('INVALID_DIGEST')


def _bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def _snapshot(job, store_revision):
    return dict(deepcopy(job), job_revision=job['revision'], store_revision=store_revision)


def _process_metadata(value):
    if type(value) is not ProcessMetadata:
        raise ValueError('INVALID_PROCESS_METADATA')
    if value.termination not in ('EXITED', 'CANCELLED', 'TIMED_OUT', 'FAILED'):
        raise ValueError('INVALID_TERMINATION')
    if value.exit_code is not None:
        _integer(value.exit_code, -(2**31), 2**31-1)
    elif value.termination == 'EXITED':
        raise ValueError('EXIT_CODE_REQUIRED')


def _evidence_metadata(value, contract):
    if type(value) is not EvidenceMetadata:
        raise ValueError('INVALID_EVIDENCE_METADATA')
    _identifier(value.evidence_id); _sha(value.sha256); _integer(value.byte_count)
    if value.contract_sha256 != contract:
        raise ValueError('EVIDENCE_CONTRACT_MISMATCH')


@dataclass(frozen=True)
class JobManifest:
    schema_version: int
    job_key: str
    nonce: str
    campaign_id: str
    step_id: str
    project: str
    workflow_revision: int
    build_sha256: str
    case_set_sha256: str
    command_sha256: str
    config_sha256: str
    environment_sha256: str
    resource_policy_sha256: str
    target_id: str
    execution_timeout_seconds: int
    heartbeat_timeout_seconds: int
    cancel_grace_seconds: int
    evidence_sink_id: str
    evidence_contract_sha256: str
    retention_policy_id: str

    def __post_init__(self):
        _integer(self.schema_version, 1, 1)
        _integer(self.workflow_revision)
        for key, value in asdict(self).items():
            if key.endswith('_sha256'):
                _sha(value)
        for key in ('job_key', 'nonce', 'campaign_id', 'step_id', 'project', 'target_id',
                    'evidence_sink_id', 'retention_policy_id'):
            _identifier(getattr(self, key))
        if not 16 <= len(self.nonce) <= 128:
            raise ValueError('INVALID_NONCE')
        _integer(self.execution_timeout_seconds, 1, 86400)
        _integer(self.heartbeat_timeout_seconds, 1, min(3600, self.execution_timeout_seconds))
        _integer(self.cancel_grace_seconds, 1, 600)
        if len(self.canonical_bytes) > 65536:
            raise ValueError('MANIFEST_TOO_LARGE')

    @classmethod
    def create(cls, document):
        if not isinstance(document, dict):
            raise ValueError('INVALID_MANIFEST')
        try:
            return cls(**document)
        except TypeError as error:
            raise ValueError('INVALID_MANIFEST') from error

    @property
    def canonical_bytes(self):
        return _bytes(asdict(self))

    @property
    def digest(self):
        return hashlib.sha256(self.canonical_bytes).hexdigest()


@dataclass(frozen=True)
class VerifiedOperationAuthorization:
    provider: str
    authorization_id: str
    binding_sha256: str
    issued_at: float
    expires_at: float


@dataclass(frozen=True)
class ProcessMetadata:
    termination: str
    exit_code: int | None = None


@dataclass(frozen=True)
class EvidenceMetadata:
    evidence_id: str
    sha256: str
    byte_count: int
    contract_sha256: str


@dataclass(frozen=True)
class NoNewObservation:
    """Transport has no next record; never refreshes liveness or proves absence."""
    operation_id: str
    after_sequence: int


@dataclass(frozen=True)
class VerifiedJobObservation:
    provider: str
    observation_id: str
    operation_id: str
    manifest_sha256: str
    worker_job_id: str
    sequence: int
    observed_at: float
    kind: str
    cancel_operation_id: str | None = None
    process: ProcessMetadata | None = None
    evidence: EvidenceMetadata | None = None
    authoritative_absence: bool = False


class JobRepository:
    """Bounded single-host journal, with revision-and-byte-digest CAS."""
    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        try:
            original = self.path.read_bytes()
        except FileNotFoundError:
            return {'schema_version': 1, 'revision': 0, 'keys': {}, 'jobs': {}}, None
        if len(original) > 50_000_000:
            raise ValueError('JOURNAL_TOO_LARGE')
        try:
            document = json.loads(original.decode('utf-8'))
            self.validate(document)
        except (ValueError, TypeError, KeyError, UnicodeError) as error:
            raise ValueError('INVALID_JOURNAL') from error
        return document, hashlib.sha256(original).hexdigest()

    def validate(self, document):
        if not isinstance(document, dict) or set(document) != {'schema_version', 'revision', 'keys', 'jobs'}:
            raise ValueError('INVALID_JOURNAL')
        _integer(document['schema_version'], 1, 1)
        _integer(document['revision'])
        if not isinstance(document['keys'], dict) or not isinstance(document['jobs'], dict) or len(document['jobs']) > 1000:
            raise ValueError('INVALID_JOURNAL')
        if len(document['keys']) != len(document['jobs']):
            raise ValueError('INVALID_INDEX')
        nonces = set()
        for job_id, job in document['jobs'].items():
            _identifier(job_id)
            if not isinstance(job, dict) or set(job) != JOB_FIELDS:
                raise ValueError('INVALID_JOB')
            manifest = JobManifest.create(job['manifest'])
            if manifest.nonce in nonces:
                raise ValueError('NONCE_REUSE')
            nonces.add(manifest.nonce)
            if job['job_id'] != job_id or job['manifest_sha256'] != manifest.digest or job['state'] not in STATES:
                raise ValueError('INVALID_JOB')
            key = hashlib.sha256(manifest.job_key.encode()).hexdigest()
            if document['keys'].get(key) != job_id or job['business_result'] != 'NOT_ASSESSED':
                raise ValueError('INVALID_JOB')
            _integer(job['revision'], 1)
            _integer(job['observation_sequence'], -1)
            if not isinstance(job['events'], list) or len(job['events']) > 10000:
                raise ValueError('INVALID_EVENTS')
            for field in ('prepared_at', 'updated_at'):
                _timestamp(job[field])
            for field in ('dispatched_at', 'last_received_at', 'cancel_requested_at'):
                if job[field] is not None:
                    _timestamp(job[field])
            if job['last_confirmed_state'] not in STATES or job['last_confirmed_state'] == 'UNKNOWN':
                raise ValueError('INVALID_CONFIRMED_STATE')
            if job['state'] == 'UNKNOWN' and job['uncertainty_phase'] not in ('DISPATCH', 'RUN', 'CANCEL'):
                raise ValueError('INVALID_UNCERTAINTY')
            if job['state'] != 'UNKNOWN' and job['uncertainty_phase'] is not None:
                raise ValueError('INVALID_UNCERTAINTY')
            if job['state'] != 'PREPARED':
                _identifier(job['operation_id'])
                _timestamp(job['dispatched_at'])
                if not isinstance(job['authorization'], dict):
                    raise ValueError('INVALID_AUTHORIZATION_METADATA')
            elif job['operation_id'] is not None or job['authorization'] is not None or job['observation_sequence'] != -1:
                raise ValueError('INVALID_PREPARED_STATE')
            if job['cancel_operation_id'] is not None:
                _identifier(job['cancel_operation_id'])
                _timestamp(job['cancel_requested_at'])
            if job['state'] in ('PROCESS_FINISHED', 'EVIDENCE_AVAILABLE') and not isinstance(job['process'], dict):
                raise ValueError('MISSING_PROCESS_METADATA')
            if job['state'] == 'EVIDENCE_AVAILABLE' and not isinstance(job['evidence'], dict):
                raise ValueError('MISSING_EVIDENCE_METADATA')
            if job['observation_sequence'] >= 0 and not isinstance(job['last_observation'], dict):
                raise ValueError('MISSING_OBSERVATION_METADATA')
            self._validate_nested(job)
        _bytes(document)

    @staticmethod
    def _validate_nested(job):
        if job['revision'] != len(job['events']) or not job['events']:
            raise ValueError('INVALID_EVENT_REVISION')
        event_names = {'PREPARED', 'AUTHORIZED_DISPATCH_RESERVED', 'AUTHORIZED_CANCEL_RESERVED',
                       'VERIFIED_DISPATCHED', 'VERIFIED_RUNNING', 'VERIFIED_CANCEL_ACCEPTED',
                       'VERIFIED_PROCESS_FINISHED', 'VERIFIED_EVIDENCE_AVAILABLE', 'VERIFIED_ABSENT',
                       'EXECUTION_DEADLINE_REACHED', 'HEARTBEAT_EXPIRED', 'CANCEL_GRACE_EXPIRED'}
        for index, event in enumerate(job['events'], 1):
            keys = {'sequence', 'event', 'state', 'at'} | ({'operation_id'} if index > 1 else set())
            if not isinstance(event, dict) or set(event) != keys or type(event['sequence']) is not int or event['sequence'] != index:
                raise ValueError('INVALID_EVENT')
            if event['event'] not in event_names or event['state'] not in STATES:
                raise ValueError('INVALID_EVENT')
            _timestamp(event['at'])
            if index > 1 and event['operation_id'] != job['operation_id']:
                raise ValueError('INVALID_EVENT_OPERATION')
        if job['events'][-1]['state'] != job['state'] or job['events'][-1]['at'] != job['updated_at']:
            raise ValueError('INVALID_EVENT_STATE')
        if job['state'] == 'UNKNOWN':
            allowed_events = {'DISPATCH': {'AUTHORIZED_DISPATCH_RESERVED'},
                              'RUN': {'HEARTBEAT_EXPIRED'},
                              'CANCEL': {'AUTHORIZED_CANCEL_RESERVED', 'CANCEL_GRACE_EXPIRED'}}
            if job['events'][-1]['event'] not in allowed_events[job['uncertainty_phase']]:
                raise ValueError('INVALID_UNCERTAINTY_EVENT')
            if job['uncertainty_phase'] == 'RUN' and job['last_confirmed_state'] != 'RUNNING':
                raise ValueError('INVALID_RUN_UNCERTAINTY')
            if job['uncertainty_phase'] == 'CANCEL' and job['last_confirmed_state'] not in ('DISPATCHED', 'RUNNING', 'CANCEL_REQUESTED'):
                raise ValueError('INVALID_CANCEL_UNCERTAINTY')
        if job['state'] == 'CANCEL_DUE' and job['last_confirmed_state'] not in ('DISPATCHED', 'RUNNING'):
            raise ValueError('INVALID_CANCEL_DUE')
        for field, action, operation_id in (('authorization', 'dispatch', job['operation_id']),
                                            ('cancel_authorization', 'cancel', job['cancel_operation_id'])):
            value = job[field]
            if value is None:
                if operation_id is not None:
                    raise ValueError('MISSING_AUTHORIZATION')
                continue
            keys = {'provider', 'authorization_id', 'binding_sha256', 'issued_at', 'expires_at', 'binding'}
            if not isinstance(value, dict) or set(value) != keys:
                raise ValueError('INVALID_AUTHORIZATION')
            _identifier(value['provider']); _identifier(value['authorization_id'])
            _timestamp(value['issued_at']); _timestamp(value['expires_at'])
            if value['issued_at'] >= value['expires_at']:
                raise ValueError('INVALID_AUTHORIZATION_TIME')
            binding = value['binding']
            if not isinstance(binding, dict) or set(binding) != {'action', 'job_id', 'manifest_sha256', 'operation_id', 'job_revision', 'reason_sha256'}:
                raise ValueError('INVALID_AUTHORIZATION_BINDING')
            if (binding['action'], binding['job_id'], binding['manifest_sha256'], binding['operation_id']) != (action, job['job_id'], job['manifest_sha256'], operation_id):
                raise ValueError('INVALID_AUTHORIZATION_BINDING')
            _integer(binding['job_revision'], 1, job['revision'] - 1)
            if action == 'cancel': _sha(binding['reason_sha256'])
            elif binding['reason_sha256'] is not None: raise ValueError('INVALID_DISPATCH_REASON')
            if value['binding_sha256'] != artifact_digest(binding):
                raise ValueError('INVALID_AUTHORIZATION_DIGEST')
        if job['cancel_operation_id'] is None and (job['cancel_requested_at'] is not None or job['cancel_authorization'] is not None):
            raise ValueError('INVALID_CANCEL_METADATA')
        if (job['state'] == 'CANCEL_REQUESTED' or job['uncertainty_phase'] == 'CANCEL') and job['cancel_operation_id'] is None:
            raise ValueError('MISSING_CANCEL_METADATA')
        if job['process'] is not None:
            if not isinstance(job['process'], dict) or set(job['process']) != {'termination', 'exit_code'}:
                raise ValueError('INVALID_PROCESS_METADATA')
            _process_metadata(ProcessMetadata(**job['process']))
        if job['evidence'] is not None:
            if not isinstance(job['evidence'], dict) or set(job['evidence']) != {'evidence_id', 'sha256', 'byte_count', 'contract_sha256'}:
                raise ValueError('INVALID_EVIDENCE_METADATA')
            _evidence_metadata(EvidenceMetadata(**job['evidence']), job['manifest']['evidence_contract_sha256'])
        if job['state'] not in ('PROCESS_FINISHED', 'EVIDENCE_AVAILABLE') and job['process'] is not None:
            raise ValueError('UNEXPECTED_PROCESS_METADATA')
        if job['state'] != 'EVIDENCE_AVAILABLE' and job['evidence'] is not None:
            raise ValueError('UNEXPECTED_EVIDENCE_METADATA')
        if job['observation_sequence'] == -1:
            if any(job[key] is not None for key in ('last_observation', 'last_received_at', 'worker_job_id')):
                raise ValueError('INVALID_OBSERVATION_METADATA')
            if job['state'] not in ('PREPARED', 'UNKNOWN'):
                raise ValueError('MISSING_OBSERVATION')
            if job['last_confirmed_state'] != 'PREPARED' or (job['state'] == 'UNKNOWN' and job['uncertainty_phase'] != 'DISPATCH'):
                raise ValueError('INVALID_UNOBSERVED_STATE')
        else:
            metadata = deepcopy(job['last_observation'])
            # Exact key checking: dataclass defaults must not hide missing fields.
            if set(metadata) != set(VerifiedJobObservation.__dataclass_fields__):
                raise ValueError('INVALID_OBSERVATION_METADATA')
            for field, cls in (('process', ProcessMetadata), ('evidence', EvidenceMetadata)):
                if metadata[field] is not None:
                    if not isinstance(metadata[field], dict) or set(metadata[field]) != set(cls.__dataclass_fields__):
                        raise ValueError('INVALID_OBSERVATION_METADATA')
                    metadata[field] = cls(**metadata[field])
            observation = VerifiedJobObservation(**metadata)
            JobScheduler._validate_observation(observation, job)
            if observation.sequence != job['observation_sequence']:
                raise ValueError('INVALID_OBSERVATION_SEQUENCE')
            confirmed = {'DISPATCHED': 'DISPATCHED', 'RUNNING': 'RUNNING',
                         'CANCEL_ACCEPTED': 'CANCEL_REQUESTED', 'PROCESS_FINISHED': 'PROCESS_FINISHED',
                         'EVIDENCE_AVAILABLE': 'EVIDENCE_AVAILABLE', 'ABSENT': 'NOT_DISPATCHED'}[observation.kind]
            if job['last_confirmed_state'] != confirmed:
                raise ValueError('INVALID_CONFIRMED_OBSERVATION')
            if job['state'] not in ('UNKNOWN', 'CANCEL_DUE') and job['state'] != confirmed:
                raise ValueError('INVALID_OBSERVATION_STATE')
            if job['state'] == 'UNKNOWN' and job['uncertainty_phase'] == 'DISPATCH':
                raise ValueError('INVALID_OBSERVED_DISPATCH')
            if observation.kind == 'ABSENT' and job['state'] != 'NOT_DISPATCHED':
                raise ValueError('INVALID_ABSENCE_STATE')
            _timestamp(job['last_received_at'])

    def save(self, document, source_digest):
        self.validate(document)
        if len(_bytes(document)) > 50_000_000:
            raise ValueError('JOURNAL_TOO_LARGE')
        return save_document(self.path, document, expected_revision=document['revision'],
                             expected_sha256=source_digest, create_if_absent=source_digest is None)


class JobScheduler:
    def __init__(self, repository, *, transport=None, authorization_verifier=None,
                 observation_verifier=None, clock=time.time):
        self.repository = repository
        self.transport = transport
        self.authorization_verifier = authorization_verifier
        self.observation_verifier = observation_verifier
        self.clock = clock

    def _now(self):
        try:
            now = self.clock()
            _timestamp(now)
            return now
        except Exception:
            raise ValueError('CLOCK_UNAVAILABLE') from None

    def _ports(self, authorize=False):
        required = [(self.transport, 'observe'), (self.observation_verifier, 'verify')]
        if authorize:
            required.append((self.authorization_verifier, 'verify'))
        if any(not callable(getattr(port, method, None)) for port, method in required):
            raise PermissionError('PORT_UNAVAILABLE')

    def _load_job(self, job_id, expected_revision=None):
        document, digest = self.repository.load()
        job = document['jobs'].get(job_id)
        if job is None:
            raise ValueError('UNKNOWN_JOB')
        if expected_revision is not None:
            _integer(expected_revision, 1)
            if job['revision'] != expected_revision:
                raise StateConflictError('JOB_REVISION_CONFLICT')
        return document, digest, job

    def _save_job(self, document, digest, job, event):
        now = self._now()
        if now < job['updated_at']:
            raise ValueError('CLOCK_REGRESSION')
        job['revision'] += 1
        job['updated_at'] = now
        job['events'].append({'sequence': len(job['events']) + 1, 'event': event,
                              'state': job['state'], 'at': now,
                              'operation_id': job['operation_id']})
        persisted = self.repository.save(document, digest)
        return _snapshot(job, persisted['revision'])

    def get(self, job_id):
        document, _, job = self._load_job(job_id)
        return _snapshot(job, document['revision'])

    def prepare(self, manifest, *, idempotency_key, expected_store_revision):
        if type(manifest) is not JobManifest:
            raise ValueError('INVALID_MANIFEST')
        _integer(expected_store_revision)
        if idempotency_key != manifest.job_key:
            raise ValueError('IDEMPOTENCY_KEY_MISMATCH')
        document, digest = self.repository.load()
        index = hashlib.sha256(idempotency_key.encode()).hexdigest()
        if index in document['keys']:
            job = document['jobs'][document['keys'][index]]
            if job['manifest_sha256'] != manifest.digest:
                raise ValueError('IDEMPOTENCY_DRIFT')
            return _snapshot(job, document['revision'])
        if document['revision'] != expected_store_revision:
            raise StateConflictError('STORE_REVISION_CONFLICT')
        if any(existing['manifest']['nonce'] == manifest.nonce for existing in document['jobs'].values()):
            raise ValueError('NONCE_REUSE')
        now = self._now()
        job_id = uuid4().hex
        job = {'job_id': job_id, 'manifest': asdict(manifest), 'manifest_sha256': manifest.digest,
               'revision': 1, 'state': 'PREPARED', 'operation_id': None,
               'cancel_operation_id': None, 'authorization': None, 'cancel_authorization': None,
               'uncertainty_phase': None, 'last_confirmed_state': 'PREPARED',
               'observation_sequence': -1, 'last_observation': None, 'worker_job_id': None,
               'prepared_at': now, 'updated_at': now, 'dispatched_at': None,
               'last_received_at': None, 'cancel_requested_at': None,
               'process': None, 'evidence': None, 'business_result': 'NOT_ASSESSED',
               'events': [{'sequence': 1, 'event': 'PREPARED', 'state': 'PREPARED', 'at': now}]}
        document['jobs'][job_id] = job
        document['keys'][index] = job_id
        persisted = self.repository.save(document, digest)
        return _snapshot(job, persisted['revision'])

    def _authorize(self, job, action, operation_id, proof, reason=None):
        binding = {'action': action, 'job_id': job['job_id'], 'manifest_sha256': job['manifest_sha256'],
                   'operation_id': operation_id, 'job_revision': job['revision'],
                   'reason_sha256': artifact_digest(reason) if reason is not None else None}
        try:
            claim = self.authorization_verifier.verify(action=action, binding=deepcopy(binding), proof=proof)
            if type(claim) is not VerifiedOperationAuthorization:
                raise ValueError
            _identifier(claim.provider); _identifier(claim.authorization_id)
            _timestamp(claim.issued_at); _timestamp(claim.expires_at)
            now = self._now()
            if claim.binding_sha256 != artifact_digest(binding) or not claim.issued_at <= now < claim.expires_at:
                raise ValueError
        except Exception:
            raise PermissionError('AUTHORIZATION_REJECTED') from None
        return dict(asdict(claim), binding=binding)

    def dispatch(self, job_id, *, proof, expected_job_revision):
        self._ports(authorize=True)
        if not callable(getattr(self.transport, 'dispatch', None)):
            raise PermissionError('PORT_UNAVAILABLE')
        document, digest, job = self._load_job(job_id, expected_job_revision)
        if job['state'] != 'PREPARED':
            return _snapshot(job, document['revision'])  # UNKNOWN can never be resubmitted.
        operation_id = uuid4().hex
        authorization = self._authorize(job, 'dispatch', operation_id, proof)
        job.update(state='UNKNOWN', uncertainty_phase='DISPATCH', operation_id=operation_id,
                   authorization=authorization, dispatched_at=self._now())
        reserved = self._save_job(document, digest, job, 'AUTHORIZED_DISPATCH_RESERVED')
        if not authorization['issued_at'] <= self._now() < authorization['expires_at']:
            raise PermissionError('AUTHORIZATION_EXPIRED')
        try:
            response = self.transport.dispatch(manifest=JobManifest.create(job['manifest']).canonical_bytes,
                                               operation_id=operation_id)
        except Exception:
            return reserved  # Error payloads/proofs are never persisted or echoed.
        return self._accept(job_id, response, expected_job_revision=reserved['revision'], context='dispatch')

    def request_cancel(self, job_id, *, reason, proof, expected_job_revision):
        self._ports(authorize=True)
        if not callable(getattr(self.transport, 'request_cancel', None)):
            raise PermissionError('PORT_UNAVAILABLE')
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
            raise ValueError('CANCEL_REASON_REQUIRED')
        document, digest, job = self._load_job(job_id, expected_job_revision)
        allowed = job['state'] in ('DISPATCHED', 'RUNNING', 'CANCEL_DUE') or (job['state'] == 'UNKNOWN' and job['uncertainty_phase'] == 'RUN')
        if not allowed or job['cancel_operation_id'] is not None:
            return _snapshot(job, document['revision'])
        cancel_id = uuid4().hex
        authorization = self._authorize(job, 'cancel', cancel_id, proof, reason)
        job.update(state='UNKNOWN', uncertainty_phase='CANCEL', cancel_operation_id=cancel_id,
                   cancel_authorization=authorization, cancel_requested_at=self._now())
        reserved = self._save_job(document, digest, job, 'AUTHORIZED_CANCEL_RESERVED')
        if not authorization['issued_at'] <= self._now() < authorization['expires_at']:
            raise PermissionError('AUTHORIZATION_EXPIRED')
        try:
            response = self.transport.request_cancel(operation_id=job['operation_id'], cancel_operation_id=cancel_id)
        except Exception:
            return reserved
        return self._accept(job_id, response, expected_job_revision=reserved['revision'], context='cancel')

    def observe(self, job_id, *, expected_job_revision):
        return self._poll(job_id, expected_job_revision, reconcile=False)

    def reconcile(self, job_id, *, expected_job_revision):
        return self._poll(job_id, expected_job_revision, reconcile=True)

    def _poll(self, job_id, expected_job_revision, reconcile):
        self._ports()
        method = 'reconcile' if reconcile else 'observe'
        if not callable(getattr(self.transport, method, None)):
            raise PermissionError('PORT_UNAVAILABLE')
        document, _, job = self._load_job(job_id, expected_job_revision)
        if reconcile != (job['state'] == 'UNKNOWN') or job['state'] == 'PREPARED':
            raise ValueError('INVALID_POLL_STATE')
        if job['state'] in ('NOT_DISPATCHED', 'EVIDENCE_AVAILABLE'):
            return _snapshot(job, document['revision'])
        try:
            if reconcile:
                response = self.transport.reconcile(operation_id=job['operation_id'], uncertainty_phase=job['uncertainty_phase'], after_sequence=job['observation_sequence'])
            else:
                response = self.transport.observe(operation_id=job['operation_id'], after_sequence=job['observation_sequence'])
        except Exception:
            raise RuntimeError('TRANSPORT_UNAVAILABLE') from None
        if type(response) is NoNewObservation:
            _integer(response.after_sequence, -1)
            if response.operation_id != job['operation_id'] or response.after_sequence != job['observation_sequence']:
                raise ValueError('NO_NEW_BINDING_MISMATCH')
            current, _, unchanged = self._load_job(job_id, expected_job_revision)
            if unchanged['operation_id'] != response.operation_id or unchanged['observation_sequence'] != response.after_sequence:
                raise StateConflictError('JOB_REVISION_CONFLICT')
            return _snapshot(unchanged, current['revision'])
        return self._accept(job_id, response, expected_job_revision=expected_job_revision, context=method)

    def _accept(self, job_id, response, *, expected_job_revision, context):
        document, digest, job = self._load_job(job_id, expected_job_revision)
        binding = {'job_id': job_id, 'operation_id': job['operation_id'],
                   'manifest_sha256': job['manifest_sha256'], 'cancel_operation_id': job['cancel_operation_id']}
        try:
            observed = self.observation_verifier.verify(binding=deepcopy(binding), observation=response)
            self._validate_observation(observed, job)
        except Exception:
            raise PermissionError('OBSERVATION_REJECTED') from None
        metadata = asdict(observed)
        if observed.sequence <= job['observation_sequence']:
            if metadata == job['last_observation']:
                return _snapshot(job, document['revision'])
            if observed.sequence < job['observation_sequence']:
                raise ValueError('OBSERVATION_STALE')
            raise ValueError('OBSERVATION_DRIFT')
        if observed.sequence != job['observation_sequence'] + 1:
            raise ValueError('OBSERVATION_GAP')
        state, phase = job['state'], job['uncertainty_phase']
        kind = observed.kind
        if kind == 'DISPATCHED':
            allowed = state == 'UNKNOWN' and phase == 'DISPATCH'
            target = 'DISPATCHED'
        elif kind == 'RUNNING':
            allowed = state in ('DISPATCHED', 'RUNNING') or (state == 'UNKNOWN' and phase in ('DISPATCH', 'RUN') and context == 'reconcile')
            target = 'RUNNING'
        elif kind == 'CANCEL_ACCEPTED':
            allowed = state == 'UNKNOWN' and phase == 'CANCEL'
            target = 'CANCEL_REQUESTED'
        elif kind == 'PROCESS_FINISHED':
            allowed = state in ('UNKNOWN', 'DISPATCHED', 'RUNNING', 'CANCEL_DUE', 'CANCEL_REQUESTED')
            target = 'PROCESS_FINISHED'
        elif kind == 'EVIDENCE_AVAILABLE':
            allowed = state == 'PROCESS_FINISHED'
            target = 'EVIDENCE_AVAILABLE'
        elif kind == 'ABSENT':
            allowed = state == 'UNKNOWN' and phase == 'DISPATCH' and context == 'reconcile' and observed.authoritative_absence
            target = 'NOT_DISPATCHED'
        else:
            allowed = False
            target = state
        if not allowed:
            raise ValueError('INVALID_OBSERVATION_TRANSITION')
        job.update(state=target, last_confirmed_state=target, uncertainty_phase=None,
                   observation_sequence=observed.sequence, last_observation=metadata,
                   worker_job_id=observed.worker_job_id, last_received_at=self._now())
        if observed.process is not None:
            job['process'] = asdict(observed.process)
        if observed.evidence is not None:
            job['evidence'] = asdict(observed.evidence)
        return self._save_job(document, digest, job, 'VERIFIED_' + kind)

    @staticmethod
    def _validate_observation(observed, job):
        if type(observed) is not VerifiedJobObservation:
            raise ValueError('INVALID_OBSERVATION')
        if observed.kind not in ('DISPATCHED', 'RUNNING', 'CANCEL_ACCEPTED', 'PROCESS_FINISHED', 'EVIDENCE_AVAILABLE', 'ABSENT'):
            raise ValueError('INVALID_OBSERVATION_KIND')
        for field in ('provider', 'observation_id', 'operation_id', 'worker_job_id'):
            _identifier(getattr(observed, field))
        _timestamp(observed.observed_at)
        _integer(observed.sequence)
        if observed.operation_id != job['operation_id'] or observed.manifest_sha256 != job['manifest_sha256']:
            raise ValueError('OBSERVATION_BINDING_MISMATCH')
        if job['worker_job_id'] is not None and observed.worker_job_id != job['worker_job_id']:
            raise ValueError('WORKER_BINDING_MISMATCH')
        if observed.cancel_operation_id is not None and observed.cancel_operation_id != job['cancel_operation_id']:
            raise ValueError('CANCEL_BINDING_MISMATCH')
        if observed.kind == 'CANCEL_ACCEPTED' and (job['cancel_operation_id'] is None or observed.cancel_operation_id != job['cancel_operation_id']):
            raise ValueError('CANCEL_BINDING_MISMATCH')
        if type(observed.authoritative_absence) is not bool or (observed.authoritative_absence and observed.kind != 'ABSENT'):
            raise ValueError('INVALID_ABSENCE')
        if observed.kind == 'ABSENT' and not observed.authoritative_absence:
            raise ValueError('INVALID_ABSENCE')
        if observed.kind == 'PROCESS_FINISHED':
            if type(observed.process) is not ProcessMetadata or observed.evidence is not None:
                raise ValueError('PROCESS_METADATA_REQUIRED')
            _process_metadata(observed.process)
        elif observed.kind == 'EVIDENCE_AVAILABLE':
            if type(observed.evidence) is not EvidenceMetadata or observed.process is not None:
                raise ValueError('EVIDENCE_METADATA_REQUIRED')
            _evidence_metadata(observed.evidence, job['manifest']['evidence_contract_sha256'])
        elif observed.process is not None or observed.evidence is not None:
            raise ValueError('UNEXPECTED_METADATA')

    def check_timeout(self, job_id, *, expected_job_revision):
        document, digest, job = self._load_job(job_id, expected_job_revision)
        now = self._now()
        if now < job['updated_at']:
            raise ValueError('CLOCK_REGRESSION')
        manifest = job['manifest']
        if job['state'] == 'RUNNING':
            heartbeat_deadline = job['last_received_at'] + manifest['heartbeat_timeout_seconds']
            execution_deadline = job['dispatched_at'] + manifest['execution_timeout_seconds']
            if now >= heartbeat_deadline and heartbeat_deadline <= execution_deadline:
                job.update(state='UNKNOWN', uncertainty_phase='RUN')
                return self._save_job(document, digest, job, 'HEARTBEAT_EXPIRED')
        if job['state'] in ('DISPATCHED', 'RUNNING') and now >= job['dispatched_at'] + manifest['execution_timeout_seconds']:
            job.update(state='CANCEL_DUE', uncertainty_phase=None)
            return self._save_job(document, digest, job, 'EXECUTION_DEADLINE_REACHED')
        if job['state'] == 'RUNNING' and now >= job['last_received_at'] + manifest['heartbeat_timeout_seconds']:
            job.update(state='UNKNOWN', uncertainty_phase='RUN')
            return self._save_job(document, digest, job, 'HEARTBEAT_EXPIRED')
        if job['state'] == 'CANCEL_REQUESTED' and now >= job['cancel_requested_at'] + manifest['cancel_grace_seconds']:
            job.update(state='UNKNOWN', uncertainty_phase='CANCEL')
            return self._save_job(document, digest, job, 'CANCEL_GRACE_EXPIRED')
        return _snapshot(job, document['revision'])
