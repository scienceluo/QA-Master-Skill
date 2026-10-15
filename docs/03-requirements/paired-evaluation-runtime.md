# Paired-evaluation runtime requirements

- Artifact ID: `DOC-PAIRED-EVALUATION-RUNTIME-REQ-001`
- Document State: `DRAFT`
- Evaluation State: `IN_REVIEW`
- Change: `CR-011`
- Work: `TASK-039` / `work-587b299b6c8648ac9b381247df513ddf`
- Version: `0.7`
- Date: 2026-10-15

## Purpose and scope

`qa_master.benchmark` v1 validates submitted, human-rated artifacts; it does
not materialize participants or run a model.  CR-011 adds a separate local
paired-evaluation runtime that can make a real, explicitly requested Codex
model call and preserve its observed artifacts.  The old validator remains
compatible and is not the runtime's raw-run schema.

This work is needed to move from a validator-only benchmark toward actual
paired evidence.  The current user direction authorizes necessary local model
test calls for that purpose.  It does not authorize enterprise actions,
enterprise credentials, Jira/SynapseRT/GitLab writes, remote workers, or an
automatic run when a manifest is parsed, validated, materialized, or graded.

An actual pilot may use the same configured model alias and settings for both
arms when an exact provider model revision cannot be obtained.  Such a pair is
explicitly `EXPLORATORY`, not a strict same-revision comparison.  It cannot
support fairness, superiority, release, acceptance, human-rating, or aggregate
score claims.  No requirement here permits fabricating a provider revision,
system baseline attestation, participant output, score, or human rating.

Sources and rationale are `CR-011`, `REQ-011`,
`DOC-PAIRED-EVALUATION-PLAN-001`, `docs/BENCHMARK.md`, the existing
`qa_master.benchmark` source, and the current local Codex CLI observation.
They establish planning and a local runner opportunity, not a future provider
capability or security proof.

## Shared run contract

The future runtime uses a new strict `raw-run` schema, not benchmark submission
schema v1.  A run manifest has exactly two participant descriptors and exact,
versioned fields for:

- unique `run_id`, lane, and evaluation schema version;
- each participant's ID, source commit, tree hash, entry point, and every
  visible asset's relative path and SHA-256;
- a content-addressed common `visible_input` and neutral response-envelope
  schema; both arms receive byte-identical copies;
- Codex executable path, version, executable SHA-256, configured model alias,
  provider revision status/value, system-baseline status/value, canonical
  reasoning/settings, tool/sandbox/user-config policy, timeout, retry count,
  host metadata, and UTC timestamps;
- redacted command template, per-attempt status/classification, and an
  integrity ledger for retained outputs and transformations.

`visible_input` is a separate finite object containing only the pre-registered
scenario fields visible to both arms: scenario ID/title, request, known facts,
scope, and other explicitly permitted neutral fields.  Evaluator-only oracle,
traceability/coverage answer keys, grader fixtures, human-rating material, and
holdout paths never enter an arm root, prompt, common response envelope, or
visible-asset list.  A public development pilot may use a public oracle, but
it remains physically separate and is not passed to either arm.  A holdout is
held by an independent evaluator until both participant versions are frozen;
only its commitment hash may be visible beforehand.

The response envelope is neutral and capable of holding free-form participant
output plus declared references; it cannot demand QA-Master-specific campaign
fields or upstream-specific Skill wording.  The only permitted arm difference
is the separately materialized, content-addressed participant asset set.

The runner creates a new evaluation root and refuses existing `run_id`, path
traversal, symlink escape, duplicate JSON key, non-finite number, unknown
member, or out-of-root artifact path.  It uses atomic creation/writes.  Limits
are 2 participants, 64 visible assets/arm, 2 MiB total visible assets/arm,
2 MiB each for visible input and envelope, 2 MiB per retained output artifact,
6 MiB per constructed prompt, 1–1,800 seconds per arm, and `retry_count: 0`;
a limit failure starts no model process.  No credential, cookie, token, private key, environment
value, full presigned URL, or arbitrary process environment dump is permitted
in a manifest, command line, prompt, trace, or report.  Known secret-shaped
controlled fields are rejected and their values redacted; this is not a claim
to detect every secret embedded in arbitrary prose.

`--sandbox read-only`, an arm current directory, and absence of `--add-dir`
are recorded tool policies that restrict writes.  They do **not** prove OS read
isolation from parent/sibling paths, network isolation, or absence of all
unobserved access.  The runtime records this limitation as
`WRITE_RESTRICTED_READ_SCOPE_UNVERIFIED`.  A trace-observed prohibited tool
call is a policy violation; lack of a trace-observed call is only
`OBSERVED_NOT_SEEN`, never an OS-security proof.

## Requirements

### REQ-019 — immutable provenance preflight

| Item | Requirement |
|---|---|
| Source / rationale | `REQ-011` and `DOC-PAIRED-EVALUATION-PLAN-001` require a reviewable, paired input rather than unbound output files. |
| Priority | P1 |
| Preconditions | An explicit local evaluation command supplies a new run root and a complete raw-run manifest. |
| Inputs | Two participant descriptors, source/asset bytes, visible-input bytes, response-envelope schema bytes, runtime/model policy, and an empty run ID. |
| Expected behavior / output | Before any model process, hash every declared source-visible asset, visible input, envelope, executable, and canonical settings; compare every value to the manifest; then create a sealed preflight record or a typed failure with zero attempts. |
| Normal flow | Both participant descriptors, the same visible-input hash, envelope hash, configured model alias, settings, tool policy, timeout, and retry policy are retained in the preflight record. Source and asset drift is detected before materialization. |
| Error / exception flow | Missing/unknown/duplicate fields, duplicate JSON keys, `NaN`/infinity, hash mismatch, missing executable, invalid path, invalid size, nonempty existing run ID, or any required provenance status not declared causes `PRECHECK_REJECTED` and starts no model. |
| Boundary conditions | Provider revision and system baseline may be explicitly `NOT_AVAILABLE`/`UNVERIFIED` for an exploratory pilot; they are never synthesized from a model alias. A strict comparable run requires them both `VERIFIED`. |
| Dependencies / constraints | New raw-run schema only; no mutation of current benchmark submissions or manifest. |
| Acceptance criteria | (1) A one-byte asset/input/settings change fails before process start. (2) Two arms with unequal visible-input/envelope bytes fail preflight. (3) Unknown provider revision is preserved as unknown, not replaced. (4) An existing run ID is never overwritten. |
| Verification method | Independent malformed-manifest, hash-drift, duplicate-key, path, and process-sentinel fixtures; inspect exact preflight ledger and zero process-spawn count. |

### REQ-020 — neutral materialization and visible-input separation

| Item | Requirement |
|---|---|
| Source / rationale | The paired plan requires common output without leaking evaluator answer keys or giving either arm undocumented help. |
| Priority | P1 |
| Preconditions | REQ-019 preflight has succeeded and evaluator-only material is available outside both arm roots. |
| Inputs | One common visible-input object, one neutral envelope schema, and two participant-specific visible asset collections. |
| Expected behavior / output | Materialize two fresh arm roots containing byte-identical common input/envelope and only that arm's declared participant assets. Record every copied byte hash and the evaluator-only commitment hash. |
| Normal flow | The same neutral prompt is generated solely from visible input plus the common envelope. Participant instructions are included only through each arm's hashed asset set. |
| Error / exception flow | Any registered evaluator-only oracle/answer-key/holdout path, known byte hash, or fixture marker in an arm root, prompt, visible-input field, or envelope is `EVALUATOR_LEAKAGE`; materialization fails before a model call. Missing or mismatched common content also fails. This is a verifiable inventory/hash boundary, not a claim to recognize every semantically equivalent answer. |
| Boundary conditions | Public development oracle files remain outside arms; a holdout may expose only a commitment hash. Free-form output is allowed when it fits the neutral envelope. |
| Dependencies / constraints | Directory separation and read-only sandbox are recorded controls, not an assertion of read isolation; no claim may say that an arm could not read unobserved parent/sibling data. |
| Acceptance criteria | (1) Common files have equal byte hashes in both roots. (2) Asset inventories exactly match the manifest per arm. (3) Injection fixtures for oracle/holdout paths are rejected. (4) The neutral envelope accepts both a structured product artifact reference and a free-form Skill response. |
| Verification method | Independent arm-tree inventory/hash oracle, leakage/path-traversal fixtures, and neutral-envelope compatibility fixtures. |

### REQ-021 — explicitly invoked bounded local Codex pair runner

| Item | Requirement |
|---|---|
| Source / rationale | CR-011 needs actual output evidence; validation, materialization, and grading must remain non-executing operations. |
| Priority | P1 |
| Preconditions | REQ-019/020 succeeded; the user or an explicitly invoked local `run` command requests the pair; both arms use the registered same configured alias/settings. |
| Inputs | Sealed preflight record, two materialized arm roots, local Codex executable, timeout 1–1,800 seconds, `retry_count: 0`. |
| Expected behavior / output | Invoke `codex exec` once per arm, sequentially in the pre-registered arm order, without `--add-dir` and with the recorded read-only sandbox/user-config/tool policy, JSONL trace and last-message output paths. Preserve actual start/end times, exit code, trace/final/stderr bytes or their absence, and each artifact hash. |
| Normal flow | An exploratory pilot declares at least three scenarios, one each for boundary, decision-table, and state-transition design. It attempts one complete pair per scenario (six bounded calls total, one per arm/scenario) and records each pair's `AB` or `BA` order; a documented infrastructure/policy stop may leave later calls `NOT_EXECUTED` without synthesizing them. No validator, plan, materializer, status, or grader command can invoke Codex. A strict-comparison profile requires at least two complete attempts with both `AB` and `BA` order, retaining every attempt. The exact command shape is redacted and retained without credentials. |
| Error / exception flow | Spawn error, executable failure, timeout, attempted process-tree termination result, nonzero exit, missing final message, malformed trace/envelope, and trace-observed forbidden tool call receive distinct typed observations. There is no automatic retry, resubmission, hidden fallback model, or output synthesis. |
| Boundary conditions | A timeout records `process_outcome: TIMED_OUT` and an independent termination outcome; it does not imply successful kill. A nonzero exit alone is `RUN_FAILURE_UNATTRIBUTED` unless evidence supports a narrower class. Exit zero records `process_outcome: EXITED_ZERO`; it derives terminal `COMPLETED_PROCESS` only if no higher-priority evidence/output/policy classification applies, and never implies a quality pass. |
| Dependencies / constraints | Uses local Codex only; no enterprise integration, remote target, or external write is part of either arm. |
| Acceptance criteria | (1) Explicit run performs exactly two bounded invocations per attempted scenario and six calls when all three pilot scenarios complete; a validation-only command performs zero. (2) Timeout/no-final/malformed-trace/nonzero/spawn fixtures retain their actual artifacts and distinct classifications. (3) Retry count remains zero across all outcomes. (4) Captured model aliases/settings are equal across arms. |
| Verification method | Test double for launcher/process-clock plus a separately authorized real local pilot; inspect attempt ledger, command redaction, traces, hashes, and process-sentinel count. |

### REQ-022 — integrity-preserving evidence and failure classification

| Item | Requirement |
|---|---|
| Source / rationale | Process completion and tool absence are insufficient evidence; failures must be auditable without exposing secrets. |
| Priority | P1 |
| Preconditions | A preflight or pair-run command has been requested. |
| Inputs | Manifest/preflight bytes, copied assets, command metadata, raw stream files, final response, and redaction policy. |
| Expected behavior / output | Retain a content-addressed ledger for every permitted artifact: relative path, byte length, SHA-256, capture status, timestamps, and redaction transformation. Never replace an observed failure artifact with a synthetic success artifact. Preserve four orthogonal fields: `process_outcome` (`NOT_STARTED`, `SPAWN_FAILED`, `EXITED_ZERO`, `EXITED_NONZERO`, or `TIMED_OUT`), `termination_outcome` (`NOT_REQUESTED`, `TERMINATION_OBSERVED`, or `TERMINATION_UNCONFIRMED`), `output_outcome` (`NOT_AVAILABLE`, `COMPLETE`, `OUTPUT_INVALID`, or `INTEGRITY_FAILURE`), and `policy_outcome` (`NOT_EVALUATED`, `POLICY_VIOLATION_OBSERVED`, or `NO_VIOLATION_OBSERVED`). |
| Normal flow | The derived terminal attempt status is deterministic and never discards those fields. Its priority is `PRECHECK_REJECTED` (no spawn), `INFRASTRUCTURE_FAILURE`, `TIMED_OUT`, `POLICY_VIOLATION`, `OUTPUT_INVALID`, `PARTICIPANT_FAILURE` (only an observed participant-declared failure), `RUN_FAILURE_UNATTRIBUTED`, then `COMPLETED_PROCESS`. If a process started and reached an output stage but a required final response or trace is absent, it retains `output_outcome: NOT_AVAILABLE` and derives `OUTPUT_INVALID` unless a higher-priority status applies. `NOT_AVAILABLE` before output stage (for example, no spawn) does not independently derive `OUTPUT_INVALID`. Thus exit zero plus malformed or required-missing output remains `process_outcome: EXITED_ZERO` with terminal `OUTPUT_INVALID`; exit zero plus an observed forbidden tool call retains both facts with terminal `POLICY_VIOLATION`. |
| Error / exception flow | Artifact write/hash/redaction failure is `INFRASTRUCTURE_FAILURE`; a malformed response is `OUTPUT_INVALID`; a trace-observed disallowed tool call is `POLICY_VIOLATION`. If a stream cannot be retained because it contains prohibited sensitive material, retain its original byte hash, redaction reason, and safe replacement locator, never the sensitive bytes. |
| Boundary conditions | Empty stderr or absent final output is recorded distinctly. Missing observable evidence never becomes `PARTICIPANT_FAILURE`, `PASS`, `SECURE`, or `ISOLATED`. Partial artifacts remain traceable after a failed run. |
| Dependencies / constraints | Artifact root containment, atomic writes, and size limits in the shared contract apply. No raw environment dump, authorization token, or model-provider credential is captured. |
| Acceptance criteria | (1) Every retained permitted artifact has a hash and path under the run root. (2) Injected write/hash/redaction failures classify correctly and leave prior finalized files intact. (3) Success exit and no-tool-call fixtures cannot produce quality/security claims. |
| Verification method | Independent fault injection, artifact-ledger reconciliation, sensitive-marker redaction fixtures, and claim/status negative assertions. |

### REQ-023 — separate objective assertions from human assessment

| Item | Requirement |
|---|---|
| Source / rationale | Deterministic test-design assertions are objectively checkable; human quality judgments require independent people and must not be fabricated. |
| Priority | P1 |
| Preconditions | A response passes the neutral envelope parser and an evaluator-supplied assertion bundle is available outside arm roots. |
| Inputs | Versioned assertion IDs, typed expected canonical values, evaluator-only oracle references, anonymous response artifacts, and parser version/hash. |
| Expected behavior / output | The script grader emits one record per assertion: `SATISFIED`, `VIOLATED`, or `UNSCORABLE`, each with an evidence pointer. It evaluates typed values and references, never substring/keyword presence alone. Grader output is stored separately from raw run artifacts and any human-review record. |
| Normal flow | Exact boundary/domain, decision-universe, state-transition, provenance, and envelope assertions can be objectively reported; absent/ambiguous input yields `UNSCORABLE`. |
| Error / exception flow | Unknown assertion grammar, parser mismatch, or unavailable oracle bundle produces a typed grading failure/`UNSCORABLE`, not a score, inferred assertion, or fabricated expected value. |
| Boundary conditions | This CR contains no human-rating execution. Human-rating fields are absent or `NOT_EXECUTED`; any supplied rating/aggregate/superiority field is rejected from the raw-run result. |
| Dependencies / constraints | Anonymization for a later human review is separate work. A script grade is neither a human judgment nor a strict cross-product quality conclusion. |
| Acceptance criteria | (1) Equivalent textual phrasing without required typed evidence does not satisfy an assertion. (2) Missing oracle is `UNSCORABLE`. (3) Grader output cannot contain ratings, aggregate score, or superiority claim. |
| Verification method | Independent assertion corpus with canonical-value, parser-failure, and keyword-only adversarial fixtures; schema/claim negative tests. |

### REQ-024 — exploratory pilot and strict-comparison boundary

| Item | Requirement |
|---|---|
| Source / rationale | The user goal requires real progress, while REQ-011 forbids treating an unknown provider revision as a fair same-model result. |
| Priority | P1 |
| Preconditions | An exploratory pilot declares at least three scenarios, one boundary, one decision-table, and one state-transition case, with identical configured alias, canonical settings, visible-input/envelope hashes, declared policy, and retained per-attempt artifact ledger. A strict-comparison profile additionally has at least two retained completed attempts, one `AB` and one `BA`. |
| Inputs | Completed raw-run result plus provider-revision/system-baseline evidence states. |
| Expected behavior / output | If both provider revision and system baseline are `VERIFIED` equal values and all strict preflight conditions hold, emit `STRICT_COMPARABILITY_CANDIDATE` for later human protocol review only. If either is `NOT_AVAILABLE`/`UNVERIFIED`, allow an actual pair but label its evidence class `EXPLORATORY_CONFIGURED_SAME_MODEL`. |
| Normal flow | Exploratory output names the configured alias/settings and missing attestation, preserves actual outputs/classifications, and returns `claim_status: NOT_ASSERTED` with `human_rating_status: NOT_EXECUTED`. |
| Error / exception flow | Different configured aliases/settings/common hashes/policies prevent the pair from being labelled configured-same-model. Missing model call/output remains a failed or partial pilot; it is not simulated. |
| Boundary conditions | Provider/model family aliases, user-entered labels, matching exit codes, artifact hashes, no observed tool call, script assertions, and local test counts cannot themselves establish exact model revision, fairness, quality superiority, safety, or OS isolation. |
| Dependencies / constraints | A strict comparison still requires the complete REQ-011 protocol, independently held holdout, completed blinded human ratings, adjudication, and a human decision; those are outside CR-011. |
| Acceptance criteria | (1) Unknown provider revision permits only the exploratory evidence class. (2) Strict label requires verified equal revision and system-baseline records. (3) Neither output class permits an automatic score or superiority conclusion. (4) A real pilot record proves two actual calls or honestly records why it did not. |
| Verification method | Controlled manifest fixtures for verified/unknown/mismatched revision state, plus a separately authorized real pilot evidence audit. |

### NFR-006 — local safety, containment, and explicit non-execution

| Item | Requirement |
|---|---|
| Source / rationale | `NFR-003`, `NFR-004`, and CR-011 scope. |
| Priority | P1 |
| Preconditions / inputs | Any runtime command and run-manifest path. |
| Expected behavior / output | Only explicit local pair-run commands may invoke Codex. Preflight, validate, materialize, inspect, and grade remain non-executing. All artifact paths remain under a new run root; the runtime rejects escape/symlink/overwrite and records read-only sandbox limits accurately. |
| Normal / error / boundary flow | Controlled secret fields and unsafe paths fail closed before launch; unknown semantic secrets remain caller responsibility and must not be represented as protected. Enterprise endpoints/credentials/actions are unsupported input and reject before launch. |
| Measurable acceptance / verification | Command-to-spawn matrix, root-containment/symlink fixtures, secret-marker redaction checks, and assertions that no output says sandbox policy proves OS read/network isolation. |

### NFR-007 — reproducible provenance and bounded resource use

| Item | Requirement |
|---|---|
| Source / rationale | Paired evaluation needs reviewable evidence without unbounded local cost. |
| Priority | P1 |
| Preconditions / inputs | Any accepted raw-run manifest. |
| Expected behavior / output | Canonical manifest/asset/hash ledgers, recorded arm order, timestamps, limits, and zero retry count make every actual attempt reproducible enough to audit. Missing facts are explicitly `NOT_AVAILABLE`, `UNVERIFIED`, `NOT_EXECUTED`, or `OBSERVED_NOT_SEEN`. |
| Normal / error / boundary flow | The shared 2/64/2-MiB/1,800-second limits apply; exceeding one fails before or at its documented attempt boundary without automatic continuation. |
| Measurable acceptance / verification | Repeated-manifest canonical-byte test, limit-boundary fixtures, and ledger reconciliation against retained artifacts. These are not performance, cost, or availability guarantees. |

### NFR-008 — no fabricated ratings, fairness, or superiority conclusion

| Item | Requirement |
|---|---|
| Source / rationale | `REQ-011` and the paired-evaluation research boundary. |
| Priority | P1 |
| Preconditions / inputs | Any raw-run, grading, or exploratory-pilot output. |
| Expected behavior / output | Output has no human rating/aggregate score by default, preserves human rating as `NOT_EXECUTED`, and fixes `claim_status` to `NOT_ASSERTED`. It explicitly distinguishes objective script assertions from a later human review. |
| Normal / error / boundary flow | Attempts to submit synthetic ratings, infer quality from exit/schema/tool absence, or state that QA Master is better are rejected with a typed claim-policy error. |
| Measurable acceptance / verification | Negative claim/rating fixtures and an output-schema scan prove absence of automatic rating, fairness, benchmark winner, release, or acceptance fields. |

## Ambiguities retained for architecture

1. The exact raw-run manifest and neutral-envelope JSON schemas, command flags,
   redaction transformation format, and assertion DSL require an architecture
   decision; their semantic contracts and acceptance bounds are defined here.
2. Codex may not expose a provider-attested revision, system baseline, or OS
   read/network isolation evidence.  This does not block an exploratory actual
   pair, but it blocks strict comparability.
3. An exploratory pilot requires three declared method scenarios (boundary,
   decision table, state transition), attempts one `AB` or `BA` pair for each,
   and records all six calls or the typed reason later calls were not executed.
   A strict profile requires at least two retained attempts counterbalanced as
   `AB` and `BA`; the runtime never silently reorders, excludes, or retries
   attempts.
4. Human ratings, holdout release, adjudication, aggregates, and any superiority
   conclusion remain separate human-controlled work after a frozen pair.

## Completeness and conflict check

The requirements cover immutable participant/runtime/scenario provenance,
neutral common input, evaluator-only oracle separation, bounded explicit local
Codex calls, atomic artifact integrity, real failure classification, objective
assertions, exploratory evidence, strict-comparison conditions, and the
prohibition on fabricated human ratings or superiority.  They are consistent
with REQ-011 and do not authorize enterprise operations.  This is a DRAFT
requirements baseline only: no model call, pair, score, rating, approval,
comparison result, or Gate decision has occurred in TASK-039.
