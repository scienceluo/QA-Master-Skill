# Canonical workflow schema migration independent test plan

- Artifact ID: `DOC-SCHEMA-MIGRATION-TEST-PLAN-001`
- Document State: `DRAFT`
- Evaluation State: `NOT_EVALUATED`
- Evidence Status: `PENDING`
- Change: `CR-007`
- Planned test task: `TASK-021` / Runtime work `work-1b1da1470b9244cea7071401ba085189`
- Test role: independent tester; this plan is not implementation evidence or a Gate decision.

## Scope and preconditions

This plan verifies the pending canonical CLI/Campaign/Workflow schema migration and pause/resume slice. The architecture interface, state schema version, migration record format and command surface remain pending the architect's final design. Test cases must be reconciled to that design before execution without weakening their security and compatibility oracles.

The test subject must be a fixed source revision. Each executed row must record the revision, Python version, OS, exact command or method, time, observed output, retained evidence locator and any BUG ID. Until then every case in this document is `NOT_EXECUTED`.

No case authorizes enterprise access, external writes, test execution, a release, human approval, or a Gate decision. Test-only receipt fixtures prove only local control flow.

## Requirement and risk coverage

| Requirement / risk | Test cases |
|---|---|
| REQ-001 persistent project state | TC-SM-001, TC-SM-002, TC-SM-004, TC-SM-005, TC-SM-007, TC-SM-008, TC-SM-010, TC-SM-013 |
| REQ-003 design-only has no execution or writes | TC-SM-001, TC-SM-003, TC-SM-009, TC-SM-010, TC-SM-012 |
| REQ-006 pause/resume, invalidation and stale rejection | TC-SM-004, TC-SM-005, TC-SM-008, TC-SM-011, TC-SM-013 |
| REQ-009 evidence and regression links | TC-SM-005, TC-SM-011, TC-SM-012 |
| REQ-012 reproducible local contract path | TC-SM-001, TC-SM-005, TC-SM-006, TC-SM-007, TC-SM-010, TC-SM-013 |
| NFR-001 no inferred approval or execution | TC-SM-003, TC-SM-009, TC-SM-011, TC-SM-012 |
| NFR-003 no secret leakage | TC-SM-013 |
| NFR-004 explicit authorization and distinguishable planning | TC-SM-003, TC-SM-004, TC-SM-009, TC-SM-012 |

## Test cases

| ID | Objective and method | Expected observable result | Status | Defect |
|---|---|---|---|---|
| TC-SM-001 | Canonical round trip: exercise `init`, `answer`, `plan`, `status` and `check` through one canonical document. | `project`, `known`, `approvals`, `task_contract`, `stages`, `questions` and `no_execution` remain compatible and semantically consistent after reload. | NOT_EXECUTED | — |
| TC-SM-002 | Legacy migration, version compatibility and idempotence: migrate representative Campaign and Workflow states with their recorded answers, approvals, artifacts, questions, history, runs, steps, results, bindings and receipts; load and save twice. | Required data and event order remain readable, the state is never silently replaced with an empty workflow, and a version upgrade occurs at most once. | NOT_EXECUTED | — |
| TC-SM-003 | Migrate and reload a design-only request that also contains legacy version-only approvals. Attempt exact approval, execution and external-write paths. | Execution and external writes stay default-denied; legacy approvals do not become exact authority, receipts or authorization. `check execution` is `DENIED_BY_TASK_SCOPE`. | NOT_EXECUTED | — |
| TC-SM-004 | Pause at requirements, design and side-effect preflight; restart/reload and resume. Repeat pause/resume. | Pause reason, steps, answers, history and revision survive. Resume retains only permitted state and cannot bypass dependencies/approvals or revive invalid results. | NOT_EXECUTED | — |
| TC-SM-005 | From one revision, race two writers that migrate, answer, complete, pause or resume. | A stale or concurrent write/completion is rejected with `StateConflictError` or the final design's equivalent; one complete winner state remains with no temporary file. | NOT_EXECUTED | — |
| TC-SM-006 | Run canonical CLI JSON with Chinese project/prompt values under an ASCII output pipe on supported platforms. | JSON remains parseable and preserves Unicode values without changing planning authority. | NOT_EXECUTED | — |
| TC-SM-007 | Route each CLI command after migration/reload, including legacy Campaign and Workflow inputs. | Every command resolves the same canonical state with no legacy-state ambiguity or split authorization path. | NOT_EXECUTED | — |
| TC-SM-008 | Supply malformed JSON, non-object state, negative/boolean/string revisions, unknown future schema, missing members, conflicting state and unmappable legacy data. | Command fails safely with a remediable error; original bytes and revision remain unchanged. No approval or history is guessed or discarded. | NOT_EXECUTED | — |
| TC-SM-009 | Hash/stat current, legacy and paused state before and after `status` and `check`; invoke `init` on a pre-existing valid path. | Read-only commands do not change bytes, modification time, revision or migration record. Existing state is refused by `init`; only a missing path initializes. | NOT_EXECUTED | — |
| TC-SM-010 | Change a required answer, exact artifact, scope and approval after a completed branch. | Changed branch and descendants lose result/binding/receipt and required approvals; prior history remains with an invalidation event. | NOT_EXECUTED | — |
| TC-SM-011 | Complete an ancestor (`baseline` or `test_plan`), then change/remove/replace its artifact, scope or approval; directly evaluate and complete `execution`, `regression` and `report`. | A stale ancestor is recursively detected: no descendant returns `READY` or retained `DONE`; completion is rejected and the branch becomes invalidated or explicitly stale. | NOT_EXECUTED | — |
| TC-SM-012 | Attempt any side-effecting command while paused, stale, legacy-approved, exact-approval-mismatched or receipt-invalid. | No external call occurs. Invalid/missing typed receipt, binding digest, issuer or evidence reference rejects completion. Synthetic callbacks remain test-only. | NOT_EXECUTED | — |
| TC-SM-013 | Inject a validation or write failure during migration; test state/output with secret-shaped values. | Original state remains recoverable without a half-written/empty replacement, and no secret value is emitted. | NOT_EXECUTED | — |

## Execution evidence and defect handling

Run focused unit/contract cases first, then the strict full local regression with `ResourceWarning` promoted to an error, followed by an installed-package CLI smoke if the implementation changes packaging or command routing. Test failures receive a `BUG-xxx` record with requirement, case, fixed revision, reproduction, expected/actual observations and retained evidence. A passing test requires an executed command or observable method result; unrun tests stay `NOT_EXECUTED`.

Enterprise E2E, remote execution, performance/load/stress, production identity and release validation are outside this change slice and remain `NOT_EXECUTED` unless separately authorized.
