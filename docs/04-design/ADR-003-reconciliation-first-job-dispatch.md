# ADR-003 — Reserve UNKNOWN before job transport calls

- Artifact ID: `ADR-003`
- Status: `PROPOSED`
- Date: 2026-10-15
- Requirements: `REQ-008`, `REQ-009`, `NFR-001`, `NFR-002`, `NFR-004`
- Related design: [DES-026](DES-026-local-job-lifecycle-scheduler-core.md)

## Context

A dispatch or cancellation can reach a worker even when the caller receives a timeout or crashes before saving the response. Treating that error as “not sent” and retrying can execute a test twice or cancel the wrong attempt.

## Alternatives

1. Retry transport errors automatically. This improves apparent availability but can duplicate irreversible operations.
2. Save `DISPATCHED` before the call. This falsely claims a worker accepted work.
3. Persist an `UNKNOWN` reservation with a stable operation ID before the call, then reconcile that same operation. This preserves uncertainty and prevents duplicate calls.
4. Require a distributed transaction with every future worker. No such transport or transaction coordinator exists, and the requirement would prevent a transport-neutral local core.

## Decision

Choose option 3. Validate all configured ports and operation-specific authorization first. In one CAS transaction, record the authorization event, stable operation ID and `UNKNOWN` phase. Only that CAS winner may call transport. A verified observation moves the record forward. Missing/malformed/lost responses remain unknown; repeated commands never call transport again. Reconciliation reuses the same operation ID. Only a verified authoritative-absence observation may end the job as `NOT_DISPATCHED`, after which another attempt requires a new manifest nonce, job key and authorization.

The same rule applies to cancellation. Cancel acceptance does not imply process termination. Local timeout and heartbeat decisions never manufacture a terminal worker state.

## Consequences

- Duplicate dispatch/cancel is prevented at the local coordinator boundary.
- Some jobs remain unknown until a future transport can reconcile them; availability is traded for correctness.
- The local repository and operation ID become durable recovery dependencies.
- This decision does not prove a transport is exactly-once. It prevents automatic duplicate calls and records observable uncertainty.

## Reversibility and validation

The scheduler ports allow a future transactional queue, but its stronger guarantee must be independently demonstrated before changing the state semantics. Local fake-port tests must cover lost responses, concurrent callers, replay, restart and authoritative/non-authoritative reconciliation. No such test is remote-execution evidence.
