# Local job scheduler independent test results

- Artifact ID: `DOC-JOB-SCHEDULER-TEST-RESULTS-001`
- Document State: `DRAFT`
- Evaluation State: `DECIDED`
- Evidence Status: `VERIFIED`
- Change / task: `CR-008` / `TASK-028` (`work-11c7092fe12a4e2a8f52ac9cdbbc9621`)
- Primary implementation subject: `79d8ce4076807dd05eea87fe3e36bc171e873365` (`CODE-JOB-SCHEDULER-CORE-001 v1`)
- Test-plan input: `DOC-JOB-SCHEDULER-TEST-PLAN-001 v3`, SHA-256 `FBC8E0C340939B5E204BBE0D30998248874ADBA0B69BF8C70C61C7F92BA5FEB8`
- Tester-owned overlay: `tests/test_job_scheduler_independent.py`, SHA-256 `5EC5BFBD70AAD7E208BBEE0BB56CE1C13F168EE8039349B0DDE61F5F54B3CB84`
- Environment: Windows NT 10.0.26200.0, CPython 3.13.5, local synthetic ports only.
- Execution window: 2026-10-15 11:22–11:27 +08:00.

## Results

| Test plan ID | Observed result | Status | Evidence locator |
|---|---|---|---|
| TC-JS-001 | Canonical digest is stable; extra/sensitive-shaped, invalid digest, boolean nonce and URL target input were rejected. | PASS | `test_tc_js_001_canonical_manifest_rejects_drift_and_sensitive_shape` |
| TC-JS-002 | Same manifest/key replay stayed idempotent; digest drift was rejected; returned store revision prepared a distinct job and reloaded correctly. | PASS | `test_tc_js_002_prepare_is_idempotent_and_store_revision_is_usable` |
| TC-JS-003 | Missing each required port, invalid proof and expired authorization denied before dispatch or journal mutation. | PASS | `test_tc_js_003_*` |
| TC-JS-004 | Lost dispatch response, verifier-rejected direct response and injected post-I/O CAS conflict preserved `UNKNOWN / DISPATCH`; repeat dispatch did not call transport again and raw values were absent from journal. | PASS | `test_tc_js_004_*` |
| TC-JS-005 | Two dispatches at one revision produced one transport call and one CAS conflict. | PASS | `test_tc_js_005_concurrent_dispatch_has_one_irreversible_call` |
| TC-JS-006 | Stored sequence cursor, typed no-new, exact replay, binding drift, stale sequence, same-sequence drift and sequence gap all failed closed or were idempotent as specified. | PASS | `test_tc_js_006_*` |
| TC-JS-007 | At `now >= deadline`, heartbeat first and equal deadlines entered `UNKNOWN / RUN`; execution first entered `CANCEL_DUE`; no process result was fabricated. | PASS | `test_tc_js_007_timeout_boundaries_do_not_fabricate_process_results` |
| TC-JS-008 | Cancel acknowledgement stopped at `CANCEL_REQUESTED`; grace became `UNKNOWN / CANCEL`; wrong cancel binding stayed unknown; terminal process observation could resolve the cancel race. | PASS | `test_tc_js_008_*` |
| TC-JS-009 | A zero-exit terminal process recorded `PROCESS_FINISHED` while business result remained `NOT_ASSESSED`. | PASS | `test_tc_js_009_process_finish_never_becomes_business_pass` |
| TC-JS-010 | Exact evidence metadata reached only `EVIDENCE_AVAILABLE`; no business/release conclusion was created. | PASS | `test_tc_js_010_evidence_stops_at_available` |
| TC-JS-011 | Authoritative dispatch absence reached `NOT_DISPATCHED`; unknown-cancel absence remained unknown and no redispatch occurred. | PASS | `test_tc_js_011_*` |
| TC-JS-012 | Atomic replacement failure and malformed/index-corrupt journals retained original bytes and made no transport call; two distinct prepare calls at one store revision had one winner and a valid index/job journal. | PASS | `test_tc_js_012_*` |
| TC-JS-013 | Proof, cancel reason and verifier-rejected raw cancel payload markers were absent from persisted journal. | PASS | `test_tc_js_013_journal_redacts_proof_reason_and_transport_exception` |

Command: `python -m unittest -v tests.test_job_scheduler_independent` completed 21 tests with `OK` in 3.179 seconds. `python -m compileall -q qa_master tests` completed without diagnostics. These calls and their complete console output are retained in the TASK-028 command evidence.

The primary-subject focused verdict is **PASS for executed coverage**. No scheduler `BUG-xxx` was found by this execution. This is not a remote worker, transport, identity, evidence-verification, performance/load, deployment, release or business-result claim.

## Separate regression and configuration observations

The following observations are outside the primary scheduler subject and do not alter its result:

- The current tree was `3f83e9b2426b426ed33c707a0b12a4ac65ce4752`; its functional source includes the separate configuration repair `a3905d3572ab44b8e7f0f3ca17eae11ec15c6ab1` and only documentation afterward.
- A fresh wheel, SHA-256 `BE22FB3E5DBF6D62FD0EC1C57805BD01A15000016D41C4D94974C614BF2507BA`, was built and installed in a temporary virtual environment. Installed `qa-master` accepted Chinese `init`, `answer`, `plan`, `pause`, reload/status, `resume` and returned `DENIED_BY_TASK_SCOPE` for `check execution`; no external target was contacted.
- The installed wheel also imported `qa_master.job_scheduler`; its temporary-journal smoke prepared and reloaded a job, then verified default-port dispatch denial as `PORT_UNAVAILABLE`.
- `python -m unittest -v tests.test_configuration` passed 12/12 in 3.139 seconds, including complete 65,537-byte POST returning 413, 1 MiB header-only/incomplete POST bounded to 413, and normal configuration POST/readback.
- Final `python -W error::ResourceWarning -m unittest discover -s tests -v` passed 457/457 in 19.654 seconds on the current tree. This includes the tester overlay but is a regression observation on `3f83e9b`, not a claim that `79d8ce4` contained the overlay or BUG-008 repair.

Earlier in this change, a full-suite run reported by the parent failed at the old oversized-POST test with Windows `WinError 10053` while awaiting the expected 413. That report is recorded as prior, non-pass context only; it is superseded for the separate BUG-008 repair by the independent 12/12 and 457/457 observations above. No claim is made for oversized actual bodies beyond the bounded-drain test contract.

Remote transport, real worker execution, credentials/IAM, actual cancellation, evidence retention/verification, browser/enterprise integration, performance/load/stress and production validation remain `NOT_EXECUTED`.
