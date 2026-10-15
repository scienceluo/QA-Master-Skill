# Awesome QA Skills comparison research and evaluation boundary

- Research task: `TASK-031`
- Change context: `CR-010`
- Related requirement: `REQ-011`
- Document State: `DRAFT`
- Evaluation State: `IN_REVIEW`
- Research date: 2026-10-15
- Scope: public upstream material and the current QA Master working tree. No comparator was installed, invoked, scored, or modified.

## Decision boundary

This report supports product and evaluation planning. It is not a quality score, a competitive claim, a human assessment, or a release/acceptance decision. In particular, catalog directories, source-file presence, local unit-test counts, static validation, and a successful CLI process are not behavioral quality evidence.

## FACT and EVIDENCE

### Comparator snapshot

| FACT | EVIDENCE | Source and observed date |
| --- | --- | --- |
| The upstream `main` ref resolved to `1a8c57c0e1c31b80aea5cb85dd830387dee09c9f`. | `git ls-remote` against the public repository returned this SHA for `refs/heads/main`. | [Git repository](https://github.com/naodeng/awesome-qa-skills/tree/1a8c57c0e1c31b80aea5cb85dd830387dee09c9f), observed 2026-10-15. |
| The snapshot contains 165 English and 165 Chinese `SKILL.md` files: 10 workflows, 150 testing types, and 5 skill-engineering packages per language. | Git tree enumeration at the pinned SHA found 330 files, split 165/165. The README describes the same grouping. The number 330 therefore represents bilingual directories, not 330 independent canonical capabilities. | [Pinned tree](https://github.com/naodeng/awesome-qa-skills/tree/1a8c57c0e1c31b80aea5cb85dd830387dee09c9f), [README](https://raw.githubusercontent.com/naodeng/awesome-qa-skills/1a8c57c0e1c31b80aea5cb85dd830387dee09c9f/README.md), observed 2026-10-15. |
| Upstream is a composable Skill library, rather than an integrated test-management product. Its documented entry points route a request to a Skill and its artifacts are instructions, references, prompts, examples, scripts, and evaluations as applicable. | The README describes standalone and composable Agent Skills and lists installation/copy flows. | [Pinned README](https://raw.githubusercontent.com/naodeng/awesome-qa-skills/1a8c57c0e1c31b80aea5cb85dd830387dee09c9f/README.md), observed 2026-10-15. |
| The upstream router distinguishes unavailable skills from installed ones and limits selection to one primary plus at most one helper. | `discover-testing` requires recording `UNKNOWN` or `UNAVAILABLE` availability when installation evidence is missing and instructs one primary plus at most one helper. | [discover-testing](https://raw.githubusercontent.com/naodeng/awesome-qa-skills/1a8c57c0e1c31b80aea5cb85dd830387dee09c9f/skills/en/testing-workflows/discover-testing/SKILL.md), observed 2026-10-15. |
| The representative boundary, decision-table, and state-transition specialists demand sourced inputs and keep absent rules or execution evidence explicit. | Boundary design calls for source, unit, inclusivity, type and step; decision-table design calls for domains, actions, exceptions, precedence, overlaps and gaps; state-transition design calls for state/event/guard/action/target and invalid transitions. Each says its output is candidate design, not execution or coverage evidence. | [boundary-value-testing](https://raw.githubusercontent.com/naodeng/awesome-qa-skills/1a8c57c0e1c31b80aea5cb85dd830387dee09c9f/skills/en/testing-types/boundary-value-testing/SKILL.md), [decision-table-testing](https://raw.githubusercontent.com/naodeng/awesome-qa-skills/1a8c57c0e1c31b80aea5cb85dd830387dee09c9f/skills/en/testing-types/decision-table-testing/SKILL.md), [state-transition-testing](https://raw.githubusercontent.com/naodeng/awesome-qa-skills/1a8c57c0e1c31b80aea5cb85dd830387dee09c9f/skills/en/testing-types/state-transition-testing/SKILL.md), observed 2026-10-15. |
| Upstream separately documents Skill evaluation and cautions against treating validation or a single observation as semantic or release proof. | The `skill-evaluation` package distinguishes benchmark from version regression, calls for run metadata/traces/judges, and preserves incomplete evidence states. | [skill-evaluation](https://raw.githubusercontent.com/naodeng/awesome-qa-skills/1a8c57c0e1c31b80aea5cb85dd830387dee09c9f/skills/en/skill-engineering/skill-evaluation/SKILL.md), observed 2026-10-15. |

### QA Master baseline

| FACT | EVIDENCE | Source and observed date |
| --- | --- | --- |
| QA Master currently discovers and filters six bundled professional guidance files. It reports `PLANNING_ONLY` and `NOT_EXECUTED`; it does not invoke a model or execute a test. | `qa_master.skill_registry` enumerates six required guide files and returns these states from `select_skills`. | Local source: `qa_master/skill_registry.py`, observed 2026-10-15. |
| QA Master can generate a generic positive draft per requirement/dimension and an optional supplied negative draft. It has no boundary, decision-table, or state-transition construction algorithm. | `generator.design()` creates a single generic positive case and only adds a negative case when both input and expected result are supplied. `coverage_design.design_matrix()` similarly emits one case per approved requirement/dimension. | Local source: `qa_master/generator.py`, `qa_master/coverage_design.py`, observed 2026-10-15. |
| The current paired benchmark checker enforces identical scenario hash, model identifier, settings, complete responses, hashes, and five submitted rubric dimensions. It deliberately emits `HUMAN_REVIEW_REQUIRED`. | `qa_master.benchmark` validates paired artifacts but treats ratings as `SUBMITTED_UNVERIFIED_HUMAN_RATINGS` and has no automatic superiority conclusion. | Local source: `qa_master/benchmark.py`; [benchmark contract](../BENCHMARK.md), observed 2026-10-15. |
| No same-model paired execution, independent expert rating, or preserved pair of comparator outputs exists in this repository. | The benchmark manifest is initial `NOT_EXECUTED`; the RTM and gap register retain `REQ-011`/`RISK-006` as incomplete. | Local source: `benchmarks/manifest.json`, `docs/03-requirements/requirement-traceability-matrix.md`, `docs/08-project-management/gap-register.md`, observed 2026-10-15. |

## INFERENCE: capability gaps that matter to users

The relevant gap is not the number of catalog entries. QA Master already has a safer stateful-product direction: it can persist campaigns, preserve authorization/evidence boundaries, and make local planning explicit. It needs deeper, deterministic design work inside that product to turn an approved, sourced contract into useful and reviewable test obligations.

The highest-value bounded increment is an original test-design-methods capability that persists results through the campaign/application path. It should start with three methods whose correctness can be independently checked without a model:

1. **Boundary construction.** For explicitly sourced integer or exact-decimal domains, produce the in-range and out-of-range neighbours around each supplied bound. An absent decimal step, unit, inclusivity rule, valid oracle, or invalid oracle must produce a typed gap; it must never assume `0.01`, a timezone, or a default granularity.
2. **Constrained decision tables.** For supplied finite condition domains, explicit exclusions, actions, and precedence, enumerate legal combinations in a stable order. Report undefined combinations, overlapping rules with different outcomes, and conflicts rather than guessing a priority or compressing away ambiguity.
3. **State-transition design.** For an explicit finite state/event/guard/action model, emit valid and invalid transition candidates. Require the expected target state plus any stated persistence or side-effect oracle; report unknown states, events, guards, initial state, or expected effects as gaps.

These methods should return canonical JSON with a stable method identifier, candidate identifier, source reference, evidence state, trace, validation action, and `DRAFT_UNAPPROVED`/`NOT_EXECUTED` boundary. This is a product differentiation hypothesis, not evidence that QA Master is better today.

## RECOMMENDATION: CR-010 acceptance evidence

Implement and validate the methods in this order: boundary construction, constrained decision table, then state transitions. The increment should be considered complete only when all of the following evidence exists:

| Acceptance area | Required observable evidence |
| --- | --- |
| Source discipline | A missing, conflicting, or unsupported input produces a stable typed gap and no invented rule, value, precision, state, or action. |
| Boundary method | Fixtures prove inclusive/exclusive integer behaviour; exact decimal strings with an explicit step; and rejection of floating-point/default-precision shortcuts. Each candidate has source and valid/invalid oracle references. |
| Decision-table method | Fixtures prove exact legal-combination enumeration with exclusions, gap detection, and overlap/conflict detection. Inputs exceeding a declared finite-combination limit fail safely. |
| State method | Fixtures prove valid and invalid transitions, guard handling, state-preservation expectations, and unknown reference gaps. |
| Product integration | Campaign/application persistence retains the method output, its source trace, and unanswered gaps across reload. It remains a design artifact and cannot create execution, external write, PASS, defect closure, or release evidence. |
| Quality evidence | A developer unit suite, independent negative/integration test, and independent review cover this increment. Counts alone do not satisfy any row. |

This proposal is derived from the product gap and the public comparator's observable design boundaries; it does not copy upstream prompts, templates, examples, or algorithms.

## RISK

- A prompt-library workflow and a stateful local product are not automatically like-for-like participants. A catalog count, skill discovery, schema validation, or successful process can establish availability or integrity, not user-facing design quality.
- If a benchmark runner changes the system prompt, selected upstream skill assets, tool availability, retries, model revision, or sampling settings between arms, the result cannot support a same-model comparison.
- Letting the implementer see the evaluation holdout before implementation turns a general-quality measurement into an optimization set. Conversely, forcing a narrative Skill to satisfy a product-specific JSON schema is an unfair interface advantage.
- The current scenario set is safety/evidence weighted. It does not objectively measure method-specific quality such as boundary neighbours, legal decision combinations, or transition reachability.

## RECOMMENDATION: future fair paired-behaviour evaluation

Do not execute this protocol until an independent owner approves an evaluation plan and the relevant product increment is frozen. At that point use a pre-registered bundle with the following controls.

1. Record the upstream commit, selected skill directory and every referenced asset hash; record the QA Master Git SHA, package version, selected entry point, and all product prompt/template assets. Preserve the platform/system prompt, model provider and revision, decoding parameters, seed where supported, tool policy, timeout/retry policy, runner version, host/time, and the raw/redacted response artifacts with hashes.
2. Give both arms the same user-facing scenario facts, source material, scope, and output format. The arm-specific selected instructions are part of the participant and are recorded, not silently supplemented. If an arm cannot run on the identical model/tool configuration, label the pair `NOT_EXECUTED` rather than substituting a different setup.
3. Split cases before development into a visible development set and a holdout managed by someone who does not implement or tune the methods. Include deterministic method cases and realistic narrative cases. The holdout, answer keys, and grading scripts must not enter product prompts, training material, fixtures, or tuning discussions.
4. Use fixed script oracles for deterministic artifacts: exact integer/decimal boundary sets, decision-table legal universe plus gap/conflict cells, and reachable/invalid state transitions. Report parser/schema failures separately from semantic failures. Do not turn schema conformance into a quality score.
5. For narrative cases, blind participant identity and use at least two independent human raters with a pre-registered rubric, rationale, and evidence references. Preserve disagreements and have a third independent adjudicator handle them. Report unavailable or unscorable cases without imputation.
6. Keep safety/evidence behaviour, factuality, scope discipline, oracle quality, traceability, method completeness, and usability as separately reported dimensions. Do not sum them into a claim unless the pre-registered protocol specifies an interpretable rule and human reviewers approve the conclusion.
7. Publish the complete run bundle and limitations beside any conclusion. Until then, all comparison status remains `NOT_EXECUTED` and no superiority assertion is permitted.

## Current conclusion

**NOT_EXECUTED.** The evidence supports prioritising deterministic, source-bound test-design methods and a stronger future evaluation protocol. It does not demonstrate that QA Master currently outperforms Awesome QA Skills.
