---
id: regression-evidence-reporting
title: Regression impact, defect reporting and evidence review
dimensions: regression
intents: regression, report, design, review
risks: low, medium, high
artifacts: regression-impact-map, defect-report, evidence-report
---
# Regression, defect and evidence reporting

Use this guide to decide what must be rechecked after a bounded change and to make results assessable. It cannot convert a draft, a runner exit code or an unverified external artifact into a pass result.

## Inputs and output contract

Inputs are pinned before/after revisions, changed components and interfaces, approved requirements/cases, known defects, environment/build identity, execution records and artifact hashes. Output is a `regression-impact-map`, a reproducible `defect-report` where a failure is observed, and an `evidence-report` whose result state is `NOT_EXECUTED`, `UNVERIFIED_EXTERNAL_ARTIFACT`, `OBSERVED`, or `VERIFIED` according to actual provenance.

## Method

Trace changed code/configuration/schema/API contracts to direct requirements, callers, consumers, data migration paths and critical journeys. Select smoke, direct-impact and risk-based adjacent cases with a stated reason. A defect report records title, severity rationale, build/environment, exact preconditions, minimal reproduction, expected oracle, observed result, timestamps, logs/screenshots/artifact hashes and duplicates/known limitations. Keep flaky or unavailable results distinct from failures.

## Executable acceptance oracle examples

After a tax calculation change, the impact map includes invoice creation, refund, export and ledger reconciliation. A case oracle can assert that the approved input produces the approved tax total, the persisted invoice and export show the same total, and a rejected invalid rate produces no ledger entry. A defect is reproducible only when the same pinned build and input produce the observed mismatch against that oracle; otherwise record `NEEDS_REPRODUCTION`.

## Missing information

No pinned revision/build, affected interface map, oracle, environment identity or trustworthy artifact yields `IMPACT_UNCONFIRMED`, `ORACLE_MISSING`, `ENVIRONMENT_UNIDENTIFIED` or `EVIDENCE_UNVERIFIED`. Do not close a defect, mark a case PASS, or make release recommendations from those gaps.

## Review checklist

- Does impact include interfaces, data and operational configuration rather than changed files alone?
- Does every reported result cite a case, build, environment and immutable/locatable evidence?
- Are blocked, skipped, flaky, unverified and failed outcomes kept distinct?
- Are defect severity and release risk justified without claiming human acceptance?
