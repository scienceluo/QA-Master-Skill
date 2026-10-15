# ADR-001 — Use one canonical workflow aggregate behind an application service

- Status: `PROPOSED`
- Date: 2026-10-15
- Artifact ID: `ADR-001`
- Requirements: `PRD-001`, `REQ-001`, `REQ-002`, `REQ-003`, `REQ-006`, `REQ-009`, `REQ-012`, `NFR-001`, `NFR-004`
- Related design: [DES-019](DES-019-canonical-campaign-workflow.md)

## Context

The installed command persists `core.Campaign`, while stronger dependency, exact-binding and receipt rules exist in `workflow.Workflow`. The offline campaign command is a third orchestration path. Maintaining all three as peers creates inconsistent readiness and approval behavior and prevents a safe schema migration.

The change must preserve existing command spellings and legacy data, support local/offline use, and remain fail closed. In particular, legacy free-text approvals cannot become trusted decisions merely because they are migrated.

## Options considered

### A. Make `Campaign` canonical and copy `Workflow` behavior into it

This minimizes changes in `qa_master.__main__`, but preserves the weaker model as the center of the product. Approval and graph rules would have to be copied, with a high risk of keeping two subtly different implementations while compatibility code remains.

### B. Make `Workflow` semantics canonical and place all entry points behind an application service

This reuses the stronger dependency, exact-binding, invalidation and receipt concepts. The service becomes the only mutation boundary. `Campaign` and the offline CLI remain compatibility adapters during migration. It requires a versioned state migration and changes legacy `approve` semantics from authorizing to audit-only.

### C. Introduce an event-sourced database aggregate now

An append-only transactional store would improve multi-user concurrency and projections. It adds deployment, backup, schema, operational and migration complexity that is unsupported by current local-product requirements and evidence. It would also combine the workflow correction with a storage-platform replacement.

### D. Keep all models and synchronize them bidirectionally

This appears compatible but creates dual-write failure modes and requires conflict resolution between approval and invalidation models. A partial failure could make one path report readiness while another denies it.

## Decision

Choose **B**.

Implement one `CampaignWorkflow` aggregate based on current `Workflow` semantics, accessed only through `CampaignApplicationService`. Persist it as `qa-master.campaign` schema v2 using the existing locked, atomic, revision-CAS JSON repository through a repository port. `Campaign` becomes a compatibility adapter and never owns separate authoritative state. The pure `campaign_cli.prepare_campaign` utility remains stateless and cannot authorize or mutate a campaign.

The v2 migration preserves legacy data but classifies free-text approvals as `UNVERIFIED_LEGACY`. Existing receipt-shaped or exact-approval-shaped records are not upgraded to provider-verified assurance. Read-only operations migrate only in memory; the first mutation creates a copy-once backup and atomically writes v2. There is no dual write.

## Consequences

Positive:

- every entry point receives identical task-scope, pause, dependency, invalidation and approval behavior;
- compatibility is isolated from security policy;
- migration and rollback are explicit and testable;
- a future database repository can replace JSON without changing command or aggregate contracts.

Costs and risks:

- scripts that relied on `qa-master approve` to make execution ready will continue to parse, but the command will only record an unverified assertion;
- legacy completed side effects require revalidation, which may expose previously hidden evidence gaps;
- a state migration and deprecation window are required;
- JSON remains unsuitable for high-contention, multi-user operation.

## Reversibility

The application and repository ports keep a future transactional store possible. The copy-once legacy backup allows executable rollback before post-migration mutations. After new commands are committed, automatic downgrade is deliberately refused because it would lose decisions and invalidation history.

## Validation

The current increment is accepted against the stable `TC-SM-001` through `TC-SM-013` contract in `DOC-SCHEMA-MIGRATION-TEST-PLAN-001`, reconciled with `DES-019`, followed by independent tester and reviewer evidence. The broader provider/worker target uses the deferred `TC-DES` cases in `DES-019`. This proposed decision does not itself approve a requirement, migration or release.
