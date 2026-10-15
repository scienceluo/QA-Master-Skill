# Public-development exploratory paired-pilot protocol

- Research task: `TASK-046`
- Change context: `CR-011`
- Related requirements: `REQ-019`–`REQ-024`, `NFR-006`–`NFR-008`, and retained `REQ-011`
- Design basis: `DES-040` and `ADR-005` (both DRAFT)
- Document State: `DRAFT`
- Evaluation State: `IN_REVIEW`
- Current status: `NOT_EXECUTED`

## Purpose and boundary

This protocol supplies three **public development** fixtures for an eventual exploratory local pilot. It does not invoke Codex, materialize a participant, execute a test, grade an output, record a human rating, compare participants, or assert that QA Master is better. It is not an enterprise integration activity.

The fixtures cover a narrow no-tool design subset: one finite integer boundary rule, one finite decision table with an explicit exclusion and unresolved overlap, and one finite state model with valid and invalid transitions. They are suitable for developer-visible contract checks only. They are not holdouts and cannot establish general QA-product quality.

## Fixture inventory

| Scenario | Visible input | Public typed oracle | Method boundary |
| --- | --- | --- | --- |
| `PE-BND-001` | `benchmarks/paired-pilot/public-development/visible-inputs/PE-BND-001.json` | `benchmarks/paired-pilot/public-development/oracles/PE-BND-001.public-oracle.json` | Inclusive whole-number 1–9 neighbours; no assumed decimal precision. |
| `PE-DTT-001` | `benchmarks/paired-pilot/public-development/visible-inputs/PE-DTT-001.json` | `benchmarks/paired-pilot/public-development/oracles/PE-DTT-001.public-oracle.json` | Finite plan/destination universe with one excluded combination and an unprioritized overlap. |
| `PE-STT-001` | `benchmarks/paired-pilot/public-development/visible-inputs/PE-STT-001.json` | `benchmarks/paired-pilot/public-development/oracles/PE-STT-001.public-oracle.json` | Explicit DRAFT/SUBMITTED/CANCELLED model with guard, persistence, terminal, and unknown-event cases. |

Every visible-input file follows the strict DES-040 scenario object: exactly `schema_version`, `scenario_id`, `method`, `title`, `request`, `known_facts`, `scope`, and `checks`. It contains no `oracle`, `expected`, `answer`, `rating`, `score`, or `winner` member. All requests expressly prohibit tool use, execution, external writes, and quality/pass claims.

### Fixture integrity record

| File | SHA-256 |
| --- | --- |
| `visible-inputs/PE-BND-001.json` | `E160E7212335D17AAC0FEECDFF6201CBE3C5E4CEA45C0E2C9F2748EE7258160C` |
| `oracles/PE-BND-001.public-oracle.json` | `8F66BBE77E68E3163C871B265403771180546D359EF62A17D8752C3712E82EE8` |
| `visible-inputs/PE-DTT-001.json` | `8EF491BF4DED08583CD6831DC83DF856B5D5304610B310A16A121744BC1BD543` |
| `oracles/PE-DTT-001.public-oracle.json` | `913D8D7EA2743738628F4B264B8C1206FE1DA3C966510E0AB0D6B3EC9BD1F0B6` |
| `visible-inputs/PE-STT-001.json` | `B09F9E3772D608B825611569979D8841B310D9BF5F537216B4261E7E8A885689` |
| `oracles/PE-STT-001.public-oracle.json` | `4857508B014D972AEE8CD36D863682A199960E0EFE84DCF27F8B4F24B5105DD5` |

## Typed-oracle separation

The `*.public-oracle.json` files are deliberately public development material, not runtime inputs. They state fixture expectations in the same typed assertion row shape as DES-040: assertion ID, scenario/check IDs, exact typed expected value, required evidence references, and oracle reference. They cannot be passed to `qa_master.paired_evaluation.run` as evaluator bundles because the final bundle additionally binds a frozen run-manifest SHA-256 and response-schema SHA-256.

Before any future run, the evaluator must create that final bundle outside the manifest directory and both arm roots, copy each public assertion unchanged, and add only the two required binding hashes. The runner must expose only the visible-input bytes, common response schema, and registered participant context to either arm. The public oracle files must never be copied into an arm, stdin, participant context, visible input, or response schema. A public-development oracle is not a holdout and does not turn a process result into a quality score.

## FACT and EVIDENCE: comparator asset provenance

The comparator source is Awesome QA Skills public commit `1a8c57c0e1c31b80aea5cb85dd830387dee09c9f`, read on 2026-10-15. This repository does not copy upstream assets. A future participant materializer must retrieve the listed bytes independently, verify their SHA-256 values, and record them in its frozen raw-run manifest.

| Method | Required upstream assets | SHA-256 of UTF-8 bytes |
| --- | --- | --- |
| boundary | [SKILL.md](https://raw.githubusercontent.com/naodeng/awesome-qa-skills/1a8c57c0e1c31b80aea5cb85dd830387dee09c9f/skills/en/testing-types/boundary-value-testing/SKILL.md), [prompt](https://raw.githubusercontent.com/naodeng/awesome-qa-skills/1a8c57c0e1c31b80aea5cb85dd830387dee09c9f/skills/en/testing-types/boundary-value-testing/prompts/boundary-value-testing.md) | `91D4B18E9EA5E6DF5EF2606A48B8F0DAC7E5D2D8C0AF497CDF26CC8D847AEC03`; `7E21A31C8A78253F7A4B45919087B0CB4120F6E75642802314B35B27A90AF553` |
| decision table | [SKILL.md](https://raw.githubusercontent.com/naodeng/awesome-qa-skills/1a8c57c0e1c31b80aea5cb85dd830387dee09c9f/skills/en/testing-types/decision-table-testing/SKILL.md), [prompt](https://raw.githubusercontent.com/naodeng/awesome-qa-skills/1a8c57c0e1c31b80aea5cb85dd830387dee09c9f/skills/en/testing-types/decision-table-testing/prompts/decision-table-testing.md) | `684714B77C5CB52810B17FA7F286ADC9D18DB92CAF252F1C561A66C3849FA04C`; `A3BC2325A58C048B584232203A23828AB949B88F08FE2DDB2419EC5642660F3B` |
| state transition | [SKILL.md](https://raw.githubusercontent.com/naodeng/awesome-qa-skills/1a8c57c0e1c31b80aea5cb85dd830387dee09c9f/skills/en/testing-types/state-transition-testing/SKILL.md), [prompt](https://raw.githubusercontent.com/naodeng/awesome-qa-skills/1a8c57c0e1c31b80aea5cb85dd830387dee09c9f/skills/en/testing-types/state-transition-testing/prompts/state-transition-testing.md) | `D782952A897A082176A555ED8E352880A25DB87DF500BAD69D1C905EB98965AE`; `FB95B1D8581487B4A3548CF0324035B8C75BE5CFD2390BF46CA631CF27236007` |

The selected `SKILL.md` files explicitly direct their full method prompts to be read. Listing both declared files makes the future participant treatment observable without importing upstream prose into this product repository. The evaluator must separately record byte counts, logical paths, media types, source commit/tree labels, and the final participant context hash required by DES-040.

## Future exploratory execution contract

After the paired-runtime implementation is frozen, independently tested, reviewed, and assigned a separate explicit run task, an exploratory pilot may schedule one `AB` or `BA` pair for each of the three fixtures. This would create six actual bounded calls only if all prior calls complete; it must preserve `NOT_EXECUTED` stop reasons rather than retrying or synthesizing later attempts.

The evidence class remains `EXPLORATORY_CONFIGURED_SAME_MODEL` while provider revision or system baseline is `NOT_AVAILABLE`/`UNVERIFIED`. `WRITE_RESTRICTED_READ_SCOPE_UNVERIFIED` must remain the isolation label unless an enforceable filesystem boundary and negative probe provide stronger evidence. These facts do not block an explicitly authorized exploratory pilot, but they prohibit treating it as strict comparison evidence.

## RISK

- These visible fixtures and their public oracle values are development material. They cannot be reused as a holdout or cited as independently validated capability quality.
- A read-only sandbox, empty current directory, disabled-feature request, or absent observed tool event does not prove filesystem-read or network isolation.
- The asset hashes identify only the listed upstream bytes. Linked or unlisted upstream files are intentionally absent unless a future frozen manifest explicitly lists and hashes them.
- Exact typed assertions can identify agreement with these three fixture contracts; they cannot supply a human rating, aggregate score, fairness conclusion, or product winner.

## Current conclusion

**NOT_EXECUTED.** Three public design fixtures and their separated public typed-oracle definitions are ready for a future controlled exploratory pilot. No model output, participant context, assertion grade, comparison, human rating, or superiority claim exists.
