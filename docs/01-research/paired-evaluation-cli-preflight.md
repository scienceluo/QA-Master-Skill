# Paired evaluation native Codex CLI preflight

- Research task: `TASK-045`
- Change context: `CR-011`
- Related requirement: `REQ-011`
- Depends on: `DOC-PAIRED-EVALUATION-PLAN-001`
- Document State: `DRAFT`
- Evaluation State: `IN_REVIEW`
- Executed at: 2026-10-15 UTC
- Scope: one synthetic `READY`-only CLI feasibility probe. This is not a paired evaluation, quality test, rating, or superiority result.

## Test record

| Field | Value |
| --- | --- |
| TC ID | `TC-CR011-CLI-001` |
| Objective | Observe whether the configured native Codex CLI can run a synthetic, non-private, feature-restricted `exec` call and preserve JSONL/final-output artifacts. |
| Linked requirement | `REQ-011` (feasibility evidence only; not its completion evidence) |
| Preconditions | Native executable existed at the registered path; existing local authentication was used without reading, copying, displaying, or recording credentials; a per-call empty working directory existed outside the product repository. |
| Data | UTF-8 stdin only: `Reply with exactly READY. Do not call tools or read files.` Prompt SHA-256: `b1b453404e04166cfe6ac07e9365110cf244a8a95f1a75593b46488690a41939`. |
| Execution method | A local Python `subprocess.run` invoked the native executable with `shell=False`, UTF-8 bytes on stdin, a 120-second timeout, and no product/comparator/holdout input. |
| Expected result | Exit code 0; native JSONL trace and last-message files exist; final output is exactly `READY`; no quality, comparison, or rating output is produced. |
| Actual result | Exit code 0. The final file contains exactly `READY`. A JSONL trace was written and records `thread.started`, two configuration-warning items, `turn.started`, one `agent_message` with `READY`, and `turn.completed`. No quality, comparison, rating, or participant output was requested or produced. |
| Status | `PASS` for this bounded CLI feasibility objective. |
| Linked defects | None observed within this synthetic scope. |

## FACT and EVIDENCE

| FACT | EVIDENCE |
| --- | --- |
| The probe used `C:\Users\leon.wang\AppData\Local\OpenAI\Codex\bin\9614f1d9b40d9c4f\codex.exe` with `gpt-6-astra` and `model_reasoning_effort=medium`. | The preserved non-secret command array in the ignored probe record contains `--model gpt-6-astra` and `-c model_reasoning_effort=medium`. |
| The call used ephemeral execution, `read-only` sandbox, `--ignore-user-config`, `--skip-git-repo-check`, JSONL output, and an absolute last-message path. | The command array and JSONL/final artifacts are retained under the ignored per-call probe directory. |
| The requested feature-disable flag shape was accepted by the native CLI. | The command passed repeated `--disable` values for `shell_tool`, `unified_exec`, `apps`, `plugins`, `hooks`, `memories`, `multi_agent`, `browser_use`, `browser_use_external`, `computer_use`, `image_generation`, `view_image`, `skill_search`, `sleep_tool`, `code_mode_host`, and `unbounded_connection_retries`, plus `--enable skip_host_skill_discovery`; the process completed with exit code 0. |
| The trace recorded a warning that `skip_host_skill_discovery` is under development and a message that code mode is unavailable because `code_mode_host` is disabled. | Both warning items appear in the preserved JSONL trace. |
| A shell snapshot warning was emitted on stderr for PowerShell support. | Preserved stderr contains `Failed to create shell snapshot for powershell: Shell snapshot not supported yet for PowerShell`. This did not change the exit code. |
| The native path produced the required output artifacts. | SHA-256: trace `73d7dc53b3daa6088e6125be1f39d1f4c15cce55c6284d1118b8c3b1fdfb83d9`; stderr `09f7329965c66bcf5e1eff31f13b4db5c7f675b471d2efdf8064b2e109085f4d`; final `c2e3ac47f4a325469c1a2d5f117e463ec943c721986d5d9f09ac4540b7d80526`. |
| The probe used an actual model service through existing authentication. | A completed native trace records token usage and the final synthetic response. Authentication material was neither printed nor retained. |

## Observed command shape

The recorded invocation was equivalent to the following, with an isolated per-call directory outside the product repository:

```text
codex.exe exec --ephemeral --sandbox read-only --skip-git-repo-check --ignore-user-config \
  --model gpt-6-astra -c model_reasoning_effort=medium --json \
  --output-last-message <absolute-final-path> \
  --disable shell_tool --disable unified_exec --disable apps --disable plugins \
  --disable hooks --disable memories --disable multi_agent --disable browser_use \
  --disable browser_use_external --disable computer_use --disable image_generation \
  --disable view_image --disable skill_search --disable sleep_tool \
  --disable code_mode_host --disable unbounded_connection_retries \
  --enable skip_host_skill_discovery -
```

The runner passed the prompt as UTF-8 stdin, not a command-line argument. The ignored local record keeps the full non-secret argument array, outcome, return code, output hashes, timeout, and `shell=false` assertion. It is intentionally outside version control.

## LIMITATIONS AND RISKS

- **No filesystem-isolation evidence:** `--sandbox read-only` denies writes; it does not by itself prove that an arm cannot read another arm or evaluator-held material. A future paired runner needs enforceable per-arm filesystem isolation, such as a container or ACL boundary, and a negative probe that records the result.
- **Provider revision unknown:** the observed command and JSONL trace identify the requested model alias but do not expose a provider-attested immutable model revision. This probe therefore does not satisfy the strict same-model comparison criterion in `DOC-PAIRED-EVALUATION-PLAN-001`.
- **Feature acceptance is not a complete policy proof:** exit code 0 and the code-mode warning show that the supplied flag shape was accepted for this call. The synthetic prompt did not attempt a prohibited tool operation, so it is not a full enforcement test of every disabled capability.
- **One bounded call only:** the result establishes no reliability rate, no prompt quality, no QA capability, no competitor behavior, and no superiority claim. The under-development-feature warning must be preserved in any future runner evidence.
- **Exploratory path only:** after separate authorization and a controlled runner implementation, an exploratory pilot could record a model alias plus `provider_revision: UNKNOWN`. Such a pilot must remain outside the strict-comparison result set; it cannot meet `REQ-011`'s same-model evidence condition.

## RECOMMENDATION

CR-011 can use this observed native command shape as input to a runner design. Before any paired evaluation, add enforceable per-arm read isolation with a tested negative probe; materialize and hash all participant assets; preserve the observed warnings; and obtain a provider-attested revision for the strict result path. Keep the current `qa_master.benchmark` validator as a submission-integrity layer only, with deterministic grading and blinded human ratings remaining separate.

## Current conclusion

**OBSERVED.** One synthetic native CLI call completed and retained the expected trace/final artifacts. It does not execute a benchmark or establish a comparison result, quality conclusion, rating, or claim that QA Master is better.
