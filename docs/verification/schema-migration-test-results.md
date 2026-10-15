# Canonical workflow schema migration independent test results

- Artifact ID: `EVD-SCHEMA-MIGRATION-TEST-001`
- Change: `CR-007`
- Task: `TASK-021` / Runtime work `work-1b1da1470b9244cea7071401ba085189`
- Tester: `/root/workflow_validation` (independent of `TASK-020` implementation)
- Subject: `830d2317310a2526624f40088dc227327e156961` (`feat(workflow): unify CLI state with safe legacy migration`)
- Subject source fingerprint: `qa_master/application.py` SHA-256 `1c8907ff990473f3663d58f70382e32d3d8aa027344be5d5a40175cd93ec110c` at that commit
- Environment: Windows, Python 3.13.5 from `D:\codex-rd-platform\.venv\Scripts\python.exe`
- Executed at: 2026-10-15T10:41:51+08:00 (first independent run completed before remediation edits were started)
- Evidence status: `OBSERVED`
- Result: `FAIL` — 5 of 10 independent tests passed; 1 errored and 4 failed.

## Scope and command

The tester added only `tests/test_application_independent.py`. It covers the CR-007 migration contract separately from implementation-owned tests. No enterprise connection, remote execution, external write, release action or human approval occurred.

```text
D:\codex-rd-platform\.venv\Scripts\python.exe -W error::ResourceWarning -m unittest tests.test_application_independent -v
```

The command ran 10 tests in 1.625 seconds and exited 1. The complete console result is retained in this task's command evidence (`chunk 8f6653`). The test file is the reproducible locator for each case below.

## Observed results

| Test case | Observable result | Status | Linked defect |
|---|---|---|---|
| TC-SM-001 canonical CLI round trip and ASCII JSON | Passed. `init`/`answer`/`plan`/`status` retained planning-only authority and Chinese project data through parseable JSON. | PASS | — |
| TC-SM-002 legacy Campaign migration and backup | Passed. Read-only projection left legacy bytes intact; first mutation wrote one byte-identical backup and v2 state; reload did not create another backup. | PASS | — |
| TC-SM-003 default-deny after legacy migration | Passed. Design-only contract retained denial after reload; legacy approval returned `RECORDED_UNVERIFIED` and did not authorize execution. | PASS | — |
| TC-SM-004 pause/reload/resume | Passed. Paused state rejected answer, plan and approval without changing bytes; resume restored active state. | PASS | — |
| TC-SM-005 CAS | Passed. A stale service mutation raised `StateConflictError`; winner state was complete and no temporary state file remained. | PASS | — |
| TC-SM-007/009 canonical routing and read-only CLI | Passed. `status` and `check` did not change legacy bytes or modification time; `init` refused an existing legacy file. | PASS | — |
| TC-SM-001 next material questions across reload | `status()` lacks the `questions` projection after a successful plan; access raised `KeyError`. An answered requirement therefore has no observable refreshed question set through status. | FAIL | BUG-004 |
| TC-SM-008 malformed task contract | A v2 document with string `schema_version`, an unknown stage, or an extra contract member loaded without `ValueError`; each negative subcase failed. | FAIL | BUG-005 |
| TC-SM-013 legacy sensitive data projection | `status` printed the test marker stored in legacy `known.token`, `known.gitlab` URL query and derived `known.source`. | FAIL | BUG-003 |
| TC-SM-011 recursive exact-ancestor invalidation | Passed. Changing a completed ancestor artifact made the completed descendant stale and reset its status. | PASS | — |

## Defects filed from this execution

### BUG-003 — Status renders migrated historical answer values

- Requirement: `NFR-003`; test case `TC-SM-013`.
- Reproduction: migrate a legacy Campaign with a `PROVIDED` answer containing a marker, then run `python -m qa_master --state legacy.json status`.
- Expected: status retains the answer field shape and state but does not render raw historical answer values, including values carried into derived `source`.
- Actual: marker was emitted three times in JSON (`token`, `gitlab`, `source`).
- Severity: High, because a status call can disclose a historical token-like value or URL query value.

### BUG-004 — Canonical status omits persisted next-question projection

- Requirement: `REQ-002`; test case `TC-SM-001` question persistence subcase.
- Reproduction: initialize, answer `gitlab`, plan a design-only request, reload, then inspect status.
- Expected: the same next material questions are observable after reload, and answering a question refreshes that projection.
- Actual: `status()` has no `questions` key; independent test raised `KeyError`.
- Severity: Medium, because the canonical CLI cannot show that it retains or refreshes question state after restart.

### BUG-005 — Canonical task contract accepts malformed or unrecognized content

- Requirement: `NFR-004`; test case `TC-SM-008`.
- Reproduction: modify a v2 document's `task_contract` to use a string schema version, unknown stage, or unexpected member, then load it.
- Expected: validation rejects each document and leaves its bytes unchanged.
- Actual: all three malformed contracts loaded successfully.
- Severity: High, because the canonical routing and scope contract is accepted without the declared schema boundary.

## Conclusion and remaining boundary

`830d231` provides observable local evidence for migration backup/CAS, default denial, pause/resume, read-only commands and recursive stale handling. It fails this independent acceptance slice because BUG-003 through BUG-005 remain reproducible. A later fix must use a new fixed revision and a separately registered independent retest; it cannot reuse this failure result as a pass.

This evidence does not change the full V1 evaluation: enterprise E2E, remote execution, production authority, performance/load/stress, release and acceptance remain `NOT_EXECUTED`.
