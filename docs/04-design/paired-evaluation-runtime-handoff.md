# Paired-evaluation runtime architecture handoff

- Artifact ID: `DOC-PAIRED-EVALUATION-RUNTIME-HANDOFF-001`
- Document State: `DRAFT`
- Evaluation State: `IN_REVIEW`
- Change / task: `CR-011` / `TASK-040`
- Design: `DES-040` and `ADR-005`

## Implementation scope

Create `qa_master.paired_evaluation` and an additive module/installed CLI with `validate`, `run`, `inspect`, and `grade`. Only `run` may invoke the native Codex executable. Preserve `qa_master.benchmark` unchanged.

The implementation must provide:

- strict duplicate-safe raw-run loading, content hashes, path containment, link/reparse rejection, fixed limits, and an evaluator-exclusion registry outside participant/manifest roots;
- exactly two arm descriptors, deterministic length-framed inline participant context, byte-identical common request/response blocks, built-in frozen template/neutral response schema bytes, and no recursive asset discovery;
- atomic new-run reservation, sealed preflight, append-only attempt artifacts, bounded concurrent stream capture, private last-message staging with honest cleanup outcome, timeout/process-tree termination evidence, and no retry;
- the exact independent `process_outcome`, `termination_outcome`, `output_outcome`, `policy_outcome`, terminal priority, fixed `CODEX_ENV_V1` allowlist, and native-vs-test backend provenance in `DES-040`;
- neutral user-facing `summary`, `cases`, `gaps`, typed `observations`, and fixed DRAFT/NOT_EXECUTED metadata through the shared output schema;
- exact typed assertion grading separate from raw evidence, with no human rating, aggregate score, winner, or superiority output;
- a built-in exploratory profile only. Provider revision/system baseline remain unknown or unverified unless a future trusted verifier is configured; caller labels are not verification.

The current observed command profile uses native Codex `gpt-6-astra`, reasoning effort `medium`, stdin prompts, JSONL and a private last-message staging file, read-only sandbox, ignored user config, ephemeral mode, no added directories, and the exact disable list in `DES-040`. The frozen neutral contract is prompt-delivered and locally parsed because strict provider `--output-schema` compatibility was not established by the CLI preflight. It is `WRITE_RESTRICTED_READ_SCOPE_UNVERIFIED`, not read/network isolation.

## Acceptance handoff

Developer verification should cover parser, path, atomicity, call-count, outcome-precedence, redaction, trace, and compatibility fixtures. Independent testing owns the three frozen boundary/decision/state pilot scenarios and assertion bundle, must run the installed artifact with the real launcher, and must retain all six calls or exact typed stop reasons. Independent review uses the frozen code and retained evidence.

Deferred work is explicit: provider/system attestation, enforceable OS read/network isolation, strict comparison, released holdout, full anonymization, human ratings/adjudication, aggregate interpretation, enterprise integration, remote execution, retention deletion, and any superiority decision.

This handoff records a DRAFT architecture candidate. It is not implementation, test execution, approval, a Gate result, or comparison evidence.
