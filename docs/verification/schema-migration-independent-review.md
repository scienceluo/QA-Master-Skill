# CR-007 canonical workflow migration independent review

- Artifact ID: `EVD-SCHEMA-MIGRATION-REVIEW-001`
- Task: `TASK-025` / Runtime work `work-b2df5c6460c84543a7fb01b4bf07d36b`
- Reviewer: `/root/workflow_review`
- Reviewed implementation: `1c35b253736f83889b223f03f87bad3389cfffc3`
- Test/evidence commit: `769cb48fa54f27529ed5f4e411ad0409b32d00b7`
- Reviewed at: 2026-10-15T10:51:25+08:00
- Review scope: bounded `CR-007` local canonical-state migration and pause/resume increment
- Evidence status: `OBSERVED`

## Conclusion

`CR-007` is acceptable for this bounded local increment. No unresolved P0, P1 or P2 finding remains in the reviewed source. The implementation now routes the installed CLI through one schema-v2 application service, preserves legacy source privately, denies migrated approval authority, persists pause/resume and pending questions, uses revision-and-digest CAS, and persists migrated completions as `NEEDS_REVALIDATION`.

This is not a full-V1 acceptance, release recommendation, project Gate decision, production-authority verification, remote-execution verification or enterprise E2E result. Those capabilities remain outside this change and retain their existing incomplete or `NOT_EXECUTED` state.

## Findings

### P3 — TC-SM-010 lacks a dedicated independent scope/approval replacement subcase

- Requirement/test: `REQ-006`, `TC-SM-010`.
- Evidence: the focused independent suite directly covers answer-driven invalidation and exact-artifact ancestor drift. The strict full regression also exercises answer invalidation, approval clearing and artifact binding. It does not contain a named independent subcase that replaces an exact scope and a verified-approval record after completion and asserts the entire descendant branch, active receipt/result pointers and retained invalidation history.
- Failure mode: a future regression limited to scope or approval replacement could be less directly diagnosed than answer or artifact drift.
- Impact: minor test-specific coverage gap. The reviewed binding includes scope and approval digests, and no incorrect behavior was observed in current focused or full execution.
- Recommendation: add explicit scope-replacement and approval-replacement subcases to the next independent workflow regression update.

### P3 — POSIX rename durability fault path is not independently executed

- Requirement/risk: local migration recovery and durability.
- Evidence: `qa_master/state_store.py` fsyncs the temporary file, atomically replaces the destination and fsyncs the parent directory on POSIX. The independent retest ran on Windows; it injected failure before replacement and verified exact source/backup recovery, but did not execute the POSIX directory-fsync branch or simulate power loss. Ubuntu CI exercised normal installation and the strict suite, not durability fault injection.
- Failure mode: platform-specific directory-fsync or crash behavior could differ on a supported POSIX filesystem.
- Impact: minor residual evidence gap; current code follows the intended durability sequence, and ordinary Ubuntu CI passed.
- Recommendation: add a POSIX fault-injection test and filesystem/power-loss qualification before making a release-grade durability claim.

## Resolved review findings

The initial `830d231` subject had five material findings. The fixed source and fresh independent retest provide the following observations:

| Finding | Fixed behavior at `1c35b25` | Review disposition |
|---|---|---|
| Status disclosed persisted answer values | `status` retains field/state shape and returns `[stored]` for provided values | Resolved for this subject |
| Pending questions were lost across reload | Questions are part of canonical state, returned by status and refreshed after answers | Resolved for this subject |
| Task contract accepted malformed members | Exact keys, schema version, booleans and stage values are validated | Resolved for this subject |
| Migrated `DONE` could remain active in canonical state | Migrated completed steps persist as `NEEDS_REVALIDATION`; old values remain in private history/payload | Resolved for this subject |
| POSIX rename lacked parent-directory fsync | Parent directory is fsynced after replace on POSIX | Code resolved; independent POSIX fault evidence remains P3 |

## Validation reviewed and executed

- Independent tester evidence at the fixed subject: 13 focused tests passed in 2.375 seconds; 411 strict regression tests passed in 12.252 seconds; compileall and a fresh-wheel installed CLI smoke passed. The smoke retained schema v2 and returned `DENIED_BY_TASK_SCOPE` for execution.
- Reviewer rerun: `D:\codex-rd-platform\.venv\Scripts\python.exe -W error::ResourceWarning -m unittest tests.test_application_independent -q` — 13 tests passed in 2.350 seconds.
- Reviewer syntax check: `D:\codex-rd-platform\.venv\Scripts\python.exe -m compileall -q qa_master` — exit 0.
- Source/evidence separation: `769cb48` changes only the independent test overlay and retest report relative to implementation commit `1c35b25`; production source is unchanged.
- Remote evidence supplied through repository governance: remote source commit `6efd9c22` has the same source tree as local implementation `1c35b25`; push run `38672720033` and PR run `38672722232` passed the configured Ubuntu/Windows and Python 3.10/3.12 matrix. This is ordinary CI evidence, not POSIX crash qualification.
- Historical failure evidence at `830d231` remains retained and is not rewritten as a pass.

## Decision boundary

The bounded `CR-007` change-slice review is **PASS WITH P3 FOLLOW-UP**. This review does not change the repository's full-V1 `FAIL`/incomplete conclusion or any G0–G11 status.
