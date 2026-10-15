# BUG-006/007 addendum: legacy completion downgrade and durable replacement

- Artifact ID: `DOC-BUG-006-ADDENDUM-001`
- Document State: `DRAFT`
- Evidence Status: `OBSERVED`
- Change: `CR-007`

Independent design/review observation: the canonical migration still persisted a legacy step as `DONE` and only projected `NEEDS_REVALIDATION` in queries. This conflicts with the DRAFT DES-019 migration rule that untrusted legacy completions must be persistently downgraded while their source metadata remains available for audit.

BUG-007 is a review-directed durability correction: after POSIX atomic replacement, the state directory also requires `fsync` so the rename is durably recorded. This is a bounded implementation-limit correction, not a new product capability or an execution result.

The currently claimed TASK-023 must not be modified after claim. This addendum records narrow accompanying corrections in its developer output: during legacy migration, persist every old `DONE` completion as `NEEDS_REVALIDATION`, preserve other completion metadata and the complete `legacy_payload`, and fsync the POSIX state directory after atomic replacement. It does not claim a trusted receipt, test verdict, approval, or execution result. A later independent retest must cover both conditions.

This is an open tracker record, not a closed defect, implementation result, test result, Gate decision, or human approval.
