---
id: security-recovery-design
title: Authorized security proof and recovery design
dimensions: security, recovery
intents: design, review, regression
risks: high
artifacts: security-proof-plan, recovery-drill-plan, authorization-record
---
# Security and recovery design

Use this guide only within an explicit authorized target and scope. A design, tool output or successful request is not evidence that a system is secure or recoverable.

## Inputs and output contract

Inputs are written authorization, target/environment, accounts, allowed methods, data classification, time window, stop conditions, security requirements or threat scenarios, backup/restore objectives, dependency map and recovery owner. Output is a `security-proof-plan` or `recovery-drill-plan` with proof level, exact scope, reversible steps, evidence to collect, abort conditions and `authorization-record` reference.

## Method

Choose the least invasive proof level that tests the claim: configuration/document review; authenticated functional authorization check; controlled negative authorization attempt; approved intrusive validation. Keep production excluded unless authorization explicitly includes it. For recovery, define fault class, restore point, recovery-time and recovery-point objectives, dependencies, reconciliation checks and rollback to the pre-drill state. Do not test destructive scenarios until the operator and recovery route are available.

## Executable acceptance oracle examples

An authorization oracle for “viewer cannot export PII” asserts that an authenticated viewer receives the documented denial, no export artifact is created, and an audit event contains the attempt without leaking PII. A restore oracle asserts that restoring the approved backup to an isolated environment returns the specified dataset point, application health checks pass, and a reconciliation query matches the documented control total; elapsed recovery time is compared only to an approved RTO.

## Missing information

No authorization, target boundary, allowed method, test account, stop condition, recovery owner, backup identity, RPO/RTO or reconciliation oracle results in `AUTHORIZATION_MISSING`, `RECOVERY_OBJECTIVE_UNCONFIRMED` or equivalent blocking gap. Do not probe credentials, exfiltrate data, exploit vulnerabilities or simulate deletion to fill gaps.

## Review checklist

- Is the requested proof level necessary and explicitly approved?
- Are data handling, accounts, time window, abort and incident contacts recorded?
- Does each finding distinguish observation, reproduction and impact proof?
- Can the drill be reversed and validated by an independent reconciliation oracle?
