# Local job scheduler core

This is the CR-008 / DES-026 local protocol core. It does not provide SSH,
WinRM, HTTP transport, a worker process, IAM, a secret broker, capacity allocation
or evidence retention/deletion. The installed planning CLI does not dispatch it.

Host applications can instantiate `qa_master.job_scheduler.JobScheduler` with a
`JobRepository(path)`, an injected clock and explicitly configured transport,
authorization-verifier and observation-verifier ports. The default has no ports.
`prepare` and `get` are local-only; dispatch and cancellation require exact,
unexpired `VerifiedOperationAuthorization` claims from the host verifier.
Plain booleans, reviewer names and stored dispatch claims cannot authorize a
new cancellation. Test fixture ports are synthetic, not real authorization.

`JobManifest.create(document)` requires the exact fields in
[DES-026](04-design/DES-026-local-job-lifecycle-scheduler-core.md). It stores
digests and non-secret opaque identifiers rather than argv, endpoints, secret
references or environment values. The host is responsible for resolving an
execution plan that matches these digests. A new execution requires a new job
key and nonce. Same-key/same-manifest prepare is idempotent; changed content is
rejected. Limits: 1,000 jobs, 64 KiB per manifest, 50 MB journal, 10,000 events
per job. Capacity and multi-host operation are not validated product claims.

All mutations use revision/digest CAS. Callers pass `expected_store_revision`
to prepare and `expected_job_revision` to lifecycle commands. A conflict is
returned to the caller and never causes an automatic transport retry.
Snapshots expose `job_revision` (also `revision`) and `store_revision`, so a
caller can prepare another job with the current journal revision.

Before dispatch or cancellation, the core persists an `UNKNOWN` reservation
with its operation ID. Only the CAS winner calls the port. An exception or
malformed response leaves the reservation uncertain. After restart, use
`reconcile` with that operation ID; do not redispatch. Verified authoritative
absence can close an uncertain dispatch as `NOT_DISPATCHED`, requiring a new
manifest/key/authorization for another execution.

Worker observations use `VerifiedJobObservation`, with typed `ProcessMetadata`
or `EvidenceMetadata` as appropriate. Every observation binds the dispatch ID,
manifest digest and stable worker ID. Cancel acknowledgment also binds the
cancel operation ID. Sequences start at zero and advance by one. Only the exact
last observation can be replayed idempotently; it does not refresh heartbeat
time. Old, conflicting or skipped sequences are rejected. Evidence reaches
`EVIDENCE_AVAILABLE` only: there is no evidence-verification port in this slice.

The transport's `observe` and `reconcile` receive `after_sequence` (initially
`-1`). They must return the next stable, non-consuming record at cursor + 1,
allowing concurrent callers to reread it after a CAS conflict. A latest-only
stream is insufficient. `NoNewObservation(operation_id, after_sequence)` may
signal that no next record is available. The core checks its binding and rereads
the expected revision without changing state or refreshing liveness. This is
not authoritative absence and does not pass through the observation verifier.

Deadlines use the injected local clock: execution starts at dispatch reservation,
heartbeat at the latest verified observation received locally, and cancellation
grace at cancel reservation. At `now >= deadline`, execution becomes
`CANCEL_DUE`, missed heartbeat becomes `UNKNOWN/RUN`, and missed cancel grace
becomes `UNKNOWN/CANCEL`. None means the process stopped. Cancellation requires
a fresh proof; a cancel acknowledgment is merely `CANCEL_REQUESTED`.
For RUNNING jobs, the earlier deadline wins; heartbeat wins ties. UNKNOWN/RUN
then requires explicit reconciliation or cancellation. Worker `observed_at`
is audit metadata; future clock skew does not change local deadlines.

Verified process termination is recorded separately. Even exit code zero leaves
`business_result` as `NOT_ASSESSED`; no PASS/FAIL, defect closure, acceptance or
release decision is produced. Provider/transport failures never persist opaque
proofs, raw responses or exception messages. Cancellation reasons are bound by
digest. Hosts must protect journal permissions and supply non-secret identifiers;
this JSON journal is not a signed or tamper-proof organizational audit store.

Developer unit tests live in `tests/test_job_scheduler.py`; all ports there are
synthetic and neither contact a network nor start a process. Independent evidence
is tracked separately under `docs/verification/`. No local test establishes a
real remote-execution result.
