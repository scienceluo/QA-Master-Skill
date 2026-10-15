# Local job scheduler independent test plan

- Artifact ID: `DOC-JOB-SCHEDULER-TEST-PLAN-001`
- Document State: `DRAFT`
- Evaluation State: `NOT_EVALUATED`
- Evidence Status: `PENDING`
- Change: `CR-008`
- Planned task: `TASK-028` / Runtime work `work-11c7092fe12a4e2a8f52ac9cdbbc9621`
- Design input: `DES-026` (DRAFT; ordering clarification pending design registration), SHA-256 `C61E5AA64130E62FE8EEC8982C1D7867F755E15DA2C597569C5C92F3BCBFEA17`
- Test role: independent tester; no case is execution, transport, identity, evidence-verification, release or Gate evidence.

## Scope and execution rules

This plan tests the local persistent job lifecycle and fake-port contracts only. `local_runner`, SSH, WinRM, HTTP, real workers, IAM, secret resolution, evidence verification, retention deletion and enterprise targets are outside the change slice.

All transport, authorization and observation doubles are explicitly `SYNTHETIC`. Their successful calls prove only local state-machine control flow. Each executed case must name the frozen source revision, tester-owned test-file hash, OS/Python environment, exact command or method, time, observed result, retained locator and BUG ID where applicable. A `PASS` requires those observations; all rows below remain `NOT_EXECUTED` until TASK-027 is frozen and TASK-028 is validly claimed.

## Requirement and risk coverage

| Requirement / risk | Test cases |
|---|---|
| REQ-008 authorized scheduling, monitoring and timeout | TC-JS-001, TC-JS-003–009, TC-JS-011–012 |
| REQ-009 execution/evidence/report trace boundary | TC-JS-008–010, TC-JS-013 |
| NFR-001 no inferred authorization, execution or PASS | TC-JS-003–004, TC-JS-008–010 |
| NFR-002 durable provenance and sequence | TC-JS-002, TC-JS-005–007, TC-JS-011–013 |
| NFR-003 no secrets in manifest/journal/events | TC-JS-001–002, TC-JS-013 |
| NFR-004 exact authorization and default-deny side effects | TC-JS-003–006, TC-JS-011 |

## Independent acceptance cases

| ID | Objective and method | Expected observable result | Status | Defect |
|---|---|---|---|---|
| TC-JS-001 | Construct canonical manifests, vary one bound field at a time, and supply missing/extra/oversized/nonfinite/raw-sensitive fields. | Exact v1 field set and canonical digest are deterministic; any drift or invalid field is rejected before persistence. Manifest/journal/event output contains only digests and opaque IDs, never argv, endpoint, proof or secret value. | NOT_EXECUTED | — |
| TC-JS-002 | Prepare the same key/manifest twice, then reuse the key with changed manifest, nonce or digest. Reload repository between calls. | Identical replay is idempotent; drift is rejected; persisted job key index, manifest digest and events remain stable across reload. | NOT_EXECUTED | — |
| TC-JS-003 | Use no ports, each missing port, boolean/malformed authorization, mismatched action/job/manifest/operation, and boundary expiry values. | Missing port or invalid/expired authorization returns the stable denial before transport call or state/revision/event mutation. Only `issued_at <= now < expires_at` is accepted. | NOT_EXECUTED | — |
| TC-JS-004 | Race two dispatch calls from one prepared revision using a counting synthetic transport; inject transport exception, malformed response, verification failure and post-I/O CAS conflict. | At most one transport dispatch occurs. Before I/O, one durable `UNKNOWN / DISPATCH` reservation with stable operation ID exists. Every fault leaves that uncertain state and no automatic retry occurs. | NOT_EXECUTED | — |
| TC-JS-005 | From `UNKNOWN / DISPATCH`, repeat dispatch and restart/reload; reconcile with the same operation ID and phase. Exercise verified authoritative and non-authoritative absence. | Repeated dispatch never calls transport. Reconciliation never redispatches; only authoritative absence changes unknown dispatch to `NOT_DISPATCHED`. A later attempt requires a new job key, nonce and authorization. | NOT_EXECUTED | — |
| TC-JS-006 | Feed observation variants with wrong dispatch ID/manifest, lower sequence, same-sequence altered content, exact last replay, lifecycle skips and a latest-only sequence jump. Include `CANCEL_ACCEPTED` with wrong child cancel ID. Call observe/reconcile first with `after_sequence=-1`, then exactly the persisted last sequence. | Binding, ordering and allowed transition checks fail closed without state advance. Exact replay of only the last accepted observation is idempotent. A sequence gap is reported as `OBSERVATION_GAP` without a local state change. Cancel acceptance requires both dispatch and cancel operation IDs; a pull never consumes a provider cursor. | NOT_EXECUTED | — |
| TC-JS-007 | Advance injected clock exactly to and past execution, heartbeat and cancellation-grace deadlines; reload before each boundary. Set heartbeat and execution deadlines equal and in either order. | At `now >= deadline`, the earliest persisted running deadline controls: heartbeat at or before execution yields `UNKNOWN / RUN` and does not auto-advance to `CANCEL_DUE`; an earlier execution deadline yields `CANCEL_DUE`. Cancellation grace yields `UNKNOWN / CANCEL`. No deadline fabricates process termination, timeout completion, cancellation or a retry. | NOT_EXECUTED | — |
| TC-JS-008 | Request cancellation with missing/stale/mismatched proof, then with a fresh cancel-bound proof. Verify raw cancel response and terminal observation races. | Cancel needs separate unexpired authorization, reserves `UNKNOWN / CANCEL` before I/O, and only verified acknowledgment reaches `CANCEL_REQUESTED`. Grace expiry returns unknown; terminal dispatch-bound process observation may finish the job without rewriting termination reason. | NOT_EXECUTED | — |
| TC-JS-009 | Submit verified terminal process observation variants from active and cancellation states. | Only permitted terminal transitions reach `PROCESS_FINISHED`; process metadata is retained while `business_result` remains `NOT_ASSESSED` and no PASS/FAIL/release state appears. | NOT_EXECUTED | — |
| TC-JS-010 | Submit verified evidence-available observation with exact evidence reference, digest, byte count and contract binding; then attempt evidence-verification/result transitions. | State reaches at most `EVIDENCE_AVAILABLE`; no evidence authentication, business result, report or release conclusion is inferred. | NOT_EXECUTED | — |
| TC-JS-011 | Reconcile each unknown phase after reload. Test unknown-cancel absence, verifier/transport failure and wrong phase/operation. Use a stable synthetic transport that returns one typed next observation or typed no-new result for the same `after_sequence`; race two polls from the same cursor. | Reconcile is accepted only from unknown and uses dispatch operation ID plus uncertainty phase. Unknown cancel absence stays unknown; provider/transport errors remain unknown and never invoke dispatch/cancel again. A concurrent CAS loser does not consume or lose the next observation; the next poll from the persisted sequence can obtain it. | NOT_EXECUTED | — |
| TC-JS-012 | Corrupt journal/schema/index/job record; inject atomic replacement failure and simultaneous repository writes. Exercise empty-store revision 0, returned prepare store revision and cross-job CAS. | Load/mutation fails closed without overwriting bad/original bytes. CAS yields one winner, no partial journal/temp file and no transport call after failed persistence. A snapshot exposes both job and store revisions; prepare returns the persisted store revision for a subsequent different-job CAS. | NOT_EXECUTED | — |
| TC-JS-013 | Inspect persisted snapshots/events/errors after every synthetic path, including raw response and proof-shaped inputs. | Records contain IDs, state, sequence and safe digests only; they omit raw command, endpoint, transport response, proof, credential and presigned URL. | NOT_EXECUTED | — |

## Evidence and defect policy

Focused independent tests will be placed only in `tests/test_job_scheduler_independent.py`. Results will be recorded in `docs/verification/job-scheduler-test-results.md`; the prior state stays intact. Defects receive the next available `BUG-xxx` IDs with requirement, test case, fixed subject, reproduction, expected/actual result and evidence locator.

The end-to-end/production categories for this slice — remote transport, worker scheduling, credentials, real cancellation, evidence retention, deployment, performance/load/stress and enterprise validation — remain `NOT_EXECUTED` unless separately authorized.
