# ADR-002 — Keep approval and worker trust outside the workflow process

- Status: `PROPOSED`
- Date: 2026-10-15
- Artifact ID: `ADR-002`
- Requirements: `REQ-003`, `REQ-007`, `REQ-008`, `REQ-009`, `NFR-001`–`NFR-004`
- Related design: [DES-019](DES-019-canonical-campaign-workflow.md)

## Context

Current local code can bind an artifact or completion to a digest, but a reviewer name, caller callback or receipt-shaped object does not authenticate a person, service or worker. The product also has no production IAM, key lifecycle, remote worker bootstrap, transport, scheduler or revocation service.

The canonical workflow needs stable interfaces for future trustworthy approvals and remote receipts without enabling side effects or claiming those missing services exist.

## Options considered

### A. Trust local reviewer strings and booleans

This is simple and compatible, but any caller can manufacture approval. It cannot meet operation-specific authorization or evidence provenance requirements.

### B. Embed key files and signature verification directly in the aggregate

This can prove possession of a key but couples domain logic to one key format and storage method. A key file on the same mutable host does not establish organizational identity, authorization policy, revocation or production IAM. It also risks placing secrets in campaign state.

### C. Define trust-provider and worker ports with typed, exact bindings

The application service builds canonical envelopes and calls configured providers. Providers return typed verified claims; the aggregate checks the binding and policy-relevant metadata again. No provider means denial. A local signature provider can later support bounded offline use, while external IAM and worker services can implement the same ports.

### D. Let each enterprise adapter and runner define its own approval callback

This keeps modules independent but duplicates policy and produces incompatible envelopes, expiry handling, audit fields and failure behavior.

## Decision

Choose **C**.

Define separate ports for approval verification, completion verification, worker scheduling and enterprise writes. The service, rather than the caller, constructs canonical envelopes. Providers return typed claims, never booleans. Campaign state stores non-secret verified metadata and binding digests, not private keys, bearer tokens, raw proofs or credential material.

A future local signature provider may verify detached signatures against an operator-managed trust store and return `LOCAL_SIGNATURE_VERIFIED`. Its documented scope is a bounded local/offline deployment. It must not claim production identity, multi-user separation, revocation guarantees or organizational authorization unless those facilities are separately implemented and validated.

A future remote worker protocol uses a content-addressed `JobManifest` and explicit state machine:

```text
AUTHORIZED -> DISPATCHED -> RUNNING -> PROCESS_FINISHED
           -> EVIDENCE_UPLOADED -> EVIDENCE_VERIFIED
```

`CANCEL_REQUESTED`, `CANCELLED`, `FAILED` and `UNKNOWN` are explicit branches. Dispatch acknowledgment, process completion, evidence upload, evidence verification and business outcome are distinct signed/verified messages. Retrying an `UNKNOWN` operation is prohibited until authorized reconciliation resolves it.

The job manifest binds campaign/step/revision, immutable source or package digest, absolute command identity, target/environment/build identity, exact case set, sanitized environment/config digest, timeout, resource limits, evidence destination/retention, opaque secret references, nonce and idempotency key. A future transport must authenticate both ends and provide replay protection; no transport is selected by this ADR.

## Consequences

Positive:

- workflow policy is consistent across local runner, remote worker and enterprise adapters;
- signatures, IAM and transport can evolve outside the aggregate;
- missing trust infrastructure fails closed;
- audit records distinguish assertion, cryptographic verification, dispatch, process completion, evidence verification and business result.

Costs and risks:

- side effects remain unavailable until a provider and policy are configured;
- provider availability becomes a dependency for authorization and completion;
- local signatures alone can be overinterpreted, so assurance labels and documentation must remain explicit;
- remote cancellation, lease recovery, clock skew, key rotation and artifact retention require additional product and operational requirements.

## Security and failure rules

- Verify expiry, nonce/replay state, action, target and full binding; deny on clock/provider error.
- Treat private keys and tokens as external secret-store concerns; campaign state contains only references and digests.
- Do not log raw approval proofs, secrets, full external payloads or presigned URLs.
- A receipt with a valid signature but mismatched binding is invalid.
- A successful process receipt leaves business outcome `NOT_ASSESSED` until evidence is separately parsed and verified.
- Loss of a response after an irreversible call results in `UNKNOWN`; the system does not retry automatically.

## Deferred decisions

The following require requirements and threat-model approval before implementation: provider/IAM product, trust-root ownership, signature algorithm profile, clock and revocation policy, remote transport, worker enrollment, sandbox/isolation level, target inventory authority, heartbeat/cancel SLA, retention and deletion policy, multi-tenancy, and disaster recovery.

## Validation

Use deterministic fake providers only in unit/contract tests. Independent security review must verify that the production default has no configured provider, all side-effect paths deny, typed claims cannot be replaced by truthy values, bindings cover every operation-specific field, and logs/state contain no credential material. This ADR does not authorize a live enterprise write or remote execution.
