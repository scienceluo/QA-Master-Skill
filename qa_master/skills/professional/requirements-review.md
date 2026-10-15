---
id: requirements-review
title: Requirements, source conflict, and human-baseline review
dimensions: functional, negative
intents: requirements, review, discovery, design
risks: low, medium, high
artifacts: requirement-review-packet, conflict-register, human-baseline-decision
---
# Requirements and source review

Use this guide to turn supplied PRD, UI observations, API documents, issue records and code observations into a review packet. Source code and a running system are evidence of observed behaviour only; neither is an approved business rule.

## Inputs and output contract

Inputs are versioned source references, each with owner, date or commit, scope, and statement; a requested feature boundary; and known risk or regulatory constraints. Output is a `requirement-review-packet` containing atomic candidate requirements, a source-to-statement map, open questions, contradictions, assumed terms, and a `human-baseline-decision` field set to `PENDING` until a named human approves a version.

## Method

Split compound statements into actor, trigger, precondition, behaviour, observable result, failure result and data rule. Compare every candidate against every higher-priority source. Record disagreement as a conflict rather than “resolving” it from plausibility. For code-only discovery, cite commit, path, line and content hash and label the candidate `NEEDS_HUMAN_CONFIRMATION`. Ask reviewers to approve, reject, or restate each candidate; preserve rejected candidates and the reason.

## Executable acceptance oracle examples

For “a finance approver may release an invoice only after two distinct approvals”, an executable oracle is: with one valid approval, release request returns a documented denial and invoice state stays `PENDING`; after two approvals from distinct authorized identities, the documented success response occurs and the audit event includes both identities. “Works as expected” is not an oracle.

## Missing information

If source versions disagree, output `SOURCE_CONFLICT` with both citations. If an owner, state transition, authorization policy, error response, retention rule or success observable is absent, output a named question and mark the candidate `INCOMPLETE`; do not infer it from code or UI.

## Review checklist

- Is every assertion linked to a versioned source or explicitly marked an assumption?
- Are conflicts, obsolete sources and code observations visibly distinct from approved requirements?
- Does every candidate have a measurable positive and relevant failure result?
- Has a human approved a bounded baseline version before formal test-case baselining?
