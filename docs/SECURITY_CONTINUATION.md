# TASK-009: integration and evidence controls

Date: 2026-10-14. State: DRAFT. Requirements: REQ-003, REQ-006, NFR-001, NFR-003, NFR-004.

The baseline independent review found credential forwarding on redirects, default write permission in design-only intent, caller-asserted release evidence, self-authorized workflow completion, mutable execution targets, and truthy string API approval flags. These are product defects, not requests to operate enterprise systems.

Acceptance contract:

- Authenticated HTTP reads never follow redirects. Size limits apply while reading.
- Planning never grants execution or external-write capabilities. The CLI persists the task contract and denies an execution check for a design-only task, including after restart.
- Release assessment requires a host evidence verifier and governance verifier. The latter checks the complete release scope, including case approvals and defect inventory, and separately checks skip waivers and defect closures. Missing, failing or exception-raising verification blocks assessment; a JSON `source_authenticated` flag is insufficient. External XML remains untrusted.
- A side-effect workflow completion requires a trusted host receipt verifier bound to current project, step, result, input artifacts, scopes, answers and approval records. It must return `VerifiedCompletionReceipt`, with a receipt ID, issuer, issuance/expiry timestamps, exact binding digest and evidence reference. The host verifies authenticity and temporal validity; the workflow verifies the digest/reference and persists the non-secret metadata in the step and event. A boolean return is rejected. Changing a required answer invalidates that step and descendants.
- API generation requires actual boolean approval values. Its generated pytest fixture is an accidental-use guard; the trusted host must authorize the exact command before starting pytest. Workspace code can replace fixtures, so this is not a hostile-code security boundary. Environment flags alone cannot authorize execution.
- Exact workflow completion stores artifact, scope, input and approval digests. Re-evaluating a completed step with different content invalidates it and returns `STALE`.
- SynapseRT dry-run scope uses canonical structured JSON including the assignee. Caller scope assertions never claim authenticated approval.

The verifier callbacks are trusted host extension points, not authentication services. A caller able to replace Python code or supply a malicious verifier is outside this process boundary. No default verifier grants authority. This increment does not deliver a multi-user identity provider, OS sandbox, remote runner or automatic enterprise deployment.

Independent regression and review results are recorded under `docs/verification/`. Historical green claims in earlier documents do not apply to the current working tree.
