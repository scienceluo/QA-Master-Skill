# CR-008 local scheduler and BUG-008 bounded repair independent review

- Artifact ID: `DOC-JOB-SCHEDULER-INDEPENDENT-REVIEW-001`
- Evidence ID: `EVD-JOB-SCHEDULER-REVIEW-001` (registration pending at authoring time)
- Task: `TASK-029` / Runtime work `work-38ddd716a6444c1d89e351f92386ac61`
- Reviewer: `/root/workflow_review`
- Reviewed scheduler subject: `79d8ce4076807dd05eea87fe3e36bc171e873365`
- Reviewed configuration repair: `a3905d3572ab44b8e7f0f3ca17eae11ec15c6ab1`
- Independent source/test published snapshot: `5c0bfea25340f792334dfabe0b1ae80868737678` (remote `7eb8025`)
- Corrected independent test report: `def09b05ed49d300f48e54012413fc41ba6f7bbc`, SHA-256 `470A8517E451DFEB680EC5FC6C7CFB3625E9693F7791553421C6D71AA63FF07B`
- Supporting documentation commits: `d464f68`, `3f83e9b`
- Reviewed at: 2026-10-15T11:35:00+08:00
- Document State: `DRAFT`
- Evaluation State: `DECIDED`
- Evidence Status: `OBSERVED`

## Conclusion

The bounded local CR-008 scheduler increment and the bounded BUG-008 configuration-UI repair are acceptable at the reviewed subjects. No unresolved P0, P1 or P2 finding remains. The scheduler persists `UNKNOWN` before irreversible dispatch/cancel calls, admits only one CAS winner, never automatically retries an uncertain operation, uses a stable non-consuming observation cursor, keeps timeout/cancel states separate from process completion, and stops evidence state at `EVIDENCE_AVAILABLE` with `business_result: NOT_ASSESSED`.

The configuration repair drains at most 65,537 bytes for at most 0.25 seconds, returns HTTP 413, and closes the connection. The independent regression observed both a complete 65,537-byte body and a 1 MiB header-only request returning 413, while normal configuration save/readback remained successful.

This conclusion is limited to the local core, synthetic ports and loopback HTTP repair. It is not full REQ-008 acceptance, a real worker/transport/IAM result, evidence authentication, performance qualification, release recommendation, human acceptance or a G8/G0–G11 Gate decision.

## Findings

### P3 — Journal capacity limits are not performance-qualified

- Evidence: every scheduler mutation loads, parses and strictly validates the complete JSON journal, then serializes, fsyncs and atomically replaces it. The design caps the journal at 1,000 jobs, 50 MB and 10,000 events per job, but the independent execution did not measure latency or contention near those limits.
- Impact: acceptable for this bounded single-host correctness increment; operational latency at the documented upper bounds is unknown.
- Recommendation: benchmark representative and near-limit journals before claiming production capacity, throughput or scheduling latency.

### P3 — BUG-008 repair intentionally cannot guarantee clean client behavior beyond the drain bound

- Evidence: the server consumes at most 65,537 bytes before replying and closing. The boundary-sized complete body and header-only oversized request passed. The repair documentation correctly states that a client sending a larger actual body may observe connection closure after the bounded drain.
- Impact: the observed Windows race is resolved for the tested boundary contract without allowing an unbounded read or slow-client hang. Arbitrarily large in-flight uploads are outside the guarantee.
- Recommendation: keep the bounded contract in user/operator documentation; use a reverse proxy or protocol-level early-rejection strategy if a future requirement demands clean handling of much larger active uploads.

## Resolved review observations

Pre-freeze review found material ambiguities or defects that were corrected before the frozen scheduler subject:

| Area | Reviewed resolution |
|---|---|
| Dispatch/cancel operation binding | Worker observations bind the dispatch operation; cancel acceptance also binds the child cancel operation. Authoritative absence terminates only unknown dispatch. |
| Time and ordering | Authorization uses `issued_at <= now < expires_at`; persisted local anchors control deadlines; the earlier running deadline wins and heartbeat wins a tie. Remote `observed_at` is audit-only. |
| Direct response and replay | Dispatch/cancel responses require verification plus reserved-revision CAS. Only the exact last observation is replay-idempotent; stale, drifted and skipped sequences fail closed. |
| Poll cursor concurrency | `observe` and `reconcile` pass `after_sequence`; typed `NoNewObservation` is non-consuming and cannot refresh liveness or create worker facts. |
| Snapshot CAS usability | Snapshots expose job and store revisions, allowing a subsequent distinct prepare without reading repository internals. |
| Journal integrity | Exact nested schemas, authorization bindings, event history, observation kinds and reachable uncertainty-phase combinations are validated before use. Corrupt bytes are not replaced. |
| Result/evidence separation | Process exit, including zero, cannot create PASS/FAIL. Evidence can reach only `EVIDENCE_AVAILABLE`; no verifier or release state is present. |

## Validation reviewed and executed

- Independent evidence `EVD-JOB-SCHEDULER-TEST-002 v1` fixed the primary scheduler subject at `79d8ce4`: 21/21 focused synthetic acceptance tests passed, including post-I/O CAS conflict and distinct-prepare concurrency; compileall passed.
- The independent current-tree regression passed 457/457 with `ResourceWarning` treated as errors. A fresh wheel imported the scheduler, prepared/reloaded a job and returned `PORT_UNAVAILABLE` for default-port dispatch. The installed CLI retained `DENIED_BY_TASK_SCOPE` for execution.
- The independent configuration regression passed 12/12 on `a3905d3`, covering complete 65,537-byte rejection, bounded header-only rejection, normal save/readback and the strict full suite. The earlier `WinError 10053` remains preserved as historical failure evidence.
- Reviewer rerun: `D:\codex-rd-platform\.venv\Scripts\python.exe -W error::ResourceWarning -m unittest -q tests.test_job_scheduler_independent` — 21 tests passed in 3.348 seconds.
- Reviewer rerun: `D:\codex-rd-platform\.venv\Scripts\python.exe -W error::ResourceWarning -m unittest -q tests.test_configuration` — 12 tests passed in 3.160 seconds.
- Reviewer syntax check: `D:\codex-rd-platform\.venv\Scripts\python.exe -m compileall -q qa_master tests` — exit 0.

## Decision boundary

The reviewed change slice is **PASS WITH P3 FOLLOW-UP**. Remote transport, real worker execution, production identity/authorization, actual cancellation, evidence retention/verification, browser/enterprise integration, performance/load/stress, release and human acceptance remain `NOT_EXECUTED` or outside this increment. The repository's full-V1 incomplete/FAIL conclusion and all project Gate statuses remain unchanged.
