---
id: functional-api-design
title: Functional state, boundary, API contract, authentication and negative design
dimensions: functional, api, negative
intents: design, review, code_refinement
risks: low, medium, high
artifacts: functional-case-set, api-contract-matrix, auth-negative-matrix
---
# Functional and API design

Use this guide when a requirement needs testable examples before any execution. It designs cases; it neither sends API requests nor creates external cases.

## Inputs and output contract

Inputs are an approved requirement ID and oracle, data domain or state model, API contract/version where relevant, identities and authorization policy, and a declared environment. Output is a `functional-case-set` with trace IDs, data partitions, state transitions, preconditions, exact expected result and `execution: NOT_RUN`; an `api-contract-matrix`; and an `auth-negative-matrix`.

## Method

Partition input domains into valid equivalence classes, invalid classes and boundaries. For an ordered range, include each endpoint, just-inside and just-outside values; never use arbitrary values as a substitute for a declared bound. Build a state-transition table: each allowed transition has a triggering role and effect; each forbidden transition has its denial and invariant. For APIs, compare method, path, parameters, headers, media types, status, response schema, idempotency and error shape to the contract. Exercise authentication absence, invalid credentials, expired credentials, wrong tenant and authorized-but-forbidden roles according to the documented policy.

## Executable acceptance oracle examples

For quantity `1..100`, a test oracle can assert that `1` and `100` create the order, `0` and `101` receive documented validation responses, and no rejected request creates an order. For `POST /orders`, the matrix can assert HTTP `201`, a response body conforming to the declared schema, a nonempty server order ID, and a repeated request with the same idempotency key has the documented single-effect outcome. Expected status alone is insufficient when the contract specifies a body or state effect.

## Missing information

Unknown bounds, response schemas, idempotency rules, privilege matrix or error contracts become `ORACLE_MISSING`, `CONTRACT_MISSING` or `AUTH_POLICY_UNCONFIRMED`. Keep the affected case draft blocked; do not invent a `401` versus `403` distinction or success payload.

## Review checklist

- Does each partition map to a real domain rule and each transition preserve stated invariants?
- Are API versions and request/response contracts pinned to a source?
- Do negative cases prove no unintended state change?
- Are identity, tenant and permission assumptions explicit and safe for the target environment?
