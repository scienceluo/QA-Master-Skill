# QA Master V1 baseline-audit reconciliation

- Artifact ID: `DOC-BASELINE-001`
- Document State: `DRAFT`
- Evaluation State: `IN_REVIEW`
- Evidence Status: `OBSERVED`
- Source report: `DOC-TEST-BASELINE-001` / `docs/verification/baseline-2026-10-14.md` (Runtime evidence `EVD-BASELINE-20261014-001`)

## What the independent baseline audit established

The audit report records actual local execution against `77e3b5d4e8be8076720ebfd2f0338db73dac2079` using Windows Python 3.13.5 from `D:\codex-rd-platform\.venv\Scripts\python.exe`.

| Evidence | Scope | Observed result | Evidence Status |
|---|---|---|---|
| EV-BASE-001 / EV-BASE-002 | Full local `unittest` regression, verbose and quiet repeat | 301 tests ran; two workflow tests errored. The initial baseline is not clean. | OBSERVED |
| EV-BASE-003 | Side-effect approval guard | 5 targeted tests passed. | OBSERVED |
| EV-BASE-004 | Python module compilation | `compileall` process succeeded. This is syntax evidence only. | OBSERVED |
| EV-BASE-005 | Workflow, side-effect, and exact-approval targeted retest after test correction | 25 targeted tests passed. | OBSERVED |
| EV-BASE-006 / EV-BASE-007 / EV-BASE-010 | Continuation safety, artifact attribution, and typed-receipt persistence checks | 40 targeted tests passed against the observed continuation worktree. Test-only fixtures do not authenticate a human or remote executor. | OBSERVED |
| EV-BASE-008 / EV-BASE-011 | Mutable-worktree continuation local regression | Earlier 375/379-test runs passed with a subprocess warning; they are retained as historical observations. | OBSERVED |
| EV-BASE-009 | Wheel build, clean temporary-venv installation, package-resource and CLI smoke | The observed wheel installed and the bounded smoke checks passed. | OBSERVED |
| EV-BASE-015 | Fixed candidate `18e92b1` strict local regression | 384 tests completed `OK` with `ResourceWarning` promoted to an error; no such warning was emitted. | OBSERVED |
| EV-BASE-016 | Fixed candidate `18e92b1` fresh isolated-wheel smoke | The wheel SHA-256 was `0C0816F2E1D6DF663B912004C06A8EA5DF9822B73A174F667AA2D0FDE73F0364`; bounded import/resource/CLI checks passed. | OBSERVED |
| Reviewer portability re-check | Current `73a86bb` fresh wheel | Independent review records a fresh-wheel ASCII/Chinese JSON round trip with design-only state preserved. | OBSERVED |

EV-BASE-006 through EV-BASE-011 were run against shared continuation worktrees and remain historical observations. EV-BASE-015 and EV-BASE-016 are the current fixed-source local evidence at `18e92b1`; the GitHub branch tree is recorded as equal to its local tree. Neither establishes CI success, external-service validation, release readiness, a Gate decision, or product acceptance.

## Observed defect and disposition

`BUG-001` is an observed stale test-expectation defect in `tests/test_workflow.py`. The initial full suite failed because legacy side-effect completion now deliberately raises `PermissionError`, while two old tests expected or used the prior legacy completion contract. The test correction changed no production implementation and EV-BASE-005 passed the bounded retest.

EV-BASE-015 verifies `BUG-001` for the fixed local source `18e92b1`. This is not a retrospective Runtime defect closure: the original executions were not pre-registered Runtime test cases/executions, and creating such a chain now would fabricate it.

`BUG-002` is verified for `18e92b1` by EV-BASE-015, which promoted `ResourceWarning` to an error and completed successfully. This bounded local-suite disposition does not make a production, load, enterprise, release, or deployment claim.

## Resulting gaps

- `TC-INT-001` and `TC-INT-002`: the continuation report adds mock-level and local redirect checks, but provider-backed GitLab reader/artifact transport integration remains `NOT_EXECUTED`.
- `TC-INT-003`: local runner Windows/recovery integration is `NOT_EXECUTED` because the dedicated disposable-run permit was not part of this audit.
- `TC-E2E-001`: GitLab staging E2E is `NOT_EXECUTED`; no authorized target, account, or token was supplied or accessed.
- Performance, load, stress, reliability, and compatibility evidence remains `NOT_EXECUTED`.

The next verification action is a fresh independent regression if source changes, followed by evidence reclassification from actual results. No Gate is eligible to pass from this audit alone.
