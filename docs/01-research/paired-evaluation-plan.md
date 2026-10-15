# Paired QA capability evaluation plan

- Research task: `TASK-038`
- Depends on: `DOC-COMPARISON-RESEARCH-001` / `TASK-031`
- Change context: `CR-010`
- Related requirement: `REQ-011`
- Document State: `DRAFT`
- Evaluation State: `IN_REVIEW`
- Planning date: 2026-10-15
- Current status: `NOT_EXECUTED`

## Purpose and boundary

This is a bounded execution plan for a future same-model, same-scenario comparison of QA Master with Awesome QA Skills. It specifies evidence that would make a pair reviewable. It does not authorize a model invocation, benchmark run, human rating, product change, remote action, Gate decision, or superiority conclusion.

The comparator is fixed to public commit `1a8c57c0e1c31b80aea5cb85dd830387dee09c9f`; the planned QA Master product subject is frozen source commit `e619c79` supplied by the CR-010 handoff. Both must be re-read and re-hashed during preflight. If either subject cannot be materialized exactly, the pair is `NOT_EXECUTED`.

## FACT and EVIDENCE

| FACT | EVIDENCE | Source / date |
| --- | --- | --- |
| The existing benchmark contract checks that two submitted artifacts use the same scenario hash, model label, settings and complete response set. It always returns `HUMAN_REVIEW_REQUIRED`; submitted ratings are not independently verified. | `docs/BENCHMARK.md` and `qa_master.benchmark` document/implement these checks. | Local repository, read 2026-10-15. |
| The existing manifest contains twelve narrative and safety/evidence scenarios, all marked `NOT_EXECUTED`. It has no method-specific deterministic oracle cases. | `benchmarks/scenarios.json` and `benchmarks/manifest.json`. | Local repository, read 2026-10-15. |
| Installed CLI preflight found `codex-cli 0.162.0-alpha.17.2`. Its `exec` command supports explicit model selection, read-only sandbox, ephemeral mode, JSON event output, and a last-message output file. | `codex --version` and `codex exec --help`. | Local host, observed 2026-10-15. This version is an observation, not a future-run guarantee. |
| Public comparator research fixed the upstream commit and established that the relevant specialist instructions are source-bound design guidance, not proof of execution or quality. | `DOC-COMPARISON-RESEARCH-001`. | Local repository and linked primary GitHub sources, 2026-10-15. |

## INFERENCE: comparison structure

One evaluation must not force two different products into a single product-specific format. Use two distinct tracks and report them separately.

| Track | Question | Participant output | Judge | Prohibited conclusion |
| --- | --- | --- | --- | --- |
| Deterministic product verification | Does QA Master produce the specified structured boundary, decision-table, and state-transition artifacts from a fixed finite input? | Native structured artifact from the frozen QA Master subject. | Versioned script oracle with visible development fixtures and independently held holdout fixtures. | It does not compare prompt-library quality or prove product superiority. |
| Paired agent behaviour | Given the same user request and source facts, how well does a fixed-model agent guided by each participant preserve scope, facts, oracles, traceability and coverage? | A neutral, common response envelope containing the requested design/report. | Deterministic checks where possible; otherwise blinded independent human review. | A schema-valid response, safety refusal, or one arm's tool success is not a superiority result. |

The paired behaviour track has two intentionally separate lanes:

1. **Specialist lanes:** boundary, decision-table, and state-transition cases declare their method before invocation. Both arms receive the same material and neutral response envelope. The upstream arm uses the matching pinned specialist bundle; the QA Master arm uses the frozen matching entry point/assets. This avoids treating route selection as an invisible human advantage.
2. **Router lane:** method labels are withheld. The upstream arm uses its pinned discovery bundle and the QA Master arm uses its frozen discovery/selection entry point. It evaluates selection explanation and availability/provenance boundaries separately from specialist design quality.

## Required immutable run bundle

An independent evaluation owner creates a new run directory outside the product working tree. Every pair receives one signed-or-hashed `run-manifest.json`; a missing field means the pair is `NOT_EXECUTED`.

| Bundle item | Required fields |
| --- | --- |
| Participant identity | `participant_id`, Git commit, repository tree SHA-256, package/CLI version, selected entry point, selected asset paths, and SHA-256 for every selected instruction, prompt, reference, template and fixture actually made visible to the agent. |
| Common input | Scenario ID, canonical input SHA-256, user-facing request, allowed source materials with hashes, common response-envelope schema/hash, and method label visibility for the chosen lane. |
| Model/runtime | Provider, exact model revision (not only a marketing alias), Codex CLI version, platform/system prompt identity or provider-attested immutable baseline, decoding settings, seed if supported, tool policy, sandbox, timeout, retry policy, host OS/architecture, and UTC start/end time. |
| Outputs | JSONL event trace, final response, exit code, stderr, hashes of every retained artifact, redaction record, and a classification of `COMPLETED`, `PARTICIPANT_FAILURE`, `INFRASTRUCTURE_FAILURE`, or `NOT_EXECUTED`. |
| Review chain | Deterministic grader version/hash where applicable, anonymization map held by the evaluation owner, reviewer assignments, completed rubrics, disagreement record, adjudication record, and limitations. |

No secret, token, cookie, private key, full presigned URL, or private user content belongs in this bundle. If redaction changes a source or output, retain its hash and describe the transformation; otherwise reviewers cannot establish what was judged.

## Preflight and runnable Codex execution shape

The following is a future command shape, not a command to run as part of this task. It uses only documented options available on the locally observed CLI. The evaluation owner supplies a real, provider-pinned model revision and writes the source/asset snapshot before execution.

```powershell
$evalRoot = 'D:\qa-evaluation\run-001'
$armRoot = Join-Path $evalRoot 'arm-a'
$promptFile = Join-Path $armRoot 'input\neutral-prompt.md'
$traceFile = Join-Path $armRoot 'outputs\trace.jsonl'
$finalFile = Join-Path $armRoot 'outputs\final.md'

Get-Content -Raw $promptFile |
  codex exec --ephemeral --sandbox read-only --ignore-user-config `
    --model '<provider-pinned-model-revision>' --cd $armRoot --json `
    --output-last-message $finalFile - 1> $traceFile
```

Run the exact same command shape once per arm, changing only the materialized participant bundle and arm directory. Do not use `--add-dir`; a participant must not read the other arm, the evaluator's answer material, or the parent product workspace. Do not add arm-specific helper prose outside the recorded participant assets. Record the command template and environment allowlist in the manifest, but do not record credentials.

Before a pair is runnable, the owner must verify all of these conditions:

1. Both subjects are exactly materialized at their pinned commits and all visible asset hashes match the manifest.
2. The same provider can attest the identical exact model revision and system baseline for both arms. If an alias such as a model family name cannot be resolved to a fixed revision, do not run the pair.
3. Sampling/tool/sandbox/timeout/retry settings are identical. If the provider does not support a seed, use the same pre-registered repeat count for both arms and report variation; do not silently treat one sample as deterministic.
4. Both arms see only the common scenario material plus their recorded participant assets. Network/browser/tool access is either disabled for both or identically declared and made available to both.
5. The output envelope can represent both participants' natural outputs without demanding QA Master-specific campaign fields. A failure to parse is an observed outcome, not a reason to rewrite the other arm's answer.

## Scenario policy

The twelve existing scenarios remain a visible narrative/safety development set. They test scope control, absence of evidence, conflicts, recovery boundaries, and release/defect restraint. They do not establish method-design quality by themselves.

For a future paired run, an independent evaluator should add two scenario collections before the product is tuned:

| Collection | Visibility | Content boundary | Judging approach |
| --- | --- | --- | --- |
| Method development set | Visible to implementers | Sourced finite integer/decimal ranges, finite decision rules with exclusions or ambiguity, and finite state graphs with invalid events/guards. | Versioned script checks plus review of visible fixtures. |
| Method holdout set | Restricted to independent evaluator until all participants are frozen | Different values, rule shapes, conflict patterns, transition graphs, and missing-input cases from the same declared input grammar. | Versioned script checks held with the evaluator; no answer keys, expected candidate lists, or grading fixtures enter this repository before freeze. |
| Narrative holdout set | Restricted to independent evaluator until all participants are frozen | Realistic but de-identified QA planning, evidence, scope, reporting and routing problems. It includes incomplete and adversarially ambiguous inputs. | Blind human review using the pre-registered rubric. |

This document intentionally does not contain holdout source inputs, expected answers, parser fixtures, grading code, or a scoring threshold. Their presence in the shared product repository would create leakage into implementation and prompt context.

## Deterministic oracle protocol

Deterministic grading is an artifact-level check, not a human-quality score and not a cross-product comparison claim.

- The grader accepts only the neutral response envelope and produces one outcome per assertion: `SATISFIED`, `VIOLATED`, or `UNSCORABLE` with an evidence pointer.
- Boundary assertions check exact-domain arithmetic, supplied inclusivity, source references, and a typed gap when step/precision/unit/oracle is absent. They must reject float/default-precision substitution.
- Decision assertions check the declared finite legal universe, exclusions, undefined cells, and conflicting/overlapping rules. They must not award coverage merely for enumerating rows.
- Transition assertions check supplied source/target/guard/action references, valid and invalid transitions, and stated persistence/side-effect expectations. They must not infer unstated states or rules.
- The grader, input grammar, fixture hash, and assertion outcomes are preserved. Parser failure, schema failure, timeout, unavailable model, and unknown semantics remain distinct outcomes.

The QA Master deterministic product-verification track may use the same grader for its native structured artifacts. It must be reported separately from paired agent behaviour because Awesome QA Skills is a prompt library rather than a matching local deterministic engine.

## Human review protocol

Only narrative or semantic assertions that cannot be objectively checked go to human review.

1. Remove participant identity, repository path, asset names, model trace details, and arm-specific wording from the review packets. The anonymization key stays with the independent evaluation owner.
2. Assign each response to two independent reviewers who did not implement either participant and have not seen the answer key. Each reviewer records a 1–5 rating, rationale, and evidence reference for the existing five dimensions: factuality, scope, oracle, traceability, and coverage.
3. Add an explicit `UNSCORABLE` option per dimension. Reviewers must use it when required evidence is absent; no imputation or default score is allowed.
4. Preserve both ratings and disagreements. A third independent adjudicator resolves only an agreed protocol question; the adjudication cannot overwrite or erase the first two ratings.
5. Report rater agreement and all missing/failed cases. Any future aggregate interpretation must be pre-registered and approved by humans; the benchmark tool continues to return `HUMAN_REVIEW_REQUIRED`.

## RISK

- **Model drift:** the current Codex CLI supports an explicit model option but may not expose a provider-pinned model revision. An unresolvable revision blocks the strict same-model condition.
- **Asset drift:** upstream progressive-disclosure files can alter behaviour even when the top-level `SKILL.md` stays constant. Hash every asset actually exposed, not only the entry file.
- **Interface bias:** asking one arm for a proprietary campaign object would favour QA Master; stripping all structured detail would discard its product value. The two-track structure makes this trade-off explicit.
- **Evaluation leakage:** a visible holdout or answer key is not a holdout. It must remain outside the shared repository and agent working directories until freeze.
- **Authority boundary:** a model invocation consumes an external service and may produce data that needs retention/redaction handling. This planning task supplies no authority to make that call.

## RECOMMENDATION: next bounded change requirements

Create a follow-on evaluation-infrastructure change only after CR-010's independent test and review evidence is frozen. Its requirements should include:

1. A strict run-manifest schema that rejects incomplete participant, model, common-input, tool-policy, and output provenance.
2. A materializer that verifies pinned source/assets by SHA-256 and creates two isolated read-only arm roots without copying private holdout material into either arm.
3. A runner wrapper that records the documented Codex command, exit status, trace/final-output hashes, and explicit failure classification without treating a process exit as a quality result.
4. A neutral common response-envelope schema with a publicly versioned parser and deterministic grader contract.
5. Separate storage/records for deterministic assertions and blinded human ratings; no automatic aggregate score or superiority statement.
6. An evaluator-held holdout register with a public commitment hash and release-after-freeze procedure, but no answer keys in the shared repository.
7. Validation tests for mismatched commits, asset hashes, model/runtime fields, settings, tool policies, scenario hashes, parse failures, missing ratings, anonymization leakage, and prohibited automatic claims.

## Current conclusion

**NOT_EXECUTED.** The existing benchmark validator is useful as a submission-integrity layer, but it is insufficient for a fair paired behavioural evaluation. This plan defines the additional provenance, isolation, deterministic-oracle, and independent-human-review evidence needed before any comparison can be evaluated by people. It provides no result and supports no claim that either participant is better.
