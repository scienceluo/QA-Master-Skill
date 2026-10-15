# TASK-027 developer verification

Date: 2026-10-15. Scope: CR-008 / REQ-008 / DES-026 local job lifecycle core.
Developer: root orchestrator. Independent testing and review remain separate.

The implementation adds strict digest-bound manifests, revision/digest CAS,
pre-I/O UNKNOWN reservations, fresh authorization ports, ordered observations,
non-consuming poll cursors, explicit reconciliation, cancellation, and local
deadline handling. Typed no-new responses do not refresh liveness. Process and
evidence metadata never produce a business verdict.

Executed on the Windows development host:

| Check | Observed result |
| --- | --- |
| `python -m unittest discover -s tests -p test_job_scheduler.py -v` | 21 tests passed, 3.305 seconds |
| First `python -W error -m unittest discover -s tests` | 432 tests; 1 error in existing configuration UI oversized-request test, WinError 10053 |
| `python -W error -m unittest discover -s tests -p test_configuration.py` | 11 passed, 2.603 seconds |
| Second full strict run | 432 passed, 16.467 seconds |
| Full run after further journal validation | 434 tests; same configuration oversized-request error, 17.187 seconds |
| Final focused strict scheduler run | 24 passed, 3.622 seconds |
| `python -m compileall -q qa_master` | Exit 0 |
| `git diff --check` | Exit 0; line-ending warnings only |

The first full-run failure is retained: config_ui rejects an oversized request
before consuming its body, which can race with the Windows HTTP client's send.
Independent read-only inspection found those files unchanged in CR-008. A later
passing run does not prove that pre-existing timing issue fixed.

Scheduler fixtures are synthetic host ports. These tests do not execute a worker,
network request, IAM provider, secret broker, real cancellation, or remote job.
The core is not connected to the planning CLI or local_runner. Capacity,
retention deletion, evidence verification, and organizational authorization are
outside this increment. No project Gate, acceptance, or release conclusion is
established by this developer record.
