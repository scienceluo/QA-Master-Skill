# QA Master schema migration and pause/resume continuation plan

- Artifact ID: `DOC-SCHEMA-MIGRATION-PLAN-001`
- Document State: `DRAFT`
- Evaluation State: `NOT_EVALUATED`
- Evidence Status: `OBSERVED` for the recorded human direction; all implementation and test evidence is `PENDING`.
- Change: `CR-007`

## Scope and boundary

The current direction is to continue developing QA Master itself by unifying the CLI, Campaign and Workflow state schema, then adding durable pause/resume behavior. It does not authorize a production or enterprise test campaign, external execution, external writes, a requirements-baseline approval, a Gate decision, or a release.

The preceding frozen candidate and its portability evidence remain historical evidence. This plan starts a new design and implementation slice; it does not change the full-V1 conclusion. Enterprise E2E remains `NOT_EXECUTED` until separately authorized.

## Delivery chain

| Task | Runtime work | Role / identity | Dependency | Required output | Current evidence |
|---|---|---|---|---|---|
| TASK-019 | `work-8d8bca78289049f99166d2c063341a8a` | architect `/root/workflow_architecture` | None | Canonical schema, migration, state-machine and recovery design plus design note | PENDING |
| TASK-020 | `work-e68daa77f33e4eccb7ea5b21b82d0c6c` | developer `/root` | TASK-019 | Scoped code change and implementation documentation | PENDING |
| TASK-021 | `work-1b1da1470b9244cea7071401ba085189` | tester `/root/workflow_validation` | TASK-020 | Fresh independent local test evidence and defects when warranted | PENDING |
| TASK-022 | `work-6fd521472a424d47a5b0d654c3b0951f` | reviewer `/root/workflow_review` | TASK-021 | Independent review evidence and classified findings | PENDING |

Work records were created on 2026-10-15 after the direction was received. The first prepared TASK-020–022 work records were superseded before claim when the active-host assignment was corrected; their Runtime status is `REVIEW_REQUIRED` and they have no outputs. The listed replacement records are the current dependency chain. No work was claimed or finished by this planning record. The Runtime has registered `/root/workflow_architecture` as `architect`, `/root/workflow_validation` as `tester`, and `/root/workflow_review` as reviewer. TASK-022 must still wait for TASK-021 to finish before claim.

## Acceptance model to design and test

The architecture handoff must resolve the following model before implementation begins:

1. One versioned canonical state schema defines ownership and conversion boundaries for CLI, Campaign and Workflow state.
2. State transitions specify pause, resume, reload/restart, allowed resume scope, revision handling and rejection of stale or conflicting completion/writes.
3. Legacy state maps deterministically and idempotently, leaves an auditable version/migration record, preserves readable required history, and fails safely for unsupported or ambiguous data.
4. Migration, reload and resume preserve the existing default denial of external execution and external writes; they must not convert a read-only/design-only request into authority.
5. Failure, recovery and rollback boundaries are explicit. A migration error must not silently substitute a new empty or divergent workflow state.

The design is required to state its unresolved assumptions. A design handoff is a candidate artifact, not an approval of those assumptions.

## Planned independent test points

| Test case | Purpose | Evidence status |
|---|---|---|
| TC-SM-001 | Canonical CLI, Campaign and Workflow round trip | PENDING |
| TC-SM-002 | Legacy migration, version compatibility and idempotence | PENDING |
| TC-SM-003 | External execution/write authority remains denied after migration and reload | PENDING |
| TC-SM-004 | Pause persists through restart/reload and resume retains permitted history/revision | PENDING |
| TC-SM-005 | Stale or concurrent completion/write is rejected | PENDING |
| TC-SM-006 | CLI JSON/Unicode contract remains portable through the canonical path | PENDING |
| TC-SM-007 | Command routing uses canonical state without a legacy-state ambiguity | PENDING |

The tester must record the exact revision, environment, command or method, execution time, result and retained locator. A test point with no executable interface or no authorized environment remains `NOT_EXECUTED` or `NOT_AVAILABLE`, as applicable. The reviewer must assess only the final implementation and independent evidence, classify findings, and keep the change-slice conclusion separate from the existing full-V1 acceptance result.

The pending-only detailed matrix is [`docs/verification/schema-migration-test-plan.md`](../verification/schema-migration-test-plan.md), registered as `DOC-SCHEMA-MIGRATION-TEST-PLAN-001` v1. It adds TC-SM-008 through TC-SM-013 without redefining TC-SM-001 through TC-SM-007.

## Deferred RTM update

`DOC-RTM-001` remains unchanged in this planning step. It will be revised only after TASK-019 supplies a concrete design that establishes the requirement and design references needed for traceability.
