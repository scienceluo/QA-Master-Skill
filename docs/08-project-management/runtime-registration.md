# QA Master V1 Runtime registration

- Artifact ID: `DOC-RUNTIME-001`
- Document State: `DRAFT`
- Evaluation State: `IN_REVIEW`
- Recorded at: 2026-10-14 (Asia/Shanghai)
- Evidence Status: `OBSERVED`

## Project context

The default local Runtime was inspected before registration and contained no project named QA Master or QA-Master. The existing repository continuation is now represented by the following actual Runtime project; it is not a new-project `orchestrate-start` bootstrap and it makes no Gate decision.

| Runtime project ID | Name | Repository root | Lifecycle mode/state |
|---|---|---|---|
| `project-ac886d8fddd7483d9e706ddadf20b23c` | QA Master V1 continuation | `D:\QA-Master-Skill` | `active` / `ACTIVE` |

## Actual registered host identities

| Agent ID | Runtime role | Recorded status | Scope |
|---|---|---|---|
| `/root/governance` | documentation_manager | AVAILABLE | Continuation documentation and traceability records |
| `/root/qa_baseline` | tester | AVAILABLE | Current independent baseline audit |
| `/root/gap_review` | reviewer | AVAILABLE | Current independent gap and risk review |

Registration proves only that the identities and roles were accepted by the local Runtime. It is not an assignment claim, test result, review conclusion, or independent confirmation of a host process.

## Generic V3 continuation work

| Work ID | Required role | Gate association | Runtime status | Intended output |
|---|---|---|---|---|
| `work-01ccf93f0af74460ad8472047cace2d5` | tester | G7 | READY | Independent local-baseline audit document |
| `work-94d26e54a4c44a3d9f211363578bef5e` | reviewer | G8 | READY | Independent gap/risk review document |

Both work orders are unclaimed (`READY`) at this registration snapshot. The host tasks are already under way, but a Runtime claim may only be reported after the corresponding host identity claims it. Neither work order is strict-policy bootstrap work and neither can advance a Gate by itself.

## Subsequent registration contract

1. Register the actual host agent with its exact lifecycle role before assignment.
2. Persist the task or design artifact in Git, then register its current version in Runtime.
3. Create `work` using typed, versioned input references, dependencies, and an output contract. Do not record or expose a claim lease token.
4. The assigned host claims the work itself. Record heartbeats and finish it only with actual output references.
5. Register test/review evidence separately against the exact subject version. Gate assessment and an independent decision remain separate operations.
