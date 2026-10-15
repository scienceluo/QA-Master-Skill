# DES-026 — Local job lifecycle and scheduler core

- Artifact ID: `DES-026`
- Document State: `DRAFT`
- Evaluation State: `IN_REVIEW`
- Change / task: `CR-008` / `TASK-026`
- Requirements: `REQ-008`, `REQ-009`, `NFR-001`–`NFR-004`
- Inputs: [ADR-002](ADR-002-authority-and-worker-trust-boundary.md), [ADR-003](ADR-003-reconciliation-first-job-dispatch.md), `qa_master.local_runner`, `qa_master.sync_journal`
- Evidence boundary: this is a local core design. It does not select a transport, implement IAM, dispatch a real worker, execute a process, verify evidence, or report a test result.

## Scope and existing boundaries

The current local runner binds a command and workspace to a provider receipt and separates process status from business result. The operation journal already demonstrates the required irreversible-call rule: persist `UNKNOWN` before I/O and never retry an uncertain operation automatically. Neither module is a remote scheduler.

This slice defines a small persistent job core that can be tested with deterministic fake ports. It deliberately does not call `local_runner`, select SSH/WinRM/HTTP, resolve credentials, allocate capacity, delete retained evidence, or create a new human-approval system.

## Exact content-addressed manifest

`JobManifest` accepts exactly these keys; extra or missing keys fail validation:

| Field | Contract |
|---|---|
| `schema_version` | Integer `1`, not boolean. |
| `job_key` | Non-secret caller idempotency key, 1–200 characters. It must equal the key passed to `prepare`. |
| `nonce` | Non-secret unique value, 16–128 characters. A deliberate new execution uses a new nonce and job key. |
| `campaign_id`, `step_id`, `project` | Non-empty bounded identifiers. |
| `workflow_revision` | Non-negative integer, not boolean. |
| `build_sha256`, `case_set_sha256`, `command_sha256` | Lowercase 64-hex digests of the exact approved build, ordered case-set contract and command plan. The command text is not stored here. |
| `config_sha256`, `environment_sha256`, `resource_policy_sha256` | Lowercase 64-hex digests. Raw configuration, environment values and resource policy are not stored. |
| `target_id` | Opaque non-secret inventory identifier; no hostname, URL or credential is required by this core. |
| `execution_timeout_seconds` | Integer `1..86400`. |
| `heartbeat_timeout_seconds` | Integer `1..3600`, no greater than execution timeout. |
| `cancel_grace_seconds` | Integer `1..600`. |
| `evidence_sink_id` | Opaque non-secret sink identifier. |
| `evidence_contract_sha256` | Digest of required evidence shape and size rules. |
| `retention_policy_id` | Opaque retention-policy identifier. The core records it but performs no deletion. |

Canonical bytes are UTF-8 JSON with sorted keys, compact separators, no NaN, and a 64 KiB maximum. `manifest_sha256 = SHA256(canonical_bytes)`. The manifest contains no argv, endpoint, token, cookie, private key, environment value, raw secret reference or presigned URL. Transport-specific resolution occurs outside this core and must reproduce the bound digests.

## Persistent record

The local `JobRepository` stores one revisioned JSON journal using the existing lock/CAS/atomic-replace behavior. It contains a repository revision, a SHA-256 index of job keys, and job records. Each record contains:

- `job_id`, manifest and manifest digest;
- job revision and current state;
- stable dispatch `operation_id` and optional cancel `cancel_operation_id`;
- verified authorization metadata, never the opaque proof;
- last verified observation sequence, canonical digest, identity and non-secret receipt metadata;
- timeout/cancel metadata, uncertainty phase and last confirmed state;
- process receipt metadata and evidence reference/digest when observed;
- monotonic local event sequence and redacted events;
- `business_result: NOT_ASSESSED`.

Every `JobSnapshot` exposes both `job_revision` and the repository-wide `store_revision` read by the operation. Callers use `job_revision` for commands on that job and use the returned `store_revision` as the next `expected_store_revision` for `prepare`; they never infer either value from event counts or file contents.

The MVP is a bounded single-host journal, not a distributed queue. A default cap of 1,000 jobs and 64 KiB per manifest is an implementation safety limit subject to measurement.

## Ports and minimal API

The scheduler receives an injected clock and three optional ports. No default implementation is installed.

```python
class AuthorizationVerifier(Protocol):
    def verify(self, *, action: str, binding: dict, proof: object) -> VerifiedOperationAuthorization: ...

class ObservationVerifier(Protocol):
    def verify(self, *, binding: dict, observation: object) -> VerifiedJobObservation: ...

@dataclass(frozen=True)
class NoNewObservation:
    operation_id: str
    after_sequence: int

class JobTransport(Protocol):
    def dispatch(self, *, manifest: bytes, operation_id: str) -> object: ...
    def observe(self, *, operation_id: str, after_sequence: int) -> object: ...
    def request_cancel(self, *, operation_id: str, cancel_operation_id: str) -> object: ...
    def reconcile(self, *, operation_id: str, uncertainty_phase: str, after_sequence: int) -> object: ...
```

Synthetic test ports are labeled `SYNTHETIC` and cannot establish real trust or remote execution.

```python
prepare(manifest, *, idempotency_key, expected_store_revision) -> JobSnapshot
dispatch(job_id, *, proof, expected_job_revision) -> JobSnapshot
observe(job_id, *, expected_job_revision) -> JobSnapshot
request_cancel(job_id, *, reason, proof, expected_job_revision) -> JobSnapshot
check_timeout(job_id, *, expected_job_revision) -> JobSnapshot
reconcile(job_id, *, expected_job_revision) -> JobSnapshot
get(job_id) -> JobSnapshot
```

`prepare` and `get` work without ports. An empty repository starts at `store_revision = 0`; after a successful `prepare`, its returned snapshot supplies the new store revision, so preparing a second distinct job does not require an out-of-band repository read. `dispatch` requires all three ports so its response can be verified. `observe` and `reconcile` require transport plus observation verifier. `request_cancel` also requires a fresh, operation-specific authorization proof; persisted dispatch authorization cannot authorize cancellation. Missing required ports raises `PORT_UNAVAILABLE` before provider calls, network calls or repository mutation. The injected scheduler clock, rather than caller-supplied time, controls authorization expiry and timeouts.

`VerifiedOperationAuthorization` must bind action, job ID, manifest digest, operation ID, issue/expiry times and provider/authorization IDs. The scheduler accepts it only when `issued_at <= clock.now() < expires_at`, using normalized UTC instants from the injected clock.

Every `VerifiedJobObservation` binds its `operation_id` to the original dispatch operation ID, plus provider/observation ID, manifest digest, worker job ID, strictly increasing non-negative sequence, observation kind and observed time. A `CANCEL_ACCEPTED` observation additionally carries and exactly matches the current `cancel_operation_id`, thereby binding cancellation to its parent dispatch. State-specific metadata is typed; truthy booleans and free-form dictionaries are rejected. Remote `observed_at` is audit metadata only in this MVP; it is not used for age or future-skew acceptance.

## Lifecycle and transition rules

| Current | Trigger | Next | Required invariant |
|---|---|---|---|
| absent | `prepare` | `PREPARED` | Same key + same manifest is idempotent; key drift is rejected. |
| `PREPARED` | `dispatch` | `UNKNOWN / DISPATCH` before I/O | All ports exist; dispatch proof verifies and is unexpired; one CAS winner records `AUTHORIZED` and the stable operation ID before the transport call. |
| `UNKNOWN / DISPATCH` | verified dispatch observation | `DISPATCHED` | Exact operation/manifest binding and next observation sequence. |
| `DISPATCHED` | verified running observation | `RUNNING` | No state skip or sequence replay. |
| `DISPATCHED` or `RUNNING` | execution deadline | `CANCEL_DUE` | Local clock only; this does not claim the process stopped or timed out. |
| `RUNNING` | heartbeat deadline | `UNKNOWN / RUN` | Last confirmed state is retained; no automatic cancel or redispatch. |
| `DISPATCHED`, `RUNNING`, `CANCEL_DUE`, or `UNKNOWN / RUN` | `request_cancel` | `UNKNOWN / CANCEL` before I/O | Fresh cancel proof binds reason and cancel operation ID. |
| `UNKNOWN / CANCEL` | verified cancel-accepted observation | `CANCEL_REQUESTED` | Dispatch operation ID and child cancel operation ID both match. Acceptance is not process termination. |
| `CANCEL_REQUESTED` | cancel grace expires | `UNKNOWN / CANCEL` | Never infer `CANCELLED`. |
| dispatch/run/cancel active or unknown | verified terminal process observation | `PROCESS_FINISHED` | Exact binding; termination reason and process state recorded; business result remains `NOT_ASSESSED`. |
| `PROCESS_FINISHED` | verified evidence-available observation | `EVIDENCE_AVAILABLE` | Evidence ref, digest, byte count and evidence-contract binding are present. |
| `UNKNOWN` | `reconcile` + verified observation | corresponding confirmed state | Reconcile with the dispatch operation ID plus uncertainty phase; never submit again. |
| `UNKNOWN / DISPATCH` | verified authoritative absence | `NOT_DISPATCHED` | Terminal for this job; a new manifest nonce/job key and new authorization are required for another attempt. |

`EVIDENCE_VERIFIED` is reserved for a later independent `EvidenceVerifier`; this slice cannot enter it. `EVIDENCE_AVAILABLE` is not a test result, authenticated evidence, release evidence or proof of retention.

Authoritative absence is meaningful only for `UNKNOWN / DISPATCH`. An absence result while `UNKNOWN / CANCEL` proves neither that the job was not dispatched nor that cancellation cannot still arrive; the record remains unknown. A verified terminal worker observation during cancellation still uses the dispatch operation ID and may converge the job to `PROCESS_FINISHED`.

### Irreversible-call ordering

For dispatch and cancel, the scheduler validates ports, input and authorization, then performs one repository transaction that reserves the stable operation ID and sets `UNKNOWN`. Only the CAS winner calls transport. The object returned directly by `transport.dispatch` or `transport.request_cancel` is raw: it must pass `ObservationVerifier`, then be stored with CAS against the reserved job revision. A transport exception, verification failure, post-I/O CAS conflict, or process crash causes no retry and leaves the durable record `UNKNOWN`. Repeating `dispatch` or `request_cancel` returns/refuses the uncertain record without calling transport again.

The injected clock time recorded in the dispatch reservation anchors `execution_deadline_at`. The local receive time of each verified `RUNNING` observation anchors `heartbeat_deadline_at`. The cancel reservation time anchors `cancel_grace_deadline_at`. A boundary is due when `clock.now() >= deadline`. These persisted local anchors make restart behavior deterministic.

When a `RUNNING` timeout check finds both execution and heartbeat deadlines due, the earlier persisted deadline is the single transition oracle. If `heartbeat_deadline_at <= execution_deadline_at`, the scheduler enters `UNKNOWN / RUN`; otherwise it enters `CANCEL_DUE`. The equality rule favors heartbeat uncertainty because process liveness was already unconfirmed at that instant. Once in `UNKNOWN / RUN`, timeout checking does not advance to `CANCEL_DUE`; reconciliation or an explicitly authorized cancel request must resolve the uncertainty.

### Observation ordering and reconciliation

The scheduler calls `observe` and `reconcile` with `after_sequence` equal to the last accepted stored sequence, or `-1` before the first observation. The transport query is non-consuming: it returns the stable next observation at `after_sequence + 1`, or `NoNewObservation`; repeated calls with the same cursor cannot advance or discard a provider-side record. A provider or adapter that can return only its latest observation does not satisfy this port.

`NoNewObservation` is a transport control result, not a worker observation or authoritative absence assertion. It is accepted only from `observe` or `reconcile` when `operation_id` exactly equals the persisted dispatch operation and `after_sequence` is the exact requested cursor; the integer is strict and cannot be boolean. It does not pass through `ObservationVerifier`, because it asserts no worker fact. Before returning an unchanged snapshot, the scheduler re-reads the job and requires the expected job revision, operation ID and cursor still to match; otherwise it returns `REVISION_CONFLICT`. No-new writes no event, refreshes no heartbeat or deadline, changes no state/revision, and creates no evidence or business claim.

The scheduler verifies observation type and binding before mutation. Exact replay idempotence is limited to the **last accepted** observation: same sequence and same canonical digest/identity returns the current snapshot without mutation. Same sequence with different content is `OBSERVATION_DRIFT`; every lower sequence is rejected as stale because the MVP does not retain a full replay ledger. A returned sequence greater than `after_sequence + 1` is `OBSERVATION_GAP` and causes no mutation. Future or skipped lifecycle states fail closed. Remote timestamps are audit metadata; persisted local receive times and the injected clock control deadlines.

Normal `observe` advances confirmed states. `reconcile` is permitted only from `UNKNOWN` and uses `transport.reconcile` with the dispatch operation ID, uncertainty phase and stored sequence cursor. A non-authoritative “not found” result cannot prove absence and leaves the job unknown. `UNKNOWN / CANCEL` never transitions to `NOT_DISPATCHED` from an absence observation. If two polls fetch the same next observation, one CAS may succeed and the other returns a repository conflict; the remote read has not consumed a cursor. A subsequent call derives its cursor from the newly read job snapshot. The scheduler does not silently retry the local mutation.

## Failure, security and operational properties

- Authorization/verifier/transport exceptions expose only stable error codes; no proof, raw observation or endpoint is logged.
- Repository conflicts are returned; the scheduler never silently retries a mutation or transport call.
- A zero process exit is recorded as process metadata only. Business outcome remains `NOT_ASSESSED`.
- Cancellation races are resolved by verified sequence. A terminal process observation wins over a later cancel acknowledgment without rewriting the termination reason.
- Journal corruption, unknown state/schema or manifest mismatch fails read-only; original bytes are not replaced.
- Events contain job/operation IDs, state change, local time, sequence and digests, with no raw command, secret, proof or transport payload.
- Recovery uses the persisted operation ID. Restarting the process does not change an uncertain job into a retryable job.

## Acceptance mapping for independent tests

The tester may assign stable `TC-JS` IDs. The design requires at least these observable oracles:

1. canonical manifest determinism, strict fields/limits and digest drift;
2. prepare replay and idempotency-key drift rejection;
3. snapshots expose job and store revisions; an empty-store prepare at revision zero returns the revision accepted by a subsequent distinct prepare;
4. missing ports, boolean/malformed/expired/mismatched authorization all deny before mutation or transport;
5. concurrent dispatch invokes transport once; lost/malformed response remains `UNKNOWN / DISPATCH`;
6. repeated dispatch/cancel from `UNKNOWN` never invokes transport again;
7. observations bind the dispatch operation; cancel acceptance also binds the child cancel operation; `observe`/`reconcile` request the stable next record using the stored sequence cursor; an exactly bound `NoNewObservation` returns an unchanged re-read snapshot and cannot refresh liveness or evidence; lower sequence, same-sequence drift, latest-only sequence gap and lifecycle skip fail closed, while exact replay of only the last accepted observation is idempotent;
8. injected-clock boundaries use `now >= deadline`: dispatch reservation anchors execution timeout, verified-running local receipt anchors heartbeat, and cancel reservation anchors grace; when execution and heartbeat are both due, the earlier deadline wins and an equal deadline enters `UNKNOWN / RUN`; no boundary manufactures `PROCESS_FINISHED` or `TIMEOUT`;
9. authorization requires `issued_at <= now < expires_at`; cancel requires fresh cancel-bound proof; cancel acknowledgment is only `CANCEL_REQUESTED`; grace expiry becomes unknown;
10. verified terminal process metadata never creates PASS/FAIL and remains `NOT_ASSESSED`;
11. evidence observation reaches only `EVIDENCE_AVAILABLE`; no evidence verification or release claim is possible;
12. reconciliation reuses the dispatch operation ID and uncertainty phase, requires authoritative verified observation, never redispatches, and treats authoritative absence as terminal only for unknown dispatch;
13. direct dispatch/cancel responses pass observation verification and reserved-revision CAS; transport, verification, CAS and crash faults preserve the uncertain reservation;
14. persisted state, events and errors contain no argv, endpoint, secret, proof or raw transport response.

The fake-port suite must include a latest-only provider returning a skipped sequence and two concurrent polls using the same cursor. The former is rejected as `OBSERVATION_GAP`; the latter proves that the losing CAS does not consume or lose the next provider observation.

These are local fake-port contract tests only. Their results cannot be described as SSH, WinRM, worker, staging or production execution.

## Deferred requirements and developer handoff

The implementation slice may add only manifest/types, local repository, scheduler state machine, fake-port tests and documentation. It must not integrate `local_runner` or enterprise adapters in this change.

Transport protocol, worker enrollment, host identity, production authorization, signature/key rotation, secret broker, capacity allocation, sandboxing, actual heartbeat service, evidence download/verification, retention deletion and disaster recovery remain unresolved product/security requirements. Their absence does not block this local core, but it blocks every real remote-execution claim.
