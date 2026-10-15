# CR-010 structured design methods review

- Artifact ID: `DOC-DESIGN-METHODS-REVIEW-001`
- Review phase: `PREFREEZE_OBSERVATION`
- Document State: `DRAFT`
- Evaluation State: `IN_REVIEW`
- Evidence Status: `OBSERVED`
- Reviewer: `/root/workflow_review`
- Reviewed code subject: `2aec195f27dd7dfa1f1d7350bb904e1682fe4d85`
- Reviewed design candidate: `DES-033` SHA-256 `764A05DAC730F9A9B71D741593EAC86428FBD7BC1DDB89FC8031BE9612081029`
- ADR candidate: `ADR-004` SHA-256 `EF5350AF611E618172D1EF5CEAFB8ECEF03366073C7CDAA26204AFE5E275639F`
- Date: 2026-10-15

This record preserves defects found before the CR-010 source freeze. It is not
the formal TASK-037 review, an independent test result, a defect closure, an
acceptance decision, a benchmark result, or a Gate decision. Formal review must
use the later frozen implementation and TASK-036 independent evidence.

## Open findings against `2aec195`

### P1 — Typed decision values collapse and the AST budget is consumed per assignment

The schema distinguishes JSON `true`, integer `1`, and string `"1"`, but rule
and constraint evaluation uses Python `==`, `!=`, `in`, and `not in`. A model
whose domain is `[true, 1]` and whose two rules match those values produced two
`conflict` assignments and zero candidates instead of two unique assignments.

The 128-node budget is also incremented while evaluating every assignment. A
valid 129-assignment table with one `ne` leaf failed with
`DECISION_CONSTRAINT_INVALID`, although its AST contains one node and its
Cartesian universe is below 4,096.

Required regression: compare `(JSON type, value)` for equality, membership and
rule matching; validate/count the AST once; exhaustively accept the 129-cell
one-node fixture and reject an actual 129-node AST.

### P1 — State structure depends incorrectly on oracle readiness and omits required closed-world cases

A valid `a --go--> b` edge with a null oracle emitted the expected
`STATE_ORACLE_MISSING` obligation but was removed from the graph before BFS.
The result reported reachable `['a']` and unreachable `['b']`; structural
reachability must remain independent of case/oracle readiness.

The required one-state terminal model with no transitions and an empty trigger
set failed with `INVALID_REFERENCE_SET`. Closed-world completion also excluded
terminal state/trigger pairs and emitted obligations rather than the denial
candidates bound to the shared oracle. The transition logical key additionally
included guards, contrary to the frozen `(from_state, trigger)` contract.

Required regression: empty-trigger terminal fixture; null-oracle reachable edge;
same-key divergent guards conflict; terminal closed-world denial candidate; and
state/transition/reachability count conservation.

### P1 — Decimal boundary input and arithmetic do not implement the precision contract

The implementation accepts decimal `scale` but has no `precision` field. Adding
the design-required `precision: 6` to an otherwise valid model failed with
`INVALID_SCHEMA`. Arithmetic uses ambient `Decimal` context even though inputs
may contain 34 significant digits, and computed neighbours are not converted
to `BOUNDARY_NEIGHBOR_UNREPRESENTABLE` when they exceed precision/scale.

Required regression: canonical precision/scale intake; 34-digit exact grid and
neighbour arithmetic; upper/lower overflow obligations; six-position
deduplication and analysis conservation.

### P2 — Decision and state classifications do not reconcile to the required analysis schema

Same-outcome rules with divergent oracle sets are counted first as overlap and
then as oracle conflict instead of the single primary `DECISION_CONFLICT`
classification. Analysis lacks the required universe/admissible/unique/oracle
splits, and state coverage excludes closed-world logical keys. Existing class
counts are therefore not the mutually exclusive ledger defined by DES-033.

Required regression: assert every exact analysis field, row enum, conservation
equation, and the mapping into common coverage fields for all three methods.

### P2 — Reference, priority and digest bindings are weaker than the design contract

The reviewed subject accepts URL-like locators such as
`https://user@example/path?token=abc#frag`; it does not enforce reference-kind
compatibility. Mixed linked priorities P0 and P3 become P2 rather than P0.
Changing a linked requirement's text left both `method_design.input_sha256` and
the derived candidate ID unchanged because only requirement IDs are bound.
Resolved source/oracle objects are also absent from the per-model digest.

Required regression: strict relative opaque locator grammar; source/oracle kind
compatibility; highest-urgency priority selection; and digest/ID drift when any
bound requirement or resolved reference changes.

## Reproduction evidence

The reviewer executed the exact `2aec195:qa_master/design_methods.py` blob in an
isolated in-memory namespace with only `DIMENSIONS` supplied. No workspace
source was changed. The focused fixture output was:

```text
OBS1_TYPED {'candidate': 0, 'gap': 0, 'overlap': 0, 'conflict': 2, 'oracle_missing': 0} 0
OBS2_BUDGET DesignMethodError DECISION_CONSTRAINT_INVALID
OBS3_EMPTY DesignMethodError INVALID_REFERENCE_SET
OBS4_REACH ['a'] ['b']
OBS5_PRECISION DesignMethodError INVALID_SCHEMA
OBS6_PRIORITY_BIND P2 True True
OBS7_LOCATOR accepted
```

The engine-owned six-test suite did not cover these failures. Each finding
remains open until the implementation owner provides focused regression tests
and TASK-036 independently exercises the frozen repair.

## Architecture prefreeze boundary

DES-033 at the hash above resolves the arithmetic, typed comparison, AST,
reachability, closed-world, binding and exact-analysis intent needed to repair
the implementation. Its remaining documentation observations are tracked with
the architect before final freeze and do not convert this prefreeze record into
a formal approval.

## Prefreeze retest of the v2 implementation candidate

- Retested source SHA-256:
  `B40F5D9EEA8BB7F274CC302266402B23C9EB0ADAFF1E413E362F00EF94A04016`
- Requirements SHA-256:
  `5638A3700F072BFFE5A58C212348966A263D60CDDBA17888314E22C1EBB4E99F`
- DES-033 SHA-256:
  `F823304B68151A3127B0A4F0BC1F5479A69F7FE6A9664C95B328EB0449232CCC`
- Result: `PREFREEZE_REPAIR_REQUIRED`

The v2 candidate closes the original AST-budget, structural-reachability,
empty-trigger, logical-key, closed-world and priority findings, but it does not
close all critical findings. This remains a prefreeze observation and is not a
formal TASK-037 review.

### P1 — Typed rule matching still collapses boolean and integer values

Constraint evaluation and the newly added analysis ledger use typed scalar
keys, but the aggregate candidate/obligation loop still matches rules with
Python equality. For a two-value domain `[true, 1]` with one rule for each
typed value, the analysis reported two unique assignments and two conflicts,
while candidate emission produced zero cases and two conflict obligations.
The mutually exclusive ledger therefore also fails its conservation equation.

Required repair: use the same typed comparison in the sole classification and
projection path. Add a regression asserting two admissible assignments, two
`UNIQUE_ORACLE_READY`, zero conflicts, two candidates, and classification sum
equal to two.

### P1 — Decimal arithmetic still depends on ambient context

A valid decimal model with `precision: 34`, `scale: 0`, `origin: "0"`,
`step: "1"`, and equal lower/upper bounds containing 34 nines raised raw
`decimal.InvalidOperation` with `DivisionImpossible` during the grid modulo.
This violates the scaled-integer arithmetic contract and the stable-error
boundary.

Required repair: parse canonical decimals to scaled integers before grid and
neighbour operations. Add a 34-digit grid regression plus a case in which a
35-digit computed neighbour becomes `BOUNDARY_NEIGHBOR_UNREPRESENTABLE` rather
than an exception.

### P1 — Boundary emptiness is coupled to oracle availability

Removing only the `IN_DOMAIN` oracle from an otherwise valid boundary emitted
both `BOUNDARY_ORACLE_MISSING` and `BOUNDARY_EMPTY_DOMAIN`. The structural
domain still contains in-domain grid points; a missing oracle suppresses a
candidate but does not make the domain empty.

Required repair: derive emptiness from classified representable points before
oracle projection. Add a regression asserting an in-domain point with a null or
missing oracle emits the missing-oracle obligation without the empty-domain
obligation.

### P2 — Common coverage and digest/reference bindings remain non-conformant

All three methods currently return coverage state `PENDING` and denominator
name `finite_declared_universe`; DES-033 permits only `ASSESSED` or
`UNASSESSED` and fixes method-specific names and projections. The full method
digest remains unchanged when linked requirement content changes, while a
candidate ID remains unchanged when its resolved oracle locator changes.
Finally, the grammar-valid locator `docs/tokenization` is rejected by a value
substring heuristic that the final design removed.

Required repair: implement the exact common coverage mappings; bind complete
linked requirements in the method input digest and every used resolved oracle
object in the model digest; enforce the opaque locator grammar and controlled
field names without value-substring guessing.

### Retest output

```text
TYPED_COUNTS {'UNIQUE_ORACLE_READY': 2, 'UNIQUE_ORACLE_MISSING': 0,
 'OVERLAP_ORACLE_READY': 0, 'OVERLAP_ORACLE_MISSING': 0, 'CONFLICT': 2,
 'GAP': 0}
TYPED_CANDIDATES 0
TYPED_CODES ['DECISION_CONFLICT', 'DECISION_CONFLICT']
EMPTY_CODES ['BOUNDARY_EMPTY_DOMAIN', 'BOUNDARY_ORACLE_MISSING',
 'BOUNDARY_ORACLE_MISSING']
DECIMAL34 decimal.InvalidOperation [<class 'decimal.DivisionImpossible'>]
LOCATOR_TOKENIZATION DesignMethodError DESIGN_SENSITIVE_LOCATOR
REQ_BIND True False
ORACLE_BIND False True
COVERAGE B PENDING finite_declared_universe
COVERAGE Q PENDING finite_declared_universe
COVERAGE S PENDING finite_declared_universe
```

For `REQ_BIND` and `ORACLE_BIND`, the two booleans respectively mean
`method input digest unchanged` and `representative candidate ID unchanged`.
The linked requirement changed only the candidate ID; the resolved oracle
changed only the top-level method digest. Both asymmetries violate the required
complete binding.
