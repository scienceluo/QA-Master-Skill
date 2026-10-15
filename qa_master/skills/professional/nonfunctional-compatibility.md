---
id: nonfunctional-compatibility-design
title: Performance load stress stability and compatibility design
dimensions: performance, load, stress, stability, compatibility
intents: design, review, regression
risks: medium, high
artifacts: workload-model, nonfunctional-readiness-register, compatibility-matrix
---
# Non-functional and compatibility design

Use this guide to make non-functional tests reproducible and bounded. It never manufactures an SLA or permits a disruptive workload without explicit authorization.

## Inputs and output contract

Inputs are workload business journeys, data shape, concurrency model, arrival pattern, approved SLO/SLA or acceptance threshold, environment capacity, monitoring fields, duration, abort limits, compatibility support policy and risk authorization. Output is a `workload-model`, `nonfunctional-readiness-register` and `compatibility-matrix`, each labelled draft until its threshold and environment are approved.

## Method

Performance measures response/resource behaviour under a declared expected load. Load verifies target operational demand. Stress intentionally exceeds it to find failure mode and must declare safe abort limits. Stability holds a defined load over a defined duration to detect degradation, leaks or accumulating errors. Separate client timing, server timing, queue delay, error rate, saturation and data correctness. Compatibility enumerates supported browser/device/OS/runtime/database/API versions and chooses representative combinations by support tier and change impact.

## Executable acceptance oracle examples

With approved target “200 virtual users, 10-minute ramp, 30-minute hold, p95 checkout latency <= 800 ms, error rate < 0.5%”, an oracle aggregates the hold window and asserts both metrics plus no order duplication. A stability oracle can assert that at an approved load for 24 hours, documented memory-growth and error thresholds are not exceeded and periodic reconciliation finds no ledger mismatch. A compatibility oracle can assert the supported browser/version executes the approved checkout journey with the same observable invoice result.

## Missing information

Without threshold, workload, duration, monitoring, representative data, support policy or authorization, report `SLA_UNCONFIRMED`, `WORKLOAD_MODEL_MISSING`, `OBSERVABILITY_MISSING` or `HIGH_RISK_AUTHORIZATION_REQUIRED`. Do not translate “fast”, “many users” or “all browsers” into numbers.

## Review checklist

- Are performance, load, stress and stability objectives differentiated?
- Are arrival rate, concurrency, data volume, duration and ramp documented?
- Are abort conditions, isolation and monitoring approved before stress/load execution?
- Does the compatibility matrix reflect an actual support policy and recent change risk?
