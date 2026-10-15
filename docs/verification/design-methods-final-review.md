# TASK-037 independent review of structured test-design methods

- Artifact ID: `DOC-DESIGN-METHODS-FINAL-REVIEW-001`
- Proposed Evidence ID: `EVD-DESIGN-METHODS-REVIEW-001`
- Change: `CR-010`
- Reviewer: `/root/workflow_review`
- Runtime work: `work-481237bfe22f440da3d6a9dc135911db`
- Review result: `PASS WITH P3 FOLLOW-UP`
- Finding counts: `P0=0`, `P1=0`, `P2=0`, `P3=2`
- Document State: `DRAFT`
- Evidence Status: `OBSERVED`
- Date: 2026-10-15

This is the formal independent review of the bounded CR-010 change slice. It
does not decide a project Gate, accept the full V1 product, approve release,
authorize test execution or external writes, or establish superiority over an
external skill or product.

## Frozen review subject

| Subject | Revision / SHA-256 |
|---|---|
| Method engine | commit `e619c79877eb64466c51ffc09d1a6d2e9a9b444b`; `qa_master/design_methods.py` `63F12C1B36BB0F9DA2B8F13D1CFF687DD2CAC9DEBE1A71C963B5BDCE5378EE93` |
| Campaign CLI integration | commit `8e6ab51`; `qa_master/campaign_cli.py` `3D6DA1E1FC0F4B2EA5E0A54E42D4779F0BD7C0BC1EDFD5DF675605FF3E94A2CF` |
| Requirements | v4 `5638A3700F072BFFE5A58C212348966A263D60CDDBA17888314E22C1EBB4E99F` |
| DES-033 | v2 `F823304B68151A3127B0A4F0BC1F5479A69F7FE6A9664C95B328EB0449232CCC` |
| ADR-004 | v1 `EF5350AF611E618172D1EF5CEAFB8ECEF03366073C7CDAA26204AFE5E275639F` |
| Independent test | `tests/test_design_methods_independent.py` `F250D0AA75AB5BD74E4F8570A6DF13587E036EA76D7D53952D1D12AFDD831F2B` |
| Independent report | `docs/verification/design-methods-independent.md` `E425C2094C29FA737C4FB273B2D0F669D3B0A852BFC5FD6ADB21243CE28ECCDA` |

The registered independent input is
`EVD-DESIGN-METHODS-INDEPENDENT-001` v1. The earlier prefreeze findings and
failed-test history remain in separate versioned artifacts; this report does
not erase or reinterpret them.

## Findings

### P3 — DES-033 gives conflicting schema direction for reachability basis

The state-transition prose says reachability is reported with
`reachability_basis: STRUCTURAL_ONLY`, while the exact state `analysis` key
list excludes that field. The implementation follows the exact key list and
implements the specified structural BFS behavior. Adding the field in an
unspecified candidate or obligation location would change identities without a
defined schema.

Recommended follow-up: make a controlled DES/ADR revision that either removes
the prose field reference or adds it explicitly to the exact analysis schema.
No source change is required for this CR-010 verdict.

### P3 — Integer boundary output representation is not explicit

DES-033 strictly defines integer input as a JSON integer and decimal output as
canonical text, but it does not state whether an emitted integer boundary
`value` is a JSON integer or canonical numeric text. The engine emits canonical
text. This ambiguity caused the independent tester's first output-type
expectation to fail; exact numeric values, classes, origins and counts were
then verified without changing product code.

Recommended follow-up: specify the output JSON type for both integer and
decimal boundary values so downstream consumers do not infer it from examples.

## Conformance and risk assessment

The implementation conforms to the in-scope requirements and architecture:

- boundary synthesis uses exact scaled-integer arithmetic, explicit
  origin/step/inclusivity, at most six distinct requested positions, canonical
  point rows, and typed missing-oracle/unrepresentable/empty-domain results;
- decision synthesis keeps boolean, integer and string values distinct,
  validates the finite constraint AST once, exhaustively classifies the bounded
  Cartesian universe, and reconciles one mutually exclusive assignment ledger;
- state synthesis uses `(from_state, trigger)` logical identity, rejects
  divergent records, preserves oracle-independent structural reachability,
  includes terminal closed-world denial cases, and retains affected links;
- model and candidate identities bind normalized method content, linked
  requirements, and every resolved source/oracle object used by the model;
- all method artifacts remain `DRAFT`/`PENDING`/`NOT_EXECUTED`; references are
  inert identifiers and no runner, network client, enterprise adapter or
  approval path is invoked;
- malformed input and limit failures are value-free typed errors. CLI
  validation completes before temporary-output creation, replacement is
  atomic, and a rejected input preserves the previous destination;
- the engine has no mutable shared state. Canonical ordering and pure local
  evaluation avoid a concurrency-sensitive persistence boundary in this slice;
- declared model, AST, assignment, state, transition and closed-world limits
  bound work before unbounded synthesis; no timing or throughput claim is made;
- legacy Campaign input omits `method_design` and preserves prior report values
  apart from the full-input digest. Method candidates remain separate from
  legacy `test_cases` and quality scoring.

No unresolved correctness, security, data-integrity, failure-handling,
backward-compatibility, or material performance finding was observed at P0,
P1, or P2 severity.

## Verification evidence assessed

The independent tester was separate from the engine and CLI implementation
authors. Its final report records:

- 18 focused independent tests passed in 1.126 seconds;
- 510 strict full-regression tests passed in 21.677 seconds with
  `ResourceWarning` promoted to error;
- a newly built wheel installed with `--no-index` into a fresh virtual
  environment and was imported from `site-packages` outside the repository;
- three installed CLI scenarios passed: all three method types, legacy input,
  and secret-shaped-key rejection with exact destination preservation;
- the installed all-method fixture produced 10 draft candidates and 3
  obligations, with `NOT_EXECUTED` and Campaign `NOT_AUTHORIZED` retained;
- installed-process socket and child-process sentinels were not triggered;
- the initial tester-oracle type mismatch and Windows UTF-8 reader error were
  preserved and corrected as test-harness issues without source edits.

The reviewer independently reran the final 18-test oracle suite on the frozen
tree: 18 tests passed in 1.161 seconds. Before freeze, the reviewer also ran the
engine and Campaign integration suites against the same source/CLI hashes: 35
tests passed in 1.330 seconds. Reviewer adversarial fixtures reproduced the
original P1/P2 defects before repair and then verified strict typed matching,
34-digit exact arithmetic, missing-oracle metamorphism, exact coverage,
reference binding, closed-world limits and permutation stability after repair.

## Verdict boundary

The frozen CR-010 structured-method engine and installed Campaign draft
integration pass independent review with the two documentation P3 follow-ups
above. This verdict is limited to deterministic local design synthesis and its
draft-only CLI projection.

The following remain outside this verdict: a project Gate decision, complete
V1 acceptance, production or enterprise-provider integration, remote execution,
performance/SLA qualification, a controlled paired comparison, human
acceptance, release readiness and deployment.
