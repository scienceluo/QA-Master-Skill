# ADR-005 — Use content-addressed stdin contexts and an exploratory Codex profile

- Artifact ID: `ADR-005`
- Status: `PROPOSED`
- Date: 2026-10-15
- Change: `CR-011`
- Decision owner: architecture role; no human approval is represented

## Context

The current benchmark validates two submitted, human-rated files but never invokes a model. CR-011 must produce actual paired outputs through the configured local Codex account while preserving exact participant, scenario, model-setting, and process provenance. The observed CLI accepts an explicit model alias, read-only sandbox, ignored user configuration, ephemeral sessions, output schema, JSONL trace, and feature-disable requests. It does not expose a provider-attested model revision, trusted system baseline, or proof of filesystem-read/network isolation.

Participant files also cannot simply be copied into an empty working directory: host skill discovery and file tools are deliberately disabled, so such files would not affect the model call.

## Decision

Build each arm's model stdin from a common content-addressed template, byte-identical visible scenario and frozen response contract, and a deterministic inline projection of only that arm's registered assets. The full prompts may differ only through those projected asset bytes. Run the native Codex executable with an argv list, shell disabled, an empty arm cwd, no added directory, requested no-tool feature disables, read-only sandbox, ignored user configuration except existing authentication, a fixed environment allowlist, bounded streams, zero retry, and retained JSONL/sanitized-final artifacts. Until strict provider output-schema compatibility is separately observed, deliver the contract in the prompt and enforce it with the local exact parser.

Classify the built-in real pilot as `EXPLORATORY_CONFIGURED_SAME_MODEL` while provider revision, system baseline, read isolation, or network isolation remains unverified. A user-entered `VERIFIED` label has no authority. A strict profile fails closed unless a future trusted attestation verifier supplies independently verifiable evidence.

Keep deterministic assertions separate from raw runs and human assessment. The machine grader performs exact typed comparisons only and cannot produce a human rating, aggregate winner, or superiority statement.

## Alternatives

1. **Keep the submission validator only.** This preserves safety but produces no actual model behavior, so it does not meet CR-011.
2. **Use provider APIs with user-supplied keys.** This could expose lower-level model parameters but creates a new credential surface and is unnecessary when an authenticated native CLI is available. It is rejected for this local slice.
3. **Let each agent discover files and use tools.** This makes exposed context and tool behavior harder to compare and would not prove identical capability policy. Deterministic stdin projection makes the treatment observable and works with tool requests disabled.
4. **Describe read-only sandbox as isolation.** This is factually unsupported. The design records `WRITE_RESTRICTED_READ_SCOPE_UNVERIFIED` and treats trace absence only as an observation.
5. **Require a container or OS ACL boundary before any call.** This is preferable for a future strict evaluation, but no verified cross-platform boundary exists in the current project. Blocking the authorized exploratory pilot would add no evidence. The exploratory/strict split keeps the limitation explicit and reversible.
6. **Trust manifest attestation labels.** A caller-controlled label can manufacture strict comparability. The verifier port and default strict denial are chosen instead.

## Consequences

The runtime can produce useful, user-facing case/gap artifacts from two declared participant contexts with exact byte provenance and actual model traces. It remains auditable after partial failure and does not need API credentials or model file tools.

The output is not strict same-revision evidence. Prompt-side no-tool instructions, accepted feature flags, an empty cwd, read-only sandbox, and a trace without tool events are controls and observations, not an OS or provider security attestation. Six sequential pilot calls may take up to the configured bounds and consume external model capacity; the runner records actual outcomes and does not retry.

This decision is reversible. A future container/ACL executor or trusted provider attestation verifier can implement the existing ports without changing raw participant or assertion semantics. Any such change requires a new design revision, capability evidence, and independent verification.
