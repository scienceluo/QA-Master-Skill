# Structured test-design methods requirements

- Artifact ID: `DOC-REQ-TEST-DESIGN-001`
- Document State: `DRAFT`
- Evaluation State: `IN_REVIEW`
- Change: `CR-010`
- Work: `TASK-032` / `work-cbd90ab4feec47fa8b1ed7515b2928fe`
- Version: `0.4`
- Date: 2026-10-15

## Purpose and evidence boundary

QA Master currently produces one requirement-by-dimension draft case and can
record a supplied negative case.  It does not implement specialized boundary,
decision-table, or state-transition synthesis.  This increment defines an
original, deterministic, local test-design capability for those three finite
models.  It advances the product's method depth; it does not establish that
QA Master is better than Awesome QA Skills.

Sources and rationale:

- `CR-010`, `PRD-001`, `REQ-005`, and the observed current
  `qa_master/generator.py`, `qa_master/coverage_design.py`, and
  `qa_master/campaign_cli.py` interfaces;
- `TASK-031` research draft `docs/01-research/competitor-analysis.md`: the
  pinned comparator exposes boundary/decision/state guidance, while counts of
  directories, prompts, or tests are not a quality comparison;
- `REQ-011`: no superiority conclusion is allowed without its separately
  controlled paired evaluation.

All output from this increment is `DRAFT_UNAPPROVED` and `NOT_EXECUTED`.
A candidate, coverage percentage, structural reachability result, schema
validation, or a passing local test never records requirement approval, a
business result, execution, defect closure, benchmark score, or Gate result.

## Shared contract

The future pure API is provisionally named `design_methods(bundle)` and is
fed from optional `bundle.design_models`.  Each model has a stable `id`, a
method (`boundary`, `decision_table`, or `state_transition`), one or more
existing requirement IDs, and typed source and oracle links.  The final API
name is a design decision, but these input/output semantics are requirements.

A `source_ref` is a strict object with `id`, `kind`, and `locator`; an
`oracle_ref` is either that object or explicit JSON `null`.  A non-null `id`
is unique within its link namespace and must resolve to the model registry;
an omitted/null oracle is an accepted `ORACLE_MISSING` obligation, whereas a
malformed or unknown non-null oracle reference rejects the bundle.  A locator
is a non-secret local/opaque label, not a URL or document payload: its exact
restricted grammar is an architecture decision, and it must reject absolute
paths, URL schemes, userinfo, query, fragment, and known credential-shaped
field names.  Callers must provide non-secret labels.  Links are references,
not imported or executed documents.  Every emitted candidate must contain sorted unique
`trace` requirement IDs, its model ID, its method, source links, oracle links,
`evidence_state: "PENDING"`, and `validation_action: "NOT_EXECUTED"`.

The input and result use canonical JSON: object keys sorted, UTF-8, no
duplicate object keys, no `NaN`/`Infinity`, and no JSON floating-point
numbers.  Supported scalar values are `string`, `boolean`, and signed
integer; decimal values use only the canonical decimal-string form defined by
REQ-014.  Results have stable, sorted case IDs derived only from canonical
model content and candidate identity.  Repeating the same accepted bundle in
the same product version yields byte-identical canonical method results.

Typed gaps and obligations have a stable `code`, `model_id`, affected links,
and a `status` of `PENDING`, `NOT_AVAILABLE`, `NOT_EXECUTED`, or
`UNASSESSED`.  They must not be represented as a fabricated case or silently
removed from a coverage denominator.

Legacy campaign bundles without `design_models` retain their existing
`prepare_campaign` result fields and values: no synthesized methods field,
extra cases, changed case ID, or changed coverage result is introduced.  A
bundle with models adds a separately named method result and cannot alter the
legacy requirement-by-dimension cases.

## Requirements

### REQ-013 — strict method-model intake and traceability

| Item | Requirement |
|---|---|
| Source / rationale | `CR-010`; current generic design lacks method-specific, reviewable links. |
| Priority | P1 |
| Preconditions | Bundle is a JSON object; each referenced requirement is present in the bundle with a stable ID. |
| Inputs | Optional `design_models`, requirement records, `source_ref` and `oracle_ref` registries. |
| Expected behavior / output | Validate model type, unique IDs, typed finite values, known requirement links, and link uniqueness before synthesis. Return canonical input digest, ordered model results, draft candidates, coverage obligations, and typed gaps. |
| Normal flow | Accept a valid finite model, preserve its explicit references, and produce only deterministically ordered draft artifacts. |
| Error / exception flow | Reject malformed JSON, duplicate IDs/keys, unknown requirement/source IDs, malformed or unknown non-null oracle IDs, JSON float, unsupported scalar, missing required fields, or limits before generating a partial result. An allowed null oracle instead yields `ORACLE_MISSING` and no candidate for its class. Return a stable typed validation error; do not invoke a runner, network client, or external adapter. |
| Boundary conditions | Empty `design_models` is valid and preserves legacy output. A model with zero candidates is valid when its coverage result names the reason. Maximum model count is 100; each identifier is 1–128 ASCII letters, digits, `_`, `-`, `.`, or `:`. |
| Dependencies / constraints | Extends `campaign_cli` and the existing draft case model; it is pure local processing and does not resolve links. |
| Acceptance criteria | (1) Same valid input produces exactly equal canonical bytes and ordered IDs across two fresh processes. (2) Every candidate has complete source/oracle/requirement links. (3) Invalid input returns a documented error with zero candidates and no external side effect. (4) A legacy bundle returns its existing v1 report shape and values. |
| Verification method | Independent fixture corpus: canonical-order/restart comparison, malformed-link/float/duplicate tests, legacy-report equality, and side-effect sentinel that fails on network, runner, or adapter call. |

### REQ-014 — finite integer and decimal boundary synthesis

| Item | Requirement |
|---|---|
| Source / rationale | `CR-010`; boundary coverage must be exact rather than a generic positive/negative placeholder. |
| Priority | P1 |
| Preconditions | A boundary model has valid `source_ref`; valid/invalid class oracle references may be explicit JSON `null`. |
| Inputs | `numeric_type` (`integer` or `decimal`); `origin`; positive `step`; lower/upper bounds; each bound's inclusivity; explicit precision/scale for decimal; domain and class oracle links. |
| Expected behavior / output | Construct only the finite grid candidates at, immediately inside, and immediately outside each declared bound; classify them as in-domain or out-of-domain; deduplicate and sort them by exact numeric order and canonical case ID. Emit a draft candidate only when its class has an explicit oracle; otherwise emit an oracle-missing obligation. |
| Normal flow | Exact integer arithmetic is used for `integer`. Decimal strings are parsed and calculated with exact `Decimal` arithmetic, with no binary float conversion. For decimal, `precision` is a maximum significant-digit count (1–34) and `scale` is the maximum fractional-digit count (0–18), so its representable grid is the multiples of `10^-scale`. A value is representable only when it has no more than `scale` fractional digits and does not exceed `precision`. Bounds and candidates must also lie on `origin + n × step`. Stored decimal text is canonical: a scale-2 value `1.20` is supplied and rendered as `1.2`; `-0` is supplied and rendered as `0`. |
| Error / exception flow | Reject boolean numeric values, float/`NaN`/infinite values, empty or noncanonical decimal strings, `step <= 0`, missing precision/scale, unsupported precision, lower above upper, or a non-grid/nonrepresentable bound with a stable error such as `BOUNDARY_MODEL_INCOMPLETE`. |
| Boundary conditions | One single interval has at most six unique candidate points (outside, bound, inside at each end); a point bound, open/closed bounds, a one-step domain, and a candidate falling outside the declared representable precision/scale range are all explicit cases. Decimal strings have no exponent or `+`, no leading zero except `0`, no redundant fractional trailing zero, and normalize negative zero to `0`. A zero-candidate model retains an honest zero denominator. |
| Dependencies / constraints | No free-form business-rule inference, HTTP status inference, error-text inference, SLA, nonnumeric domain, or value fuzzing is included. |
| Acceptance criteria | (1) Integer and decimal fixtures prove exact lower/upper open and closed behavior, including negative values and a decimal step. (2) No duplicate candidate ID or numeric value appears and the single-interval result never exceeds six points. (3) All emitted candidates have the exact input source and explicit class oracle link. (4) A null oracle yields an obligation and no candidate. (5) rejected values yield no partial candidate list. |
| Verification method | Independent deterministic oracle fixtures comparing the full ordered point/class/link tuple; malformed-grid and decimal lexical tests; maximum-six-point fixture; no-float static/runtime sentinel. |

### REQ-015 — finite decision-table synthesis

| Item | Requirement |
|---|---|
| Source / rationale | `CR-010`; finite decisions need observable gap and conflict analysis rather than sample cases treated as complete coverage. |
| Priority | P1 |
| Preconditions | Conditions have explicit finite domains and each rule has source and outcome references; its oracle reference may be explicit JSON `null`. |
| Inputs | Ordered conditions with unique IDs and strict finite scalar domains; optional declarative constraints; rules containing a partial `when` assignment, outcome ID, `oracle_ref`, and `source_ref`. |
| Expected behavior / output | Enumerate the Cartesian universe exactly once, apply only the safe declarative constraints, then classify each admissible assignment: zero matching rule is `DECISION_GAP`; exactly one matching outcome/oracle is `unique`; multiple matching rules with the same outcome and identical oracle reference set (including `{null}`) are `DECISION_OVERLAP`; divergent outcomes or divergent oracle reference sets are `DECISION_CONFLICT`. Report `universe_size`, `excluded`, `constraint_unevaluable`, `admissible`, `unique`, `overlap`, `conflict`, `gap`, `unique_oracle_ready`, `unique_oracle_missing`, `overlap_oracle_ready`, `overlap_oracle_missing`, and `oracle_ready`. |
| Normal flow | A rule matches only when all explicit `when` values equal the typed assignment values. Constraints are data declarations (equality, inequality, membership, and conjunction/disjunction of those declarations), never evaluated code or expressions. Equal-outcome overlaps with identical oracle sets retain all sorted source links and produce one deterministic candidate. A divergent outcome or oracle set is a conflict and produces no candidate. The counts must reconcile exactly: `universe_size = excluded + constraint_unevaluable + admissible`; `admissible = unique + overlap + conflict + gap`; `unique = unique_oracle_ready + unique_oracle_missing`; `overlap = overlap_oracle_ready + overlap_oracle_missing`; and `oracle_ready = unique_oracle_ready + overlap_oracle_ready`. |
| Error / exception flow | Reject empty/duplicate condition domains, floats, invalid condition values, invalid constraint grammar, rules referencing unknown conditions/values/oracles, or a Cartesian universe greater than 4,096 before enumeration. A constraint that cannot be evaluated is `DECISION_CONSTRAINT_UNEVALUABLE`, with no candidate and a separately reported denominator. |
| Boundary conditions | Domains may contain one value. A table with no rules reports every admissible assignment as a gap. Constraints that exclude all assignments report `admissible: 0`; no percentage or statement of completeness may be emitted. |
| Dependencies / constraints | This method neither samples a larger domain nor executes a predicate, service, or expression. It does not infer a default outcome or error oracle. |
| Acceptance criteria | (1) A fixture with the same inputs in different JSON key order returns the same ordered universe and candidate IDs. (2) Known gap, equal-outcome/same-oracle overlap, divergent-oracle conflict, and divergent-outcome conflict assignments yield their distinct typed outcomes. (3) Every coverage conservation formula in the normal flow reconciles exactly. (4) A >4,096 universe fails before any candidate is returned. |
| Verification method | Independent exhaustive small-table oracle corpus, boundary-size rejection test, constraint-grammar negative tests, and arithmetic reconciliation assertion for every reported count. |

### REQ-016 — explicit state-transition synthesis

| Item | Requirement |
|---|---|
| Source / rationale | `CR-010`; state models need explicit lifecycle and invalid-path semantics without a closed-world assumption. |
| Priority | P1 |
| Preconditions | Model declares one initial state, uniquely named states, and finite valid transition records with source and oracle links. |
| Inputs | `initial_state`; states with terminal flag and source links; valid transitions (`from`, `to`, trigger, optional guard reference, effect reference, source reference, oracle reference); explicit invalid transitions; optional `closed_world` and its shared deny oracle. |
| Expected behavior / output | Produce sorted valid-transition candidates; use an explicitly listed invalid transition only when it has a denial oracle; and report structural reachability of states/transitions from the initial state. Mark reachability `STRUCTURAL_ONLY`: guards/effects are not evaluated and it is not execution evidence. A valid/invalid transition logical key is `(from, trigger)`. Exact duplicate logical records with different record IDs yield one candidate plus `STATE_DUPLICATE`; divergent target/guard/effect/oracle or a valid/invalid key collision yields `STATE_CONFLICT` and no candidate for that key. Report unreachable states/transitions and duplicate/contradictory transition declarations as typed obligations. |
| Normal flow | Valid transitions are defined only by the supplied records. Missing invalid transitions remain unknown. If `closed_world: true`, the implementation may enumerate missing state/trigger pairs only from an explicit finite trigger set and only if one shared deny oracle is provided. |
| Error / exception flow | Reject no/multiple/unknown initial state, duplicate state/record ID, unknown transition endpoint, malformed or unknown non-null source/oracle/guard/effect link, a terminal state's outgoing valid transition, missing closed-world trigger set/deny oracle, or a completion universe above 4,096. A repeated logical key is handled as `STATE_DUPLICATE` or `STATE_CONFLICT` in the output rule, rather than rejecting unrelated valid keys. An unsupported or unevaluable guard is an obligation, not a transition outcome. |
| Boundary conditions | A one-state terminal model is valid and yields no valid transition. An isolated state is reported unreachable. Self-transition is valid only when explicitly supplied. An absent invalid transition is never inferred as forbidden while `closed_world` is absent or false. |
| Dependencies / constraints | Guards and effects are references only: no code, predicate, target, or UI is executed. State results do not claim service reachability, persistence, performance, security, or business correctness. |
| Acceptance criteria | (1) Valid, explicit invalid, missing-invalid, closed-world, terminal, self-loop, exact-logical-duplicate, divergent logical conflict, and unreachable fixtures have exact expected candidate/obligation sets. (2) All valid/invalid candidates retain explicit source and oracle links. (3) Structural reachability output is labeled and cannot be rendered as `EXECUTED`, `PASS`, or `VERIFIED`. |
| Verification method | Independent graph fixtures with expected sorted adjacency/reachability, invalid-completion limit test, and side-effect sentinel for guards/effects. |

### REQ-017 — honest method coverage and quality obligations

| Item | Requirement |
|---|---|
| Source / rationale | `REQ-005`, `REQ-011`, and `TASK-031`: design quality must be measurable from model obligations, never test/prompt/catalog count. |
| Priority | P1 |
| Preconditions | At least one accepted model result, including a reported method universe where applicable. |
| Inputs | Per-method candidates, typed gaps, conflict/overlap analysis, declared universe and model/link metadata. |
| Expected behavior / output | Report coverage only against the method's declared finite denominator and separate `candidate_ready`, `oracle_missing`, `conflict`, `gap`, `unevaluable`, `unreachable`, and `out_of_scope` obligations. A ratio is emitted only where the denominator is nonzero and fully defined; it has a named numerator/denominator and no `PASS` interpretation. |
| Normal flow | Preserve every unresolved assignment/transition/boundary class in deterministic order and return a method result even when it contains only obligations. |
| Error / exception flow | If an incomplete model prevents a denominator from being defined, return `UNASSESSED` with the typed cause; never substitute total generated cases, input row count, test count, prompt count, or catalog count. |
| Boundary conditions | Zero denominator, all-excluded decision universe, zero model candidates, and all-oracle-missing models retain a non-success state and explicit reason. |
| Dependencies / constraints | Does not score model semantics, product quality, or competitor performance. A future REQ-011 benchmark is a separate controlled activity with its own holdout and human rating evidence. |
| Acceptance criteria | (1) Each declared finite universe reconciles its classes exactly. (2) Undefined/zero denominators produce no percentage and an explicit non-success state. (3) Removing an oracle cannot increase `candidate_ready` or erase its obligation. (4) Result text and machine fields contain no superiority or execution conclusion. |
| Verification method | Metamorphic fixtures that remove rules/oracles and compare the complete obligation ledger; exact count reconciliation; prohibited-claim and prohibited-status assertions. |

### REQ-018 — campaign and installed-CLI draft integration

| Item | Requirement |
|---|---|
| Source / rationale | Current `campaign_cli` is the installed offline draft entry point; `REQ-003` and `NFR-004` require planning to remain non-executing. |
| Priority | P1 |
| Preconditions | User invokes the installed `python -m qa_master.campaign_cli` with a local JSON input/output path; the source file is within the existing size limit. |
| Inputs | Existing campaign bundle plus optional valid `design_models`. |
| Expected behavior / output | Incorporate the canonical method result into the campaign draft, preserving legacy output when models are absent. CLI summary names method candidate and obligation counts but always returns `status: DRAFT_UNAPPROVED`, `execution: NOT_AUTHORIZED`, and no external-system write status. |
| Normal flow | Read input once, validate/synthesize locally, atomically write an output file distinct from input, and print a redacted summary. The full output retains the input digest and links needed for later review. |
| Error / exception flow | Reject same input/output path, oversized or malformed input, and any method validation/limit error without replacing an existing output or creating a campaign, test-execution record, Jira/SynapseRT object, remote job, or network request. |
| Boundary conditions | No `design_models` preserves legacy behavior. Empty model list is valid. A valid bundle whose models yield only gaps still writes a draft with zero method candidates and all obligations. |
| Dependencies / constraints | Uses only local filesystem and existing atomic-write behavior. Controlled method-model fields named `password`, `token`, `cookie`, or `private_key` (including case-insensitive nested equivalents) are rejected and their values must not be echoed in CLI/report errors. This is schema-level protection, not a claim to detect arbitrary secret prose; callers must provide non-secret source/oracle labels. |
| Acceptance criteria | (1) Fresh installed-package CLI fixture with all three valid model types creates a draft-only report and no execution/external-write side effect. (2) Failed model input leaves a sentinel output unchanged. (3) Legacy fixture remains result-equal. (4) Secret-shaped method input is rejected without its value appearing in output. |
| Verification method | Independent installed-wheel CLI smoke, filesystem/network/adapter sentinels, atomic-output regression, secret-redaction negative fixture, and report-schema assertions. |

## NFR-005 — deterministic, bounded and safe local synthesis

| Item | Requirement |
|---|---|
| Source / rationale | `NFR-003`, `NFR-004`, CR-010 method limits. |
| Priority | P1 |
| Preconditions / inputs | Any accepted or rejected method bundle. |
| Expected behavior / output | The implementation is deterministic, makes no network/process/adapter call, rejects invalid/over-limit work before synthesis, and does not persist sensitive values from method models. |
| Normal / error / boundary flow | Limits are: 100 models, at most six boundary candidates per single-interval model, 4,096 decision assignments/model, 128 states/model, 512 explicit transitions/model, and 4,096 closed-world invalid pairs/model. Exactly-at-limit is supported for the finite input domains; one above is rejected with a stable limit code before partial output. |
| Dependencies / constraints | Local CPU/memory limits are not performance/SLA claims; timing, throughput, load, stress, and capacity remain `NOT_EXECUTED` until separately specified and run. |
| Measurable acceptance / verification | Independent limit fixtures, repeat-process canonical byte comparison, and sentinels proving no side-effect call and no prohibited secret value in emitted artifacts. |

## Ambiguities and decisions still required before implementation

1. `source_ref.kind` and `locator` controlled vocabularies need an architecture
   decision; this requirement only requires typed, preserved links.
2. Whether a boundary point outside the declared range uses one shared invalid
   oracle or separate lower/upper oracles is intentionally left to model input;
   no fallback is allowed.
3. Decision constraints are restricted to declared data grammar.  The exact
   grammar and canonical serialization must be fixed in design before coding.
4. Structural state reachability assumes referenced guarded edges are
   potentially satisfiable.  Semantic guard satisfiability is out of scope.
5. This document supplies no numeric SLA, professional-quality score, paired
   benchmark threshold, enterprise target, or human approval.  Those omissions
   are `NOT_AVAILABLE`/`NOT_EXECUTED`, not implementation defaults.

## Completeness and conflict check

The requirements define the three requested finite methods, exact sources and
oracles, deterministic ordering, coverage denominator, resource limits, error
behavior, campaign/CLI integration, legacy compatibility, secret handling, and
the draft-only boundary.  They do not conflict with `REQ-003`, `REQ-011`,
`NFR-003`, or `NFR-004`: every artifact remains local, non-authorizing, and
non-executing.  Architecture must next baseline the exact JSON schemas,
canonical ID algorithm, constraint grammar, and public module/API names before
an implementation task is released.
