# TASK-041 developer verification

- Change: CR-011
- Subject commit: `0d712c8902633902cabe07fa0e20a7881b036c8c`
- Developer: `/root`; independent tester and reviewer are separate assignments.
- Requirements: REQ-019–024, NFR-006–008; DES-040 v1 / ADR-005 v1.
- Document State: DRAFT. Evidence: OBSERVED developer checks only.
- Date: 2026-10-15, Windows, local Python via the platform virtual environment.

The additive paired evaluator now provides strict manifest/source validation,
neutral deterministic participant projection, process-free preview/inspection/
grading, an explicit native Codex runner, bounded concurrent capture, distinct
process/termination/output/policy outcomes, append-only evidence, and exact typed
assertions. The legacy submitted-human-ratings benchmark is unchanged.

The CLI uses prompt instructions plus a local response parser. Provider support
for the arbitrary-JSON observation contract as `--output-schema` has not been
verified, so that flag is absent. The native path cannot emit a strict comparison
candidate; private launcher tests are always TEST_DOUBLE/NOT_EXECUTED.

## Observed developer checks

| Check | Actual result | Retained evidence |
|---|---|---|
| `python -X utf8 -W error -m unittest discover -s tests -p test_paired_evaluation.py -v` | 32 passed, 23.181 seconds | `evidence/cr011/developer-focused.txt` |
| `python -X utf8 -W error -m unittest discover -s tests -v` | 542 passed, 44.493 seconds | `evidence/cr011/developer-full-suite.txt` |
| `python -X utf8 -m compileall -q qa_master` | Exit 0 | Host command observation |
| `git diff --check` / staged diff check | Exit 0 | Host command observation |

The process tests launch a real local Python child through an explicitly
intercepted Popen argument list. They exercise pipes, timeout/tree termination,
oversized streams/final staging and cleanup. They do not call a model. The fake
paired fixtures check six scheduled calls, AB/BA order, actual stdin projection,
failure continuation/global stops, integrity, grading and provenance labels.

## Failures and corrections retained

The first expanded 22-test developer run had three errors in the **test harness**:
its Popen interceptor also intercepted Windows `taskkill`, then failed with
`ValueError: '--output-last-message' is not in list`. The interceptor now passes
the OS helper through. The short-lived fixture children exited; an exact-PID
readback found none remaining. The corrected 22-test run passed before further
review-driven tests were added. This was not an observed product timeout failure.

Independent prefreeze review found actual product issues despite early passing
developer tests. Corrections and regression coverage are retained in the subject:

- Nested JSON claim fields are prohibited, including winner/rating/approval.
- Exact stdin write count and failure outcome are captured; incomplete writes
  cannot become a successful process artifact.
- Overflowed streams are withheld, with observed count/hash/EOF/overflow facts;
  a retained prefix is not labelled a complete raw artifact.
- Escaped keys and credential URLs are scanned before retaining JSON/JSONL,
  including malformed or mixed output with bounded escape normalization.
- Inspection cross-checks global/nested ledgers and record files, reparses valid
  outputs, recomputes terminal priority, input bindings and ordered stop causes.
- Unknown assertion scenario/check bindings fail atomically, rather than silently
  producing zero assertion records.
- Joint capacity and sensitive-input failures occur before directory reservation.

The reviewer's prefreeze disposition found no remaining P0/P1/P2 after targeted
rechecks. It is not the formal TASK-043 independent review or a Gate decision.

## Explicit remaining limits

The implementation caps a manifest at 32 scenarios/32 schedule rows (64 calls),
materialized inputs/stdin at 64 MiB, and preflight at 1 MiB, reserving per-attempt
control-record space within the 2 MiB artifact limit. Tests materialize and
inspect the 32-scenario fixture, reject 33 before reservation, and reject the
32-scenario/64-asset long-path combination before creating a directory. These
additional capacities are not in frozen REQ/DES; RISK-015 and related RTM coverage
remain partial pending disposition. They do not constrain the planned six-call
public-development pilot.

`oracle_ref` is an opaque audit locator, not a file resolver. The typed `expected`
in the separate assertion bundle is the executable oracle. An unavailable bundle
fails atomically; a valid assertion without a valid response/check is UNSCORABLE.

Child-written final staging may transiently contain sensitive bytes. Monitoring
is not an OS quota, and deletion is not secure erasure. No read/network isolation,
provider revision attestation, authenticated ledger integrity, human rating,
enterprise execution, product superiority, acceptance or release is established.
TASK-042 independent testing, TASK-043 formal review and TASK-044 actual model
pilot are pending at this developer handoff.
