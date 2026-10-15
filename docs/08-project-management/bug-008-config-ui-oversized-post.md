# BUG-008 — Windows configuration-UI oversized POST can abort the client connection

- Record type: defect record
- Change / task: `CR-009` / `TASK-030`
- Status: `RESOLVED` for the bounded tested contract
- Bounded reproduction disposition: `VERIFIED` at the documented 65,537-byte and header-only contract
- Evidence Status: `VERIFIED`
- Source: independent tester trace reported during the CR-008 continuation, 2026-10-15

## Observation

During two full strict-suite attempts on Windows, an oversized configuration-UI `POST` reproducibly ended with `WinError 10053`. A subsequent 432-test full-suite rerun passed, so the condition is intermittent and remains open. The tester traced the failure to an immediate HTTP 413 response while the client was still sending the request body; the server did not drain the body before closing the connection.

The original exact failing command and retained raw output are not a pre-registered Runtime execution. The bounded fixed source is `a3905d3572ab44b8e7f0f3ca17eae11ec15c6ab1`; independent current-tree observations recorded the stated boundary requests and a strict 457-test regression. This verifies the bounded reproduction, but does not close the Runtime work, establish clean behavior for larger active bodies, or make a release or Gate claim.

## Intended repair and verification boundary

`TASK-030` made the smallest server-side repair that preserves an oversized-request rejection while avoiding the tested client-abort race, and finished on Runtime attempt 2 after its first lease expired. The scheduler CR-008 implementation remains a separate work item. Independent evidence covers the boundary-sized request, header-only request, normal configuration request and strict regression at the current tree. The review preserves a P3 limit: a larger actual body can still observe connection closure after the bounded drain. This resolution does not extend beyond the bounded contract.
