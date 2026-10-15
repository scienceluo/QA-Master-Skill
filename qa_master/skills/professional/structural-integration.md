---
id: structural-integration-design
title: White-box branch path and integration contract design
dimensions: whitebox, integration
intents: code_refinement, design, review
risks: medium, high
artifacts: structural-candidate-register, integration-contract-map
---
# Structural and integration design

Use static source observations to create reviewable candidates and use interface ownership to design integration checks. Static analysis is not a coverage measurement or proof that current implementation is correct.

## Inputs and output contract

Inputs are a pinned source revision, source paths or control-flow observation, interface contracts, producer/consumer owners, dependencies, timeout/retry policy and test doubles permitted by the team. Output is a `structural-candidate-register` with source hashes and `NEEDS_SPECIFICATION` status, plus an `integration-contract-map` listing interaction, correlation data, expected side effect, rollback/compensation and evidence source.

## Method

For each branch, ask what business condition it represents and derive true/false cases only after an approved oracle exists. For compound predicates, document relevant condition combinations and choose decision/condition evidence appropriate to risk; do not claim MC/DC from a source scan. For integration, trace request ownership and correlation IDs through producer, consumer, persistence and async delivery. Design normal delivery, contract mismatch, dependency timeout, retry exhaustion, duplicate message, out-of-order event and partial side-effect scenarios where the interface semantics make them applicable.

## Executable acceptance oracle examples

For `if account.active and amount <= limit`, an oracle can state: active account at limit is accepted and emits one debit; inactive account or amount over limit is denied and leaves balance/event stream unchanged. For an order-to-inventory event, a duplicate event with the same event ID must produce the documented idempotent result and not reserve stock twice; an inventory timeout must expose the documented pending/failed order state and correlation ID.

## Missing information

Absent business mapping, source revision, contract version, retry ownership, delivery guarantee or state invariant yields a gap such as `BRANCH_SEMANTICS_UNCONFIRMED` or `INTEGRATION_CONTRACT_MISSING`. Do not infer expected behaviour from current exception handling.

## Review checklist

- Are source candidates clearly separated from approved requirements?
- Are paths selected by risk and meaningful decisions rather than line count?
- Does each integration case state data ownership, timing and observable effect?
- Are external side effects and compensations safe in the selected environment?
