# QA Master V1 continuation context baseline

- Artifact ID: `DOC-CONTEXT-001`
- Document State: `DRAFT`
- Evaluation State: `IN_REVIEW`
- Evidence Status: `OBSERVED` unless explicitly marked otherwise
- Observed at: 2026-10-14 (Asia/Shanghai)
- Repository baseline: `77e3b5d4e8be8076720ebfd2f0338db73dac2079` on `codex/qa-master-v1-continuation`

## Purpose and project boundary

`BG-001` is to complete QA Master as one original, installable QA product that turns a test request into controlled requirement analysis, test design, execution planning, evidence handling, regression handling, and reporting. This is an existing-repository continuation, not a new greenfield project and not an authorization to execute a customer or company test campaign.

The current V1 work is product development against a local reproducible contract/integration environment. Real enterprise adapter E2E work against Jira, Confluence, SynapseRT, GitLab, remote SSH/WinRM runners, or customer systems is `NOT_EXECUTED`; no credentials, target, or execution authority have been supplied for it.

## Sources and confidence boundaries

| Source | What it establishes | Evidence Status | What it does not establish |
|---|---|---|---|
| Current user direction in this continuation | Product scope, no-execution boundary, need for progressive questions, 13 dimensions, persistence, adapters, runners, defects/regression/report, configuration/install, and fair comparison | `OBSERVED` | Formal stakeholder sign-off, a release decision, or customer acceptance |
| Git baseline `77e3b5d` and current branch history | Existing implementation and documentation history | `OBSERVED` | A current full-suite run, external-service validation, or historical claims not independently rerun |
| Existing README and `docs/V1_ACCEPTANCE.md` | Prior assertions and declared limitations | `INFERRED` | Verified project evidence; their historical test-count claims require fresh independent evidence |
| Local Runtime snapshot | No QA Master project existed in the inspected default Runtime database before this continuation record | `OBSERVED` | That QA Master never existed in another database or host |

## Known product baseline

The repository contains a local Python package with workflow planning, deterministic requirement/case/coverage validators, GitLab read-only and CI-artifact modules, JUnit import, local runner controls, and partial enterprise guardrails. It also records material gaps: genuine LLM semantic analysis, live enterprise integration, remote scheduling, authenticated multi-user authorization, UI configuration, production-grade auditability, end-to-end lifecycle closure, and a fair competitor benchmark.

Source-derived requirements remain candidates until a real human review creates an approved requirement baseline. Code behavior alone is not an oracle.

## Current continuation controls

- The central requirement baseline and RTM are at `docs/03-requirements/requirement-traceability-matrix.md`.
- Gate status is tracked only in `docs/08-project-management/gate-register.md`. No Gate has a `PASS` decision in this continuation baseline.
- Development may continue through traceable generic work records while lifecycle evidence is being reconstructed; this does not assert that the historical project meets strict G0–G11 progression.
- Any material requirement change uses the change register and a new `CR-xxx` record.
- New claims of test execution, review, deployment, acceptance, or superiority require fresh evidence that names the subject version and actual environment.

## Immediate open decision

The current product-development scope does not require a company test target. A future enterprise E2E work item must name an authorized non-production target, dedicated account ownership, permitted operations, data boundary, and execution authority before it starts.
