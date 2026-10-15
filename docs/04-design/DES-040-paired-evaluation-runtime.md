# DES-040 — Paired evaluation runtime and exploratory pilot

- Artifact ID: `DES-040`
- Document State: `DRAFT`
- Evaluation State: `IN_REVIEW`
- Change / task: `CR-011` / `TASK-040`
- Requirements: `REQ-019`–`REQ-024`, `NFR-006`–`NFR-008`, and the retained `REQ-011` claim boundary
- Inputs: `DOC-PAIRED-EVALUATION-RUNTIME-REQ-001` v2, `DOC-PAIRED-EVALUATION-PLAN-001` v1, `DOC-PAIRED-EVALUATION-CLI-PREFLIGHT-001` v1, and the current `qa_master.benchmark` v1 contract
- Evidence boundary: this is an implementable design candidate. It records no model run, pair, score, rating, superiority, approval, acceptance, release, or Gate result.

## 1. Scope and component boundary

Add an installed, local-only module `qa_master.paired_evaluation`. It validates and materializes two content-addressed participant contexts, invokes the native Codex CLI only through an explicit `run` operation, preserves raw process evidence, and optionally applies exact machine assertions. It does not replace or silently upgrade `qa_master.benchmark`; the existing human-rated submission validator and its schema v1 remain compatible.

The module has five boundaries:

1. `ManifestLoader` performs strict JSON intake and canonicalization without starting a process.
2. `Materializer` verifies declared bytes and creates fresh arm trees without following links.
3. `CodexCliExecutor` is the only component allowed to start Codex and is called only by `run`.
4. `TraceParser` and `EnvelopeParser` preserve process facts separately from policy and output facts.
5. `AssertionGrader` consumes evaluator-held assertions after a run and never invokes Codex.

Campaign state, the structured-design engine, enterprise adapters, remote workers, credentials, human ratings, holdout release, and a superiority decision are outside this component.

## 2. Public interface and commands

```python
class PairedEvaluationError(ValueError):
    code: str

def load_run_manifest(payload: bytes, *, manifest_dir: str | os.PathLike[str]) -> dict: ...
def validate_run_manifest(payload: bytes, *, manifest_dir: str | os.PathLike[str]) -> dict: ...
def materialize_preview(manifest_path: str | os.PathLike[str],
                        evaluator_exclusions_path: str | os.PathLike[str],
                        preview_root: str | os.PathLike[str]) -> dict: ...
def run_pair(manifest_path: str | os.PathLike[str],
             evaluator_exclusions_path: str | os.PathLike[str],
             output_root: str | os.PathLike[str]) -> dict: ...
def inspect_run(run_root: str | os.PathLike[str]) -> dict: ...
def grade_run(run_root: str | os.PathLike[str],
              assertions_path: str | os.PathLike[str],
              output_path: str | os.PathLike[str]) -> dict: ...
```

`str(PairedEvaluationError) == error.code`; public errors contain a stable code and never echo input, local paths, environment values, stderr, prompts, or credentials. The public API and CLI expose no launcher, clock, or verifier injection. Internal tests may call a private `_run_pair_with_ports`; every non-native port stamps `execution_backend: TEST_DOUBLE`, `evidence_class: TEST_DOUBLE`, and `pilot_status: NOT_EXECUTED`. Such output cannot be promoted, copied, or reclassified into actual pilot evidence. The public path stamps `execution_backend: NATIVE_CODEX`, uses the real subprocess launcher and UTC clock, and has no attestation verifier in CR-011.

The additive CLI is `python -m qa_master.paired_evaluation` (and may be exposed as `qa-master-paired-eval`) with `validate`, `materialize`, `run`, `inspect`, and `grade`. Only `run` can call Codex. `validate`, `materialize`, `inspect`, and `grade` reject execution options and start no process of any kind. A preview materialization is marked `PREVIEW_NOT_RUN`, uses a caller-supplied new directory, and can never be promoted into a run root; `run` repeats preflight and materializes its own fresh roots. There is no automatic run on import, manifest load, validation, materialization, inspection, or grading.

## 3. Canonical JSON and path rules

All controlled JSON uses UTF-8, exact object-member sets, duplicate-key rejection, no BOM, no JSON float, and no `NaN`/infinity. Canonical bytes use sorted keys, compact separators, `ensure_ascii=False`, and one trailing LF only when saved as a file. SHA-256 is lowercase hexadecimal over the exact raw source bytes unless a field explicitly says `canonical_sha256`.

IDs match `[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}`. Relative paths use `/`, contain only nonempty segments matching `[A-Za-z0-9][A-Za-z0-9_.-]*`, and forbid `.`, `..`, drive/UNC prefixes, backslashes, schemes, query, fragment, userinfo, and NUL. Resolution checks every existing path component. Symlinks and Windows reparse points, including junctions, are rejected for sources, destinations, executable candidates, and all parents below the declared roots.

The controlled sensitive key set is case-folded exact membership in `password`, `passwd`, `token`, `access_token`, `refresh_token`, `api_key`, `authorization`, `cookie`, `private_key`, `client_secret`, `credential`, and `presigned_url`. Such a key is invalid anywhere in the manifest, visible input, response schema, or assertion bundle. The implementation does not substring-scan arbitrary prose and cannot claim that accepted prose is secret-free.

Limits are fixed in schema v1: exactly two participants; at most 64 assets per arm; at most 2 MiB for any asset, visible input, response schema, stream, or final artifact; at most 2 MiB total participant assets per arm; at most 6 MiB constructed stdin per call; 1–1,800 seconds per call; and `retry_count` exactly zero.

## 4. Raw-run manifest schema

The top-level object has exactly:

```json
{
  "schema_version": 1,
  "run_id": "RUN-EXAMPLE",
  "profile": "EXPLORATORY_CONFIGURED_SAME_MODEL",
  "created_at_utc": "2026-10-15T00:00:00Z",
  "participants": [],
  "scenarios": [],
  "prompt_template": {},
  "response_schema": {},
  "evaluator_commitment_sha256": "...",
  "runtime": {},
  "schedule": []
}
```

`created_at_utc` is an RFC 3339 UTC timestamp with whole seconds and the literal `Z`. `profile` is `EXPLORATORY_CONFIGURED_SAME_MODEL` or `STRICT_COMPARISON_CANDIDATE`. A manifest requesting the strict profile is rejected with `STRICT_PROFILE_NOT_SUPPORTED` unless an injected trusted verifier validates both provider revision and system baseline. User-entered labels or values cannot promote either attestation to `VERIFIED`.

### 4.1 Participants and assets

`participants` contains two entries, ordered by distinct `arm_id` values `A` and `B`. Each entry has exactly:

```json
{
  "arm_id": "A",
  "participant_id": "qa-master",
  "source": {
    "repository_id": "qa-master-skill",
    "commit": "40-or-64-lower-hex",
    "tree_oid": "40-or-64-lower-hex"
  },
  "entry_asset": "skills/qa-master/SKILL.md",
  "assets": [
    {
      "path": "skills/qa-master/SKILL.md",
      "source_path": "inputs/qa-master/SKILL.md",
      "media_type": "text/markdown",
      "byte_count": 123,
      "sha256": "..."
    }
  ]
}
```

`source_path` is relative to the manifest directory and is never placed in a prompt. `path` is the participant-visible logical path and materialization path. Assets are unique by `path`, sorted lexically, regular UTF-8 files, and restricted to `text/plain`, `text/markdown`, or `application/json`. `entry_asset` must be present. Linked or recursively referenced files are not auto-discovered; only listed bytes exist in the arm inventory. The Git values are provenance labels; exact asset hashes are the runnable identity. This slice supplies no remote Git fetch or signed Git attestation.

### 4.2 Scenarios, template, schema, and schedule

Each scenario has exactly `id`, `method`, `visible_input`, and `oracle_commitment_sha256`. `method` is `boundary`, `decision_table`, or `state_transition`. `visible_input` has `source_path`, `byte_count`, and `sha256`. Its strict object is:

```json
{
  "schema_version": 1,
  "scenario_id": "PE-BND-001",
  "method": "boundary",
  "title": "Finite boundary design",
  "request": "...",
  "known_facts": [{"id": "F-1", "text": "..."}],
  "scope": "...",
  "checks": [{"id": "Q-1", "question": "...", "value_type": "JSON"}]
}
```

Known-fact and check IDs are unique. Allowed check types are `BOOLEAN`, `INTEGER`, `DECIMAL`, `STRING`, `STRING_SET`, and `JSON`. The object cannot contain `oracle`, `expected`, `answer`, `rating`, `score`, or `winner` fields. Evaluator-only content remains outside the manifest directory and both arm roots; only its commitment hash is retained.

`prompt_template` and `response_schema` each have exactly `source_path`, `byte_count`, and `sha256`. Their files are transport copies, not caller-defined behavior: their bytes and digests must equal the module constants `PROMPT_TEMPLATE_V1` and `NEUTRAL_RESPONSE_SCHEMA_V1`. The response schema constant implements the exact envelope and limits in section 5 and rejects unknown members, ratings, scores, winners, evaluator expected-value fields, approvals, and execution claims; the explicitly declared `steps[].expected` test-behavior field remains allowed. The UTF-8 template constant contains exactly once each of `{{PARTICIPANT_CONTEXT}}`, `{{VISIBLE_INPUT}}`, and `{{RESPONSE_CONTRACT}}` and no other placeholder. The common template, visible-input bytes, and response-contract bytes are byte-identical across arms. A different schema or template is `COMMON_CONTRACT_MISMATCH` before launch; a schema-valid but later parser-invalid result remains `OUTPUT_INVALID`.

`evaluator_commitment_sha256` binds a separate evaluator-exclusion registry supplied to `materialize`/`run`. That registry must be outside the manifest directory and output root and has exactly:

```json
{
  "schema_version": 1,
  "forbidden_locators": ["holdout/answer-key.json"],
  "forbidden_sha256": ["..."],
  "fixture_markers": ["EVALUATOR_ONLY_FIXTURE_001"]
}
```

Locators use the controlled relative grammar, hashes are unique lowercase SHA-256 values, and fixture markers are unique printable ASCII synthetic sentinels of 16–128 characters. The registry contains no oracle value, expected answer, human rating, or secret. Its canonical hash must equal the manifest commitment before its fingerprints are used. It is never copied into a run/preview root, prompt, response contract, or ledger; the preflight records only its hash and match counts. This turns leakage checks into declared exact fingerprints rather than an impossible semantic-secret detector.

Each schedule row has exactly `attempt_id`, `scenario_id`, and `order`; `order` is `['A','B']` or `['B','A']`. An exploratory pilot contains at least three distinct scenarios covering all three methods exactly once or more and one schedule row per selected scenario. It therefore attempts six calls when all three pairs complete. A strict candidate needs at least two completed schedule rows with both orders represented. No operation reorders, excludes, replaces, or retries a row.

### 4.3 Runtime object

`runtime` has exactly:

```json
{
  "codex": {
    "executable_path": "C:/absolute/native/codex.exe",
    "executable_sha256": "...",
    "version": "codex-cli 0.162.0-alpha.17.2"
  },
  "model": {
    "alias": "gpt-6-astra",
    "reasoning_effort": "medium",
    "provider_revision": {"state": "NOT_AVAILABLE", "value": null, "evidence_sha256": null},
    "system_baseline": {"state": "UNVERIFIED", "value": null, "evidence_sha256": null},
    "temperature_state": "NOT_AVAILABLE",
    "seed_state": "NOT_AVAILABLE"
  },
    "policy": {
    "sandbox": "read-only",
    "add_dirs": [],
    "ignore_user_config": true,
    "ephemeral": true,
    "skip_host_skill_discovery": true,
    "requested_tool_policy": "NO_TOOL_USE",
    "disabled_features": [],
    "isolation_level": "WRITE_RESTRICTED_READ_SCOPE_UNVERIFIED",
    "response_schema_delivery": "PROMPT_AND_LOCAL_STRICT_PARSE"
  },
  "host": {"os": "Windows", "architecture": "AMD64"},
  "timeout_seconds": 600,
  "retry_count": 0
}
```

`executable_path` is a normalized absolute platform path with no environment expansion or URI syntax. On Windows, the executable is a regular non-reparse `.exe` with an `MZ` header. On POSIX, it is a regular non-symlink file with an execute bit and an ELF or Mach-O header. Batch files, PowerShell files, shell scripts, shebang wrappers, and other interpreter shims are rejected. Validation reads and hashes this file but never executes `--version`; `version` is an observed provenance label bound to the binary digest and CLI-preflight document. Only the explicit `run` command invokes this Codex binary, and every such invocation is one scheduled model call. A platform process-tree termination helper is a separately recorded operating-system action, not a Codex invocation.

Attestation `state` is `NOT_AVAILABLE`, `UNVERIFIED`, or `VERIFIED`. `VERIFIED` requires a non-null value and evidence digest returned by a configured verifier; the default runtime has none and rejects a manifest that merely claims `VERIFIED`. Exploratory execution accepts the first two states and preserves them.

The current CLI preflight did not verify provider support for this envelope as a strict `--output-schema`. Therefore schema v1 embeds the frozen contract in the prompt and validates the final bytes with the local exact parser; the command deliberately omits `--output-schema`. A future flag-enabled profile needs separate successful capability evidence, a design revision, and the same local parse after provider enforcement. The prompt contract is an instruction, not validation evidence.

For the observed CLI version, `disabled_features` is the sorted unique set `apps`, `browser_use`, `browser_use_external`, `code_mode_host`, `computer_use`, `hooks`, `image_generation`, `memories`, `multi_agent`, `plugins`, `shell_tool`, `skill_search`, `sleep_tool`, `unbounded_connection_retries`, `unified_exec`, and `view_image`. A changed executable/version requires a new observed capability record and manifest; accepted feature flags are requested controls, not proof that no unobserved capability exists.

## 5. Neutral participant context and response envelope

Copying files into an arm is not enough because host skill discovery and file tools are disabled. The materializer therefore produces a deterministic `participant_context` from every declared asset. Assets are ordered by logical `path`. The exact byte projection is `PARTICIPANT_CONTEXT_V1\n`, followed for each asset by `ASSET <path-byte-count> <content-byte-count> <sha256>\n`, the exact UTF-8 path bytes, `\n`, the exact content bytes, `\nEND_ASSET\n`, and finally `END_PARTICIPANT_CONTEXT\n`. Counts are base-10 ASCII without leading zero. No Markdown link, include, directory, or instruction causes recursive loading.

For each call, stdin is the exact template substitution:

```text
PARTICIPANT_CONTEXT := that arm's content-addressed projection
VISIBLE_INPUT       := the selected scenario's exact bytes
RESPONSE_CONTRACT   := the common response schema's exact bytes
```

Template substitution tokenizes the original frozen template once into four literal segments and inserts the three byte blocks; it never scans inserted asset/input/schema bytes for placeholders. Thus an asset containing `{{VISIBLE_INPUT}}` is ordinary content, not a second substitution. `common_request_bytes` is the canonical JSON object containing the template digest, visible-input digest, and response-schema digest; its hash is byte-identical between arms. The runner records participant-context, common-request, complete-stdin, and response-schema hashes. Complete stdin differs only because the registered participant context differs. This makes participant treatment observable without granting file-reading tools.

The neutral response JSON has exactly:

```json
{
  "schema_version": 1,
  "scenario_id": "PE-BND-001",
  "response_status": "COMPLETED",
  "summary": "User-facing QA design summary",
  "cases": [
    {
      "id": "C-1", "title": "...", "objective": "...",
      "preconditions": [], "data": [],
      "steps": [{"action": "...", "expected": "..."}],
      "source_refs": ["F-1"]
    }
  ],
  "gaps": [
    {"id": "G-1", "description": "...", "impact": "...",
     "needed_evidence": "...", "source_refs": ["F-1"]}
  ],
  "observations": [
    {"check_id": "Q-1", "value_type": "JSON", "value": "{}",
     "evidence_refs": ["F-1"]}
  ],
  "metadata": {"artifact_state": "DRAFT", "execution_state": "NOT_EXECUTED"},
  "failure_reason": null
}
```

`response_status` is `COMPLETED` or `PARTICIPANT_FAILURE`. A completed response has null `failure_reason`; a participant failure has nonempty reason and empty `cases`/`observations`. IDs are unique. Arrays are bounded at 128 cases, 128 gaps, 256 observations, 64 preconditions/data/source refs per row, and 64 steps per case. Strings are nonempty and at most 20,000 characters.

Observation `value` is always a string so the frozen schema needs no arbitrary-object escape hatch. Its `value_type` determines exact parsing: `BOOLEAN` is `true` or `false`; `INTEGER` is canonical base-10 text and rejects booleans/leading zero; `DECIMAL` is canonical finite plain-decimal text; `STRING` is the literal string; `STRING_SET` is compact canonical JSON for a sorted unique string array; and `JSON` is compact canonical JSON text with no float, maximum depth 16, and at most 4,096 nodes. Assertion expected values use the same encoding, so boolean true, integer 1, and string `1` remain different. Observation check IDs and types must match visible checks, and evidence refs must name visible fact IDs or declared participant asset paths. No rating, score, winner, quality grade, approval, execution result, or superiority field is permitted. The declared case-step member `expected` is user-facing test behavior, not an evaluator answer-key field.

## 6. Preflight, materialization, and leakage boundary

`run` first parses all controlled objects and reserves `<output_root>/<run_id>` with atomic exclusive directory creation. An existing name is `RUN_ID_EXISTS`; it is never resumed or overwritten. It then verifies source size/hash, native executable regular-file status/hash/version expectation, host fields, common content, limits, schedule, and the equality invariants before any model call.

The preflight record binds the canonical manifest SHA-256, every raw source hash, every materialized target hash, executable identity, model/settings, policy, host observation, and schedule. Materialization creates a distinct immutable call root for every `(attempt_id, scenario_id, arm_id)`; it contains only that scenario's `common/visible-input.json`, the shared `common/response.schema.json`, and that arm's `assets/` inventory. It never rewrites one logical arm root with the next scenario. Evaluator-only material is never copied.

Leakage detection is deliberately finite: it rejects exclusion-registry relative locators, exact known byte hashes, and registered synthetic fixture markers found in any call-root inventory, constructed prompt, visible input, or response schema. It does not claim to recognize a paraphrased or otherwise semantically equivalent answer. A leakage finding is `EVALUATOR_LEAKAGE` and starts no model.

Files are written with create-exclusive or temporary-file-plus-atomic-replace semantics and immediately re-read/hash-checked before sealing preflight. The run manifest, sealed preflight, materialized common bytes, and finalized attempt directories are append-only. A partial later call cannot alter an earlier finalized attempt.

## 7. Codex invocation and bounded capture

The executor resolves the manifest's native regular `.exe` directly; `.cmd`, `.bat`, `.ps1`, shell strings, and PATH substitution after preflight are rejected. It uses an argv list and `shell=False`. The current command shape is:

```text
codex.exe exec --ephemeral --sandbox read-only --skip-git-repo-check
  --ignore-user-config --model <alias>
  -c model_reasoning_effort=<effort> --json
  --output-last-message <absolute-attempt-final>
  <repeated --disable values> --enable skip_host_skill_discovery -
```

The current directory is a fresh empty per-call directory outside product, comparator, and evaluator roots. There is no `--add-dir`. Stdin holds the bounded constructed prompt. Environment policy `CODEX_ENV_V1` passes only these existing names when present:

- Windows, case-insensitive: `SYSTEMROOT`, `WINDIR`, `COMSPEC`, `PATH`, `PATHEXT`, `TEMP`, `TMP`, `USERPROFILE`, `LOCALAPPDATA`, `APPDATA`, `CODEX_HOME`, `SSL_CERT_FILE`, `SSL_CERT_DIR`, and `REQUESTS_CA_BUNDLE`;
- POSIX: `HOME`, `PATH`, `TMPDIR`, `LANG`, `LC_ALL`, `CODEX_HOME`, `SSL_CERT_FILE`, `SSL_CERT_DIR`, and `REQUESTS_CA_BUNDLE`.

Proxy variables, provider/API keys, generic credential/token variables, and every unlisted variable are dropped. The record contains only the sorted inherited names, policy ID, and canonical policy digest, never values or value hashes. Existing Codex authentication remains resolved by the native client from allowed home locations; the runtime does not copy, read back, print, or store it. If that reduced environment cannot authenticate, the attempt fails honestly; the runner does not widen inheritance.

Stdout JSONL and stderr are drained concurrently by bounded reader threads. Crossing a stream cap terminates the exact process tree and records an integrity failure; it cannot deadlock on a full pipe. `--output-last-message` points to an owner-private, per-call staging directory outside the append-only evidence tree. A concurrent size monitor requests termination if that file crosses 2 MiB; this is not an OS file-quota guarantee. After exit, the runner performs a bounded read, hashes/scans the bytes, and only then atomically writes a permitted raw or redacted final artifact into evidence. The staging file is removed in `finally`; cleanup outcome is `NOT_REQUIRED`, `DELETED`, or `DELETE_FAILED`. `DELETE_FAILED` is an infrastructure failure. Because the child writes staging directly, sensitive bytes may exist there transiently and deletion is not secure-erasure proof; the design does not claim they were never written.

POSIX uses a new session and signals only its process group. Windows creates a new process group and invokes the absolute System32 `taskkill.exe /PID <pid> /T /F` only for the captured PID if still alive. Termination command, return observation, and residual liveness check are recorded. Failure to prove termination is `TERMINATION_UNCONFIRMED`, not successful cleanup. No automatic retry or fallback model exists.

The versioned successful JSONL grammar is limited to TASK-045 observations rather than guessed provider events. `thread.started` has exactly `type`/nonempty `thread_id`; `turn.started` exactly `type`; a configuration-warning `item.completed` has exactly `type`/`item`, with item exactly `id`, `type: error`, and nonempty `message`; an agent response `item.completed` has exactly `type`/`item`, with item exactly `id`, `type: agent_message`, and nonempty `text`; and `turn.completed` has exactly `type`/`usage`. Usage has exactly the nonnegative integer members `input_tokens`, `cached_input_tokens`, `cache_write_input_tokens`, `output_tokens`, and `reasoning_output_tokens`.

Any observed `item.started` or `item.completed` whose item type is not `error` or `agent_message` is recorded first as a trace-observed tool-policy violation; its remaining payload is retained under the stream policy but is not assigned a guessed schema or trusted as an envelope. Every other unknown outer type/member set is `TRACE_SCHEMA_UNSUPPORTED`. The successful order is one `thread.started`, zero or more configuration-warning completions, one `turn.started`, exactly one agent-message completion, and one `turn.completed`. The two observed configuration warnings (`skip_host_skill_discovery` under development and code mode unavailable) and the observed PowerShell shell-snapshot stderr diagnostic are preserved as warnings, not treated as fatal by text or `item.type=error` alone. Malformed JSON, invalid order/cardinality, missing lifecycle events, or unsupported schema makes policy observation unavailable and output invalid. `NO_VIOLATION_OBSERVED` means only that this parser saw none. Nonzero/failed provider event shapes not observed in TASK-045 are retained raw and classified unsupported rather than invented in this design.

## 8. Attempt record, terminal status, and artifact ledger

Every planned call has an immutable attempt identity `(attempt_id, scenario_id, arm_id, ordinal)`. Its record preserves UTC start/end, monotonic duration, argv template with paths redacted, prompt hashes, PID, exit code, timeout, termination observations, stream/final hashes, trace warnings, token-usage fields if present, and these four orthogonal outcomes:

- `process_outcome`: `NOT_STARTED`, `SPAWN_FAILED`, `EXITED_ZERO`, `EXITED_NONZERO`, or `TIMED_OUT`;
- `termination_outcome`: `NOT_REQUESTED`, `TERMINATION_OBSERVED`, or `TERMINATION_UNCONFIRMED`;
- `output_outcome`: `NOT_AVAILABLE`, `COMPLETE`, `OUTPUT_INVALID`, or `INTEGRITY_FAILURE`;
- `policy_outcome`: `NOT_EVALUATED`, `POLICY_VIOLATION_OBSERVED`, or `NO_VIOLATION_OBSERVED`.

The derived terminal attempt status uses this priority: `PRECHECK_REJECTED`, `INFRASTRUCTURE_FAILURE`, `TIMED_OUT`, `POLICY_VIOLATION`, `OUTPUT_INVALID`, `PARTICIPANT_FAILURE`, `RUN_FAILURE_UNATTRIBUTED`, then `COMPLETED_PROCESS`. If a process reached the output stage but final response or required trace is absent, `output_outcome` remains `NOT_AVAILABLE` and derives `OUTPUT_INVALID`; `NOT_AVAILABLE` before spawn does not independently do so. Exit zero is only a process fact. `COMPLETED_PROCESS` requires a valid envelope and no higher-priority observation and still is not a quality result.

Each artifact ledger row has exactly `role`, `relative_path`, `capture_state`, `byte_count`, `sha256`, and `redaction`. `capture_state` is `RETAINED`, `ABSENT`, or `REDACTED`. Redaction has `state`, `transform_id`, and nullable `original_byte_count`/`original_sha256`. Bounded streams are held until deterministic controlled-key, authorization-header, URI-userinfo/query-secret, credential-prefix, and PEM-private-key transformations run. Safe bytes are then atomically retained. When a prohibited pattern is found, raw bytes are not written; their incremental size/hash and the safe transformed artifact are retained. This is a finite redaction policy, not proof that arbitrary prose has no secret.

For `NATIVE_CODEX`, `pilot_status` is derived without discretion: `COMPLETE` only when every scheduled call exists and has terminal `COMPLETED_PROCESS`; `FAILED` when zero scheduled model calls started; otherwise `PARTIAL`, including all-started runs with any timeout, nonzero exit, invalid output, participant failure, or policy/infrastructure finding. `TEST_DOUBLE` always uses `NOT_EXECUTED`. The run result also records configured model alias/settings and attestation states; `evidence_class` as `EXPLORATORY_CONFIGURED_SAME_MODEL` for eligible native runs unless a trusted verifier and all strict invariants support `STRICT_COMPARABILITY_CANDIDATE`; `claim_status: NOT_ASSERTED`; and `human_rating_status: NOT_EXECUTED`. A stopped schedule leaves later calls explicitly `NOT_EXECUTED` with the stop reason.

Execution follows the schedule without selective omission. `SPAWN_FAILED`, `INTEGRITY_FAILURE`, `POLICY_VIOLATION`, or `TERMINATION_UNCONFIRMED` stops the whole run after finalizing the current attempt. A timeout with `TERMINATION_OBSERVED`, nonzero exit, invalid output/trace, or explicit participant failure does not reorder or suppress the paired counterpart or later scenarios; the runner continues the declared schedule with zero retry. After a global stop, every remaining call gets an immutable `NOT_EXECUTED` record with `RUN_STOP_<terminal-status>_<attempt-id>`. No caller callback can choose which failed arm or scenario to omit at runtime.

## 9. Trusted attestation and strict-profile boundary

`AttestationVerifier` is a future port that receives provider-signed or otherwise independently trusted evidence and returns a typed subject, value, issuer, observation time, evidence hash, verification result, and verifier identity/receipt bound to an administrator-controlled trust registry. The built-in CR-011 runner configures no registry or verifier. It therefore cannot produce `VERIFIED` provider revision or system baseline, and its actual local pilot is exploratory even when both command lines use the same alias. A verifier injected through the private test port stamps `TEST_DOUBLE` and cannot promote any attestation.

A strict request without a verifier fails closed before participant calls. Injected unit-test verifiers can exercise state transitions, but fake verifier output is never production evidence. Even a future `STRICT_COMPARABILITY_CANDIDATE` is only eligible for the separate REQ-011 holdout/human protocol; it is not fairness proof or a superiority conclusion.

## 10. Exact machine assertion contract

The evaluator-held assertion bundle has exactly `schema_version`, `run_manifest_sha256`, `response_schema_sha256`, and `assertions`. It remains outside every arm and is read only by `grade`. Its controlled `expected` member is intentionally permitted here because the entire bundle is evaluator-only; the sensitive-key prohibition still applies recursively and no expected member can enter a participant input. Each assertion has exactly:

```json
{
  "id": "AS-1",
  "scenario_id": "PE-BND-001",
  "check_id": "Q-1",
  "expected": {"value_type": "JSON", "value": "{}"},
  "required_evidence_refs": ["F-1"],
  "oracle_ref": "oracle/BND-1"
}
```

The grader exact-joins `(scenario_id, check_id)` to each anonymous arm envelope and compares type plus canonical value; it does not use substring, keyword, embedding, model judge, or fuzzy match. Exact typed value plus the required evidence-ref subset is `SATISFIED`; a present typed but unequal value or missing required reference is `VIOLATED`; unavailable/invalid output or missing/ambiguous check is `UNSCORABLE`. Unknown grammar, digest mismatch, or duplicate assertion fails grading atomically. Every row carries an evidence pointer to the normalized envelope and oracle ref.

`grade_run.output_path` must be a new path outside the raw run root; it is written atomically and never replaces a grade or raw artifact. Grader output is separate from raw evidence and contains no human rating, aggregate score, participant winner, or superiority text. Participant identities may be replaced with stable anonymous arm IDs, but full human-review anonymization is deferred. `inspect_run` is read-only and recomputes every retained file's length/hash from disk, reporting `INTACT`, `MISSING`, `MISMATCH`, or `UNDECLARED`; it never trusts the ledger to attest itself and never repairs or rewrites evidence.

## 11. Reliability, security, compatibility, and lifecycle

- **Correctness:** exact schemas, byte hashes, equal common blocks, fixed schedule, orthogonal outcomes, and typed assertions prevent a process exit from becoming a quality fact.
- **Performance/capacity:** work is sequential and bounded. A complete three-scenario pilot makes six calls; the mathematical timeout ceiling is six times 1,800 seconds plus bounded local overhead. This is not a latency, availability, or cost SLA.
- **Reliability:** atomic reservation and finalized attempt directories preserve earlier evidence across later failures. Abrupt host loss may leave a temporary directory; `inspect` reports it and never converts it into a completed attempt.
- **Security/privacy:** no enterprise endpoint or credential is accepted. Existing Codex authentication remains outside artifacts. Read-only sandbox, empty cwd, no added dirs, disabled feature requests, and trace checks do not prove filesystem-read or network isolation; the exact label remains `WRITE_RESTRICTED_READ_SCOPE_UNVERIFIED`.
- **Compatibility:** `qa_master.benchmark` and its submitted human-rubric schema are unchanged. Raw-run schema v1 is new and rejects future versions rather than coercing them.
- **Observability:** every command phase, process/output/policy outcome, warning, artifact hash, and missing fact is explicit. Logs use IDs and codes, not payloads.
- **Maintainability:** loader, materializer, executor, parser, grader, and attestation port are separate. The feature-disable and trace profiles are versioned data bound to the Codex binary.
- **Deployment/upgrade:** this is an additive local Python module and entry point. A Codex binary/profile change requires a new preflight evidence record and manifest. No service, database, or schema migration occurs.
- **Rollback:** remove the additive entry point/module or install the prior wheel. Existing raw artifacts remain ordinary JSON/files for inspection; rollback never deletes evidence.
- **Data lifecycle:** artifacts are local and append-only for the run. Automatic upload, cleanup, retention expiry, and repository commit are absent. Explicit deletion is an operator action outside this runtime.

## 12. Verification mapping and implementation handoff

Independent tests should allocate stable `TC-PE` IDs and cover at least:

1. duplicate/unknown/nonfinite JSON; one-byte manifest, asset, input, schema, executable, and settings drift; exact size/count/time boundaries;
2. path traversal, absolute path, symlink, junction/reparse, target escape, existing run ID, and concurrent reservation;
3. deterministic participant projection, no recursive includes, equal common-block hashes, differing full prompts only by assets, and registered-fixture leakage;
4. validate/inspect/grade/import zero-model-call sentinels and explicit-run call counts/order for three scenarios;
5. argv-list/shell-false/native-executable checks, exact disable flags, no add-dir, stdin prompt, environment-name-only evidence, and command redaction;
6. spawn failure, nonzero exit, timeout with confirmed/unconfirmed tree termination, stream cap, absent/malformed final, malformed/unsupported trace, warning item, and observed tool item;
7. orthogonal outcome combinations and the exact terminal priority, including exit-zero plus invalid output and exit-zero plus policy violation;
8. append-only partial A/B and later-scenario failure, ledger reconciliation, atomic-finalization fault injection, and no retry/fallback;
9. response-envelope neutrality, participant-declared failure, typed value canonicalization, exact assertion outcomes, missing oracle, keyword-only adversary, and no aggregate/winner;
10. unknown/unverified attestation produces only exploratory evidence, user-supplied `VERIFIED` fails without a verifier, and strict profile is unsupported by the built-in runtime;
11. legacy benchmark byte/API behavior remains unchanged; new raw-run artifacts are rejected by that validator rather than mistaken for human-rated submissions;
12. a separately authorized installed-wheel pilot with three independently supplied method scenarios preserves six actual calls or exact `NOT_EXECUTED` stop reasons, with `claim_status: NOT_ASSERTED` and `human_rating_status: NOT_EXECUTED`.

The product developer owns the new module, entry point, schemas, and developer tests. The independent tester owns the held scenarios/assertions and fresh pilot verification; the reviewer assesses frozen code and evidence. The implementation must not hard-code the pilot's hidden oracle or use a fake launcher as the final pilot.

Material rationale is recorded in [ADR-005](ADR-005-exploratory-paired-codex-runtime.md). The concise implementation contract is [the TASK-040 handoff](paired-evaluation-runtime-handoff.md). This document remains DRAFT and supplies no Gate or comparison conclusion.
