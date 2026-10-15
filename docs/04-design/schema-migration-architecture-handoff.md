# Canonical workflow schema migration architecture handoff

- Artifact ID: `DOC-SCHEMA-MIGRATION-ARCH-HANDOFF-001`
- Document State: `DRAFT`
- Evaluation State: `IN_REVIEW`
- Change / task: `CR-007` / `TASK-019`
- Design: [DES-019](DES-019-canonical-campaign-workflow.md)
- Decisions: [ADR-001](ADR-001-canonical-workflow-aggregate.md), [ADR-002](ADR-002-authority-and-worker-trust-boundary.md)
- Test contract: [DOC-SCHEMA-MIGRATION-TEST-PLAN-001](../verification/schema-migration-test-plan.md)

## Implementation MVP

The developer may implement only the bounded local migration slice:

- make the installed CLI use one application service and schema-v2 state document;
- preserve all validated legacy `Campaign` and `Workflow` JSON in `legacy_payload`, while mapping canonical fields and never upgrading free-text approval assurance; reject ambiguous dual/partial legacy shapes;
- use deterministic UUIDv5 projection, unknown/future-schema rejection, read-only in-memory projection, first-mutation digest/revision CAS, copy-once backup and lock-protected `create_if_absent`;
- persist pause/resume and recursively validate ancestor bindings before a descendant can remain done or become ready;
- mark every migrated completion that depends on a downgraded approval or receipt `NEEDS_REVALIDATION`, including non-side-effect baselines and their descendants;
- keep `core.Campaign` and `workflow.Workflow` Python APIs compatible and explicitly deprecated; keep `campaign_cli` stateless and draft-only;
- preserve legacy bytes without heuristic secret deletion, while treating payload/backups as sensitive owner-only local state and never rendering them in CLI output, events or logs.

`CampaignApplicationService` is the sole stateful installed-CLI mutation boundary. The repository separates `create_if_absent`, `migrate_existing` and `save_existing`; revision zero must not authorize overwriting an existing revisionless file.

## Acceptance mapping

Implementation and developer checks must map to the existing `TC-SM-001`–`TC-SM-013` meanings in `DOC-SCHEMA-MIGRATION-TEST-PLAN-001`. Independent execution belongs to `TASK-021`; no test result is asserted by this handoff. The implementation handoff must identify exact files/commit and any interface deviation for tester reconciliation.

## Explicitly deferred

Production IAM, a local signing-provider implementation, general request-ID replay infrastructure, remote workers, enterprise dispatch, live integrations, multi-user state, release and acceptance are not part of this MVP. ADR-002 defines future trust boundaries only. Existing typed receipt metadata may be preserved, but migration does not re-authenticate it or turn it into production evidence.

This handoff is a reviewable architecture input. It is not a requirement approval, implementation result, test result, Gate decision or release authorization.
