# Canonical workflow schema migration independent retest results

- Proposed artifact ID: `EVD-SCHEMA-MIGRATION-RETEST-001`
- Change: `CR-007`
- Task: `TASK-024` / Runtime work `work-cfc8ca1528ac4cfe918bbb1c1f57b902`
- Tester: `/root/workflow_validation`, independent of the repair implementation
- Implementation subject: `1c35b253736f83889b223f03f87bad3389cfffc3` (`fix(workflow): protect migrated state and restore pending questions`)
- Implementation source fingerprints: `qa_master/application.py` `8D1F0EFEF85BDF8AB3EFEE8E5A118536952FFFED35FEB4CE290300988DF9A477`; `qa_master/state_store.py` `F05D4A8A1B5365E41173476BE7B3D16BD39BF812B71FCF49C2C2C27A8ACF439C`
- Independent test overlay: `tests/test_application_independent.py` SHA-256 `4D4E20C2877AC006EFA5EB9CEB88D1C34788EEC159209A045F37968A91F967A3`; it adds three tester-owned negative/recovery cases after the implementation commit and is the only tracked worktree change at final verification.
- Environment: Windows, Python 3.13.5 from `D:\codex-rd-platform\.venv\Scripts\python.exe`
- Executed at: 2026-10-15T10:48:49+08:00
- Evidence status: `OBSERVED`

## Commands and observations

| Scope | Command / method | Observable result | Status |
|---|---|---|---|
| Directed migration acceptance | `D:\codex-rd-platform\.venv\Scripts\python.exe -W error::ResourceWarning -m unittest tests.test_application_independent -v` | 13 tests in 2.375 s, `OK`. | PASS |
| Full local regression | `D:\codex-rd-platform\.venv\Scripts\python.exe -W error::ResourceWarning -m unittest discover -s tests -q` | 411 tests in 12.252 s, `OK`. | PASS |
| Syntax | `D:\codex-rd-platform\.venv\Scripts\python.exe -m compileall -q qa_master` | Exit code 0. | PASS |
| Installed-package smoke | Build with `C:\Program Files\Python\python.exe -m pip wheel --no-deps --no-build-isolation .`; install wheel with `--no-index --no-deps` into a fresh temporary venv; run installed `python -I -m qa_master`. | Wheel `qa_master_skill-0.1.0-py3-none-any.whl`, SHA-256 `E913A3DD3CD7A07C06C0C235BDB1E8E87B93B5A869D9C007CCB3E211B3A70A76`; installed Python 3.13.5. Chinese `init`, `answer`, design-only `plan`, `pause`, reload, `resume`, then `check execution` completed with `DENIED_BY_TASK_SCOPE`; persisted state had schema 2 and mode `ACTIVE`. | PASS |

The complete focused, regression and wheel-smoke command outputs are retained in this task's command evidence: `45a606`, `406c51` and `5b92a3`.

## Re-tested contract points

| Test cases | Observable result | Status |
|---|---|---|
| TC-SM-001 | Canonical CLI round trip preserved planning-only denial and ASCII JSON Chinese transport. Next material questions survived reload and refreshed to empty after the explicit `requirements=没有` answer. | PASS |
| TC-SM-002 | Legacy Campaign payload and byte-identical backup survived migration; legacy Workflow `DONE` steps persisted as `NEEDS_REVALIDATION`, retained their result references, and never made execution ready. | PASS |
| TC-SM-003 | A migrated design-only contract remained execution/write denied across reload; a legacy approval was recorded only as unverified. | PASS |
| TC-SM-004 | Pause/reload rejected progression without writing, then resume restored active state. | PASS |
| TC-SM-005 | Stale writer CAS and parallel `init` both produced one complete winner with no partial temporary state. | PASS |
| TC-SM-007 to TC-SM-009 | Status/check stayed byte- and mtime-read-only for a legacy document; init did not overwrite it. Invalid contract schema version, stage and extra member were rejected without changing input bytes. | PASS |
| TC-SM-011 | Exact-artifact change recursively made a completed descendant stale. | PASS |
| TC-SM-012/013 | No side-effect path was enabled. Status retained answer field shape/state but redacted provided values, including a token-like marker and URL query. Fault-injected migration write retained original bytes and backup, then recovered. | PASS |

## Defect disposition and limits

The prior independent failure at `830d231` remains recorded in `EVD-SCHEMA-MIGRATION-TEST-001`; it is not overwritten by this retest. The present tests did not reproduce BUG-003 (status disclosure), BUG-004 (question projection), BUG-005 (contract validation), or BUG-006 (legacy `DONE` trust). They establish only this fixed local source and the stated test methods.

The new POSIX parent-directory `fsync` branch (BUG-007) was not executed on this Windows host, so actual POSIX durability behavior remains `NOT_EXECUTED` in this independent retest. No enterprise E2E, remote execution, production identity, performance/load/stress, release, human acceptance or project Gate conclusion follows from these local results; each remains `NOT_EXECUTED` or undecided.
