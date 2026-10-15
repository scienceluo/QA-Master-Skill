# DES-033 — Structured finite test-design methods

- Artifact ID: `DES-033`
- Document State: `DRAFT`
- Evaluation State: `IN_REVIEW`
- Change / task: `CR-010` / `TASK-033`
- Requirements: `REQ-013`–`REQ-018`, `NFR-005`
- Inputs: `DOC-REQ-TEST-DESIGN-001` v4, `DOC-COMPARISON-RESEARCH-001` v1, `DOC-RTM-001` v13
- Evidence boundary: this design defines deterministic local draft generation. It does not execute tests, approve a requirement, score a competitor, or support a superiority claim.

## 1. Scope and component boundary

Add one dependency-free module, `qa_master.design_methods`, containing strict JSON intake, normalization, the three finite algorithms, canonical IDs, and result projection. `qa_master.campaign_cli.prepare_campaign` calls it only when the input contains `design_models`; the existing requirement review, generic cases, coverage and workflow fields remain unchanged.

The public API is:

```python
class DesignMethodError(ValueError):
    code: str

def load_bundle_json(payload: bytes | str) -> dict: ...
def design_methods(bundle: dict) -> dict: ...
```

`str(DesignMethodError) == error.code`. Messages contain only a stable code. The module imports no process, network, enterprise-adapter, runner or approval implementation.

`load_bundle_json` rejects invalid UTF-8/JSON, duplicate object keys, and `NaN`/`Infinity` globally. To preserve valid legacy bundles, JSON floats and secret-shaped keys are rejected recursively below `design_models` and in every requirement record referenced by a model; unreferenced legacy requirement records retain their prior handling. API callers that already hold a Python dictionary cannot prove whether duplicate JSON keys were collapsed; the CLI loader is the canonical file-input path.

## 2. Input schema

When present, top-level `design_models` is an object with exactly:

```json
{
  "schema_version": 1,
  "source_refs": [],
  "oracle_refs": [],
  "models": []
}
```

The three arrays are bounded and treated as sets: refs and models are normalized by ID. There are at most 100 models. IDs are 1–128 ASCII characters matching `[A-Za-z0-9_.:-]+`.

### 2.1 References

A source or oracle reference has exactly `id`, `kind`, `locator`, and optional `sha256`. An optional digest is lowercase 64-hex.

A locator is a relative opaque identifier of at most 512 ASCII characters. It consists of `/`-separated segments matching `[A-Za-z0-9][A-Za-z0-9_.-]*`; `.` and `..` segments are forbidden. Thus it cannot contain a URL scheme, leading slash, drive/UNC prefix, backslash, userinfo, query, fragment or whitespace. The engine does not guess whether an allowed opaque value contains a secret; callers must supply non-secret locators. Secret-shaped field names remain rejected by the exact schema/key rule.

Allowed source kinds are `requirement`, `risk`, `contract`, `model`, `guard`, `effect`, `change`, `defect`, and `other`. Allowed oracle kinds are `valid`, `invalid`, `outcome`, `transition`, `denial`, and `effect`. References are identifiers and locators only; the engine does not open or execute them.

Every model has exactly:

```json
{
  "id": "DM-1",
  "method": "boundary",
  "title": "Amount boundary",
  "dimension": "functional",
  "requirement_ids": ["REQ-X"],
  "source_refs": ["SRC-X"],
  "spec": {}
}
```

`method` is `boundary`, `decision_table`, or `state_transition`. `dimension` is one of the existing 13 `qa_master.core.DIMENSIONS`. Requirement IDs must exist in `bundle.requirements`; reference IDs must exist in their registry. Set-like arrays are non-empty, unique, and normalized lexically.

Unknown fields are rejected. Keys whose case-folded name is `password`, `token`, `cookie`, `private_key`, `private-key`, or `privatekey` are rejected anywhere below `design_models`. Values are never included in an error.

### 2.2 Structural failure versus an obligation

Malformed type, unknown field/link/requirement, duplicate ID, float, secret-shaped key, invalid arithmetic/grid, contradictory bounds, invalid grammar, or a limit breach raises `DesignMethodError` and returns no result. The whole call is atomic; valid sibling models do not create a partial result.

A valid finite model may be semantically incomplete. A missing class oracle, an uncovered decision assignment, equal-outcome overlap, conflicting rules/transitions, unreachable state, or unrepresentable requested boundary neighbour becomes a typed obligation. It does not reject valid sibling obligations and does not become a fabricated case.

## 3. Canonical form and identities

Canonical JSON is UTF-8, keys sorted, compact separators, `ensure_ascii=False`, and no non-finite or floating number. Object keys are ordered by canonical JSON. Set-like arrays are sorted by normalized ID; condition values use type order boolean, integer, string and then natural value order. Ordered procedural arrays in emitted cases retain their defined method order.

For Decimal, canonical text is the finite plain-decimal representation with no `+` or exponent, no leading integer zero except `0`, no redundant fractional trailing zero, and negative zero normalized to `0`. Input must already equal that canonical form. `scale` is the maximum allowed fractional digit count, not a request to preserve trailing zeros.

Each normalized model has `model_sha256`. The digest binds the complete normalized model, all resolved source/oracle reference objects it uses, and the complete canonical JSON object for every linked requirement; a changed linked requirement therefore changes every derived ID. Method-enabled referenced requirements use the same no-float and secret-key rule as `design_models`. A candidate identity is canonical method data excluding display text. Its ID is:

```text
TC-MD- + uppercase(first 20 hex SHA256(canonical({model_sha256, candidate_identity})))
```

An obligation uses the same rule with its code and subject and prefix `OB-MD-`. A collision between different full digests is `DESIGN_ID_COLLISION`. Outputs sort models by model ID and flattened candidates/obligations by ID. Method-specific analysis retains numeric or assignment order separately.

## 4. Boundary method

The boundary `spec` has exactly:

```json
{
  "numeric_type": "integer",
  "origin": 0,
  "step": 1,
  "lower": {"value": 0, "inclusive": true},
  "upper": {"value": 10, "inclusive": true},
  "oracle_by_class": {
    "IN_DOMAIN": "OR-VALID",
    "LOWER_INVALID": "OR-INVALID",
    "UPPER_INVALID": "OR-INVALID",
    "BOTH_INVALID": "OR-INVALID"
  }
}
```

For `decimal`, `origin`, `step`, and bound values are canonical decimal strings and both `precision` in `1..34` and `scale` in `0..18` are additionally required. Precision is the maximum significant-digit count and scale is the maximum fractional-digit count. Inputs must already be canonical: use `"1.2"` and `"0"`; `"1.20"` and `"-0"` are rejected rather than silently normalized. After lexical validation, each decimal is converted exactly to a signed integer in units of `10^-scale`; all grid checks, addition, subtraction, comparison and neighbour construction use those integers, never ambient `decimal` context or rounding. A result converts back to canonical text only after its significant-digit count is checked against `precision`. For `integer`, numeric values are strict JSON integers, booleans are rejected, and `precision`/`scale` are forbidden. Every integer has at most 34 significant digits; `step > 0`; lower is not above upper; and both bounds lie on `origin + n * step` for an integer `n`.

Candidate points are the set of `lower-step`, `lower`, `lower+step`, `upper-step`, `upper`, and `upper+step`. They are deduplicated and sorted by exact numeric value. Each point receives exactly one class:

1. `IN_DOMAIN` if it satisfies both bounds and inclusivity;
2. `BOTH_INVALID` if it violates both bound predicates;
3. `LOWER_INVALID` if only the lower predicate fails;
4. `UPPER_INVALID` otherwise.

The exact class must have an `oracle_by_class` entry to emit a candidate. `IN_DOMAIN` accepts only oracle kind `valid`; other classes accept `invalid` or `denial`. Multiple class keys may deliberately reference the same oracle ID; there is no implicit fallback. Missing entries emit `BOUNDARY_ORACLE_MISSING`. If exact neighbour arithmetic exceeds the declared precision/scale representation, emit `BOUNDARY_NEIGHBOR_UNREPRESENTABLE` for that requested point. If no grid point is valid, emit `BOUNDARY_EMPTY_DOMAIN`. The denominator is the distinct requested point set, including an unrepresentable requested neighbour as an obligation, and is at most six.

Boundary `analysis` has exactly `requested_positions`, `distinct_points`, `representable_points`, `unrepresentable`, `in_domain`, `lower_invalid`, `upper_invalid`, `both_invalid`, `candidate_ready`, `oracle_missing`, `points`, and `classification_counts`. It must satisfy `requested_positions = 6`, `distinct_points <= 6`, `distinct_points = representable_points + unrepresentable`, `representable_points = in_domain + lower_invalid + upper_invalid + both_invalid`, and `representable_points = candidate_ready + oracle_missing`. `classification_counts` uses only `CANDIDATE_READY`, `ORACLE_MISSING`, and `UNREPRESENTABLE` and sums to `distinct_points`. Each numeric-ordered point row has exactly `value`, `class`, `representable`, `origins`, `candidate_id`, and `obligation_ids`; nullable IDs keep suppressed cases visible.

Candidate method data contains canonical `value`, `class`, and originating bound positions. Steps set the named domain value, execute only the referenced requirement scenario, and collect evidence for the referenced oracle. Expected text names the oracle reference; it never invents a response code or message.

## 5. Decision-table method

The decision-table `spec` has exactly `conditions`, `constraints`, and `rules`.

```json
{
  "conditions": [
    {"id": "member", "values": [false, true]},
    {"id": "region", "values": ["domestic", "foreign"]}
  ],
  "constraints": [
    {"op": "any", "items": [
      {"op": "ne", "condition": "member", "value": false},
      {"op": "ne", "condition": "region", "value": "foreign"}
    ]}
  ],
  "rules": [
    {"id": "R1", "when": {"member": true}, "outcome_id": "discount",
     "source_refs": ["SRC-RULE"], "oracle_ref": "OR-DISCOUNT"}
  ]
}
```

Conditions are sorted by ID. Each domain contains unique strict scalars: string, boolean, or signed integer; floats are forbidden and boolean is distinct from integer. Domains are normalized by the canonical scalar order. The Cartesian product is computed before filtering and must be at most 4,096.

Constraint leaves have exact schemas:

- `{"op":"eq"|"ne","condition":ID,"value":SCALAR}`
- `{"op":"in"|"not_in","condition":ID,"values":[SCALAR,...]}`

Composite nodes are `{"op":"all"|"any","items":[NODE,...]}`. Arrays are non-empty. Nesting is at most 8 and a model has at most 128 distinct AST nodes, counted once during validation across all top-level constraints; evaluation for each assignment does not consume or increment this budget. Values must exist in the named condition domain. The top-level constraint list is an implicit `all`; an assignment is admissible only when every constraint evaluates true. Scalar equality and membership compare the pair `(JSON type, value)`, so `true`, `1`, and `"1"` are always distinct. No expression, regex, callable, `eval`, sampling, or external lookup exists.

A rule `when` is a partial object from known condition IDs to one domain value. Empty `when` is allowed as an explicit default and participates in overlap analysis. Decision rule oracle kind must be `outcome` or `effect`. Rules are sorted by ID. For every admissible assignment:

- zero matches: `DECISION_GAP`, no candidate;
- one match with oracle: one candidate;
- one match without oracle: `DECISION_ORACLE_MISSING`, no candidate;
- multiple matches with the same `outcome_id` and the identical oracle set, including the all-null set: `DECISION_OVERLAP`; emit one candidate only when that identical oracle is non-null;
- divergent outcome IDs or divergent oracle sets: `DECISION_CONFLICT`, no candidate.

Decision `analysis` has exactly `universe_size`, `excluded`, `constraint_unevaluable`, `admissible`, `unique`, `overlap`, `conflict`, `gap`, `unique_oracle_ready`, `unique_oracle_missing`, `overlap_oracle_ready`, `overlap_oracle_missing`, `oracle_ready`, `assignments`, and `classification_counts`. Schema-v1 constraints are fully evaluable after validation, so `constraint_unevaluable` is zero; the field prevents a future version from hiding an unevaluable cell. The following equations are mandatory: `universe_size = excluded + constraint_unevaluable + admissible`; `admissible = unique + overlap + conflict + gap`; `unique = unique_oracle_ready + unique_oracle_missing`; `overlap = overlap_oracle_ready + overlap_oracle_missing`; and `oracle_ready = unique_oracle_ready + overlap_oracle_ready`. `classification_counts` has exactly `UNIQUE_ORACLE_READY`, `UNIQUE_ORACLE_MISSING`, `OVERLAP_ORACLE_READY`, `OVERLAP_ORACLE_MISSING`, `CONFLICT`, and `GAP`; it is mutually exclusive and sums to `admissible`. Each canonical assignment row has exactly `values`, `admissibility`, `matched_rule_ids`, `classification`, `candidate_id`, and `obligation_ids`; `admissibility` is `ADMISSIBLE`, `EXCLUDED`, or `UNEVALUABLE`. Assignment `classification` is exactly one of the six count keys, `EXCLUDED`, or `CONSTRAINT_UNEVALUABLE`. `NO_RULES` is not a validation error: every admissible assignment becomes a gap. An all-excluded model has denominator zero and no ratio.

## 6. State-transition method

The state-transition `spec` has exactly `states`, `initial_state`, `triggers`, `transitions`, `closed_world`, and `closed_world_deny_oracle_ref`.

```json
{
  "states": [
    {"id": "draft", "terminal": false, "source_refs": ["SRC-STATE"]},
    {"id": "submitted", "terminal": true, "source_refs": ["SRC-STATE"]}
  ],
  "initial_state": "draft",
  "triggers": ["submit", "edit"],
  "transitions": [
    {"id": "T1", "validity": "valid", "from_state": "draft",
     "to_state": "submitted", "trigger": "submit", "guard_refs": [],
     "effect_refs": ["SRC-EFFECT"], "source_refs": ["SRC-STATE"],
     "oracle_ref": "OR-SUBMITTED"}
  ],
  "closed_world": true,
  "closed_world_deny_oracle_ref": "OR-DENY"
}
```

There are at most 128 states, 512 explicit transitions, and 4,096 closed-world pairs. Exactly one existing state is named by `initial_state`. State and trigger IDs are unique. `triggers` may be empty only when `closed_world` is false and there are no transition records, which permits the required one-state terminal model. Closed world requires a non-empty trigger set. A terminal state cannot have an outgoing valid transition.

A transition has the exact fields shown above. `validity` is `valid` or `invalid`. Valid transitions require `to_state` and at least one effect reference. Invalid transitions set `to_state` to `null`; they may name denial/audit effects. `guard_refs`, `effect_refs`, and `source_refs` are unique known source IDs; oracle may be `null`, which produces an obligation instead of a candidate.

Every transition trigger must occur in `triggers`. Guard references must have source kind `guard`, effect references kind `effect`. A valid transition oracle kind is `transition` or `effect`; an invalid transition oracle kind is `denial`.

The logical key is `(from_state, trigger)`. Duplicate record IDs are structural errors. Different record IDs with the same logical key and identical normalized validity, target, guards, effects, sources, and oracle produce `STATE_DUPLICATE` and one logical candidate. Divergent records for one key, including valid/invalid collision or different guard/target/effect/oracle, produce `STATE_CONFLICT` and no candidate for that key.

An explicit invalid key never implies any other invalid transition. When `closed_world` is true, `triggers` and a known non-null `denial` oracle are required. The engine creates one guardless invalid candidate for every `(state, trigger)` pair, including terminal states, having no explicit record for that pair. Terminal outgoing valid transitions remain structural errors; terminal invalid checks are legitimate denial cases. It does not enumerate the complement of guarded predicates. `closed_world_deny_oracle_ref` must be null when closed world is false.

Reachability is breadth-first from `initial_state` over every nonconflicting valid edge, including an edge whose oracle is null and whose case is therefore suppressed; oracle readiness never changes graph structure. Guards are treated as potentially satisfiable. State IDs and adjacency are sorted, yielding a stable result. It reports reachable/unreachable states and transitions with `reachability_basis: STRUCTURAL_ONLY`. A valid candidate whose source state is unreachable remains visible but adds `STATE_UNREACHABLE_TRANSITION`; reachability never becomes PASS, VERIFIED, or execution evidence.

State `analysis` has exactly `state_count`, `trigger_count`, `explicit_records`, `logical_keys`, `closed_world_added`, `reachable_states`, `unreachable_states`, `reachable_transitions`, `unreachable_transitions`, `logical_rows`, and `classification_counts`. The coverage denominator is the number of logical keys after closed-world completion. `classification_counts` has mutually exclusive keys `VALID_READY`, `VALID_ORACLE_MISSING`, `INVALID_READY`, `INVALID_ORACLE_MISSING`, `DUPLICATE_VALID_READY`, `DUPLICATE_VALID_ORACLE_MISSING`, `DUPLICATE_INVALID_READY`, `DUPLICATE_INVALID_ORACLE_MISSING`, and `CONFLICT`; their sum equals the denominator. Each row has exactly `from_state`, `trigger`, `record_ids`, `classification`, `structurally_reachable`, `candidate_id`, and `obligation_ids`. Candidate-ready is the sum of the four `*_READY` classes, duplicate is the four `DUPLICATE_*` classes, and conflict is `CONFLICT`. Reachability counts are supplementary and may overlap candidate readiness.

## 7. Output schema and existing-case compatibility

`design_methods` returns exactly:

```json
{
  "schema_version": 1,
  "status": "DRAFT_UNAPPROVED",
  "execution": "NOT_EXECUTED",
  "input_sha256": "...",
  "model_results": [],
  "candidates": [],
  "obligations": [],
  "summary": {
    "model_count": 0,
    "candidate_count": 0,
    "obligation_count": 0,
    "by_method": {}
  }
}
```

Each model result has exactly `model_id`, `method`, `input_sha256`, `candidate_ids`, `obligation_ids`, `coverage`, and `analysis`. Coverage has exactly `state`, `denominator_name`, `denominator`, `candidate_ready`, `oracle_missing`, `gap`, `overlap`, `conflict`, `unevaluable`, `unreachable`, `out_of_scope`, and `ratio`. `state` is `ASSESSED` or `UNASSESSED`. `ratio` is null unless the denominator is positive and fully defined; otherwise it is `{"numerator": candidate_ready, "denominator": denominator}`. Method `analysis.classification_counts` is the mutually exclusive reconciliation ledger; summary counts such as overlap and unreachable may be additional, overlapping observations.

The generic coverage mapping is fixed:

- boundary: denominator name `distinct_points`; denominator/candidate/oracle counts come from boundary analysis; `gap` is 1 only for `BOUNDARY_EMPTY_DOMAIN`; `overlap`, `conflict`, `unevaluable`, and `unreachable` are zero; `out_of_scope = unrepresentable`; state is `ASSESSED` and the ratio is present because the finite requested point set is known;
- decision table: denominator name `admissible_assignments`; denominator is `admissible`; candidate ready is `oracle_ready`; oracle missing is the sum of unique/overlap missing; gap/overlap/conflict/unevaluable map to the same analysis fields; unreachable is zero; out of scope is `excluded`; state is `UNASSESSED` with null ratio only when admissible is zero, otherwise `ASSESSED` with the ratio;
- state transition: denominator name `logical_transition_keys`; denominator is `logical_keys`; candidate/oracle/conflict counts derive from state classification counts; overlap is the number of duplicate logical keys, not duplicate records; unreachable is the number of unreachable valid logical transitions, not unreachable states; gap, unevaluable, and out of scope are zero; state is `UNASSESSED` with null ratio only when logical keys is zero, otherwise `ASSESSED` with the ratio.

Every candidate retains the fields consumed by `quality.review_cases`: `id`, `title`, `priority`, `trace`, `dimension`, `preconditions`, `data`, `steps`, and `expected`. It additionally has `model_id`, `method`, resolved `source_refs`, resolved `oracle_refs`, `method_data`, `approval: DRAFT`, `evidence_state: PENDING`, and `validation_action: NOT_EXECUTED`. Priority is the highest urgency among linked P0–P3 requirements (`P0` highest); if none has a valid priority it is P2. It is never inferred from generated coverage.

Every obligation has `id`, `code`, `model_id`, `method`, `status`, `requirement_ids`, resolved `source_refs`, resolved `oracle_refs`, and typed `subject`. Status uses only `PENDING`, `NOT_AVAILABLE`, `NOT_EXECUTED`, or `UNASSESSED`.

Campaign behavior is exact:

- if `design_models` is absent, do not call the engine, do not add a field or CLI-summary key, and preserve the legacy result values;
- if it is present, including an empty model array, add only `method_design` with the result above;
- never merge, renumber, replace, or quality-score `test_cases`; method cases live at `method_design.candidates`;
- CLI summary adds `method_candidates`, `method_obligations`, `status: DRAFT_UNAPPROVED`, and `execution: NOT_AUTHORIZED` only for the method-enabled path.

The full campaign `input_sha256` binds the original bundle; `method_design.input_sha256` binds normalized `design_models` plus referenced requirement identity. This offline report is immutable output, not a canonical Campaign completion or approval. A later import must bind this digest and use the existing Campaign CAS/invalidation rules; such import is outside CR-010.

## 8. CLI failure, reliability and lifecycle

The CLI parses and computes the complete report before creating a temporary output. Any loader, validation, limit, or synthesis error prints only `{"status":"REJECTED","error":CODE}` and exits 2. An existing destination stays byte-identical and no temporary file remains. Normal output retains the current same-path and 5 MB input guards and atomic replace.

Resource bounds are the requirement limits. Decision enumeration is `O(product(domain sizes) * (constraint nodes + rules * condition count))`; state reachability is `O(states + valid transitions)`; boundary work is constant per model. Results may contain at most the corresponding bounded universe. These are safety bounds, not capacity or latency claims.

No secret value, source document, oracle document, raw input, exception representation, or locator is printed in the CLI summary/error. Full local artifacts intentionally retain non-secret locators supplied by the caller. Data lifecycle is caller-managed local input/output; this slice adds no retention deletion, database migration, network upload, or remote cache.

Upgrade is additive. Rollback removes method-enabled inputs or uses the prior package; legacy bundles remain compatible. A method-enabled artifact is not readable by older code as a method artifact, so the output records schema version and input digest rather than silently degrading.

## 9. Executable example fixture

This is a complete method section to embed beside ordinary campaign `project` and `requirements`. Reference locators are illustrative non-secret identifiers.

```json
{
  "schema_version": 1,
  "source_refs": [
    {"id": "SRC-REQ", "kind": "requirement", "locator": "docs/REQ-EXAMPLE"},
    {"id": "SRC-RULE", "kind": "model", "locator": "docs/DECISION-1"},
    {"id": "SRC-STATE", "kind": "model", "locator": "docs/STATE-1"},
    {"id": "SRC-EFFECT", "kind": "effect", "locator": "docs/EFFECT-1"}
  ],
  "oracle_refs": [
    {"id": "OR-DENY", "kind": "denial", "locator": "oracles/DENY"},
    {"id": "OR-DISCOUNT", "kind": "outcome", "locator": "oracles/DISCOUNT"},
    {"id": "OR-INVALID", "kind": "invalid", "locator": "oracles/INVALID"},
    {"id": "OR-NORMAL", "kind": "outcome", "locator": "oracles/NORMAL"},
    {"id": "OR-SUBMITTED", "kind": "transition", "locator": "oracles/SUBMITTED"},
    {"id": "OR-VALID", "kind": "valid", "locator": "oracles/VALID"}
  ],
  "models": [
    {
      "id": "DM-AMOUNT", "method": "boundary", "title": "Accepted amount",
      "dimension": "functional", "requirement_ids": ["REQ-EXAMPLE"], "source_refs": ["SRC-REQ"],
      "spec": {
        "numeric_type": "decimal", "precision": 6, "scale": 2, "origin": "0", "step": "0.01",
        "lower": {"value": "0.01", "inclusive": true},
        "upper": {"value": "100", "inclusive": false},
        "oracle_by_class": {"IN_DOMAIN": "OR-VALID", "LOWER_INVALID": "OR-INVALID", "UPPER_INVALID": "OR-INVALID", "BOTH_INVALID": "OR-INVALID"}
      }
    },
    {
      "id": "DM-DISCOUNT", "method": "decision_table", "title": "Discount decision",
      "dimension": "functional", "requirement_ids": ["REQ-EXAMPLE"], "source_refs": ["SRC-REQ", "SRC-RULE"],
      "spec": {
        "conditions": [{"id": "member", "values": [false, true]}, {"id": "region", "values": ["domestic", "foreign"]}],
        "constraints": [],
        "rules": [
          {"id": "R1", "when": {"member": true}, "outcome_id": "discount", "source_refs": ["SRC-RULE"], "oracle_ref": "OR-DISCOUNT"},
          {"id": "R2", "when": {"member": false}, "outcome_id": "normal", "source_refs": ["SRC-RULE"], "oracle_ref": "OR-NORMAL"}
        ]
      }
    },
    {
      "id": "DM-ORDER", "method": "state_transition", "title": "Order submission",
      "dimension": "functional", "requirement_ids": ["REQ-EXAMPLE"], "source_refs": ["SRC-REQ", "SRC-STATE"],
      "spec": {
        "states": [{"id": "draft", "terminal": false, "source_refs": ["SRC-STATE"]}, {"id": "submitted", "terminal": true, "source_refs": ["SRC-STATE"]}],
        "initial_state": "draft", "triggers": ["edit", "submit"],
        "transitions": [{"id": "T1", "validity": "valid", "from_state": "draft", "to_state": "submitted", "trigger": "submit", "guard_refs": [], "effect_refs": ["SRC-EFFECT"], "source_refs": ["SRC-STATE"], "oracle_ref": "OR-SUBMITTED"}],
        "closed_world": true, "closed_world_deny_oracle_ref": "OR-DENY"
      }
    }
  ]
}
```

## 10. Test mapping and handoff

Independent tests should assign stable `TC-DM` IDs and cover:

1. canonical restart equality, duplicate-key/float/secret/unknown-link rejection, and all exact limits;
2. integer and Decimal open/closed/negative/one-step/point/empty/unrepresentable-neighbour boundary results;
3. exhaustive decision universe, every constraint operator, zero/one/overlap/conflict matches, all-excluded and 4,096/4,097 boundaries;
4. valid/invalid/self/terminal/closed-world state cases, duplicate/conflict logical keys, structural reachability and unreachable candidates;
5. missing-oracle metamorphism: candidate-ready never increases and its obligation remains;
6. absent versus empty `design_models`, exact legacy report equality, separate method candidate projection, atomic failed output, installed-wheel CLI, and process/network/adapter sentinels;
7. prohibited states/claims: no PASS, VERIFIED, approval, execution, external write, benchmark score, or superiority text.

Implementation ownership is disjoint: the engine developer owns `qa_master/design_methods.py` and engine tests; the integration developer owns `qa_master/campaign_cli.py`, user documentation/example fixture placement, and integration tests. Neither owner changes benchmark execution or the canonical Campaign schema in CR-010.

Material design rationale is recorded in [ADR-004](ADR-004-deterministic-structured-design-methods.md). This DRAFT is implementable guidance, not a Gate decision or evidence that any test has run.
