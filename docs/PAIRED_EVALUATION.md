# Local exploratory paired evaluation

CR-011 adds `qa-master-paired-eval` / `python -m qa_master.paired_evaluation`.
It runs two explicitly registered participant contexts through native Codex,
retains their actual output and process observations, and checks exact typed
assertions. The older `qa_master.benchmark` submitted-human-ratings validator
keeps its existing contract.

The manifest contract is [DES-040](04-design/DES-040-paired-evaluation-runtime.md).
Copy the exact exported byte constants `PROMPT_TEMPLATE_V1` and
`NEUTRAL_RESPONSE_SCHEMA_V1` into the manifest input directory. Arbitrary
templates or response schemas are rejected. List each participant asset
explicitly, including its logical path, source path, size and SHA-256. The
runner embeds those bytes in stdin; it does not recursively follow Skill links.

Keep the evaluator exclusion registry and assertion bundle outside the manifest
directory and output directory. The manifest commits to the canonical exclusion
registry hash. All three method scenarios must have a predeclared arm order.
The public development fixtures in `benchmarks/paired-pilot/` are examples,
not held-out quality measurements.

This implementation additionally limits one manifest to 32 scenarios and
32 schedule rows (64 calls), all materialized input/stdin bytes to 64 MiB,
and the precomputed preflight record to 1 MiB. Joint limits are checked before
reserving a directory, with control-record capacity reserved per attempt.
These capacity restrictions are not in the frozen
requirements/design; coverage remains partial pending its disposition. The
three-scenario pilot fits within it. `oracle_ref` is an opaque audit locator;
the executable expected value is in the assertion bundle. The grader does not
resolve arbitrary oracle files. An unavailable bundle fails atomically.

```text
qa-master-paired-eval validate inputs/manifest.json
qa-master-paired-eval materialize inputs/manifest.json --exclusions evaluator/exclusions.json --output preview
qa-master-paired-eval run inputs/manifest.json --exclusions evaluator/exclusions.json --output runs
qa-master-paired-eval inspect runs/RUN-ID
qa-master-paired-eval grade runs/RUN-ID --assertions evaluator/assertions.json --output grades/run.json
```

Only `run` starts Codex. It requires an already authenticated native Codex
executable whose hash matches the manifest. The version string is a provenance
label, not a live version query. Validation never runs `--version` or another
process. Existing run IDs, preview directories and grade files are never reused.

Each call uses a fresh temporary working directory, read-only sandbox policy,
an allowlisted environment, ignored user configuration, and requested tool
disables. Authentication is left to the native client; no credentials belong
in the manifest. Final-message staging is child-written and may transiently
contain sensitive bytes. Size monitoring requests termination rather than
enforcing an OS disk quota. Cleanup outcome is recorded; deletion is not secure
erasure. Known sensitive patterns cause an entire retained output artifact to
be withheld and replaced with a safe marker, with its original hash recorded.

`result.json` preserves four distinct outcomes per attempt, including process
exit, termination observation, output validity and observed tool policy.
Exit zero is never a quality result. Infrastructure/policy failures stop the
remaining schedule with explicit `NOT_EXECUTED` records. Confirmed timeouts
and malformed outputs remain in the schedule without retries or replacement.
`inspect` rehashes files and reports undeclared, changed or missing artifacts.

`grade` writes a separate exact-value report with `SATISFIED`, `VIOLATED` or
`UNSCORABLE` per assertion. It does not create ratings or aggregate scores.
Provider revision and system baseline remain unavailable/unverified for the
built-in exploratory profile. Strict comparison requests fail closed.
The runtime cannot establish read/network isolation, overall product quality,
human acceptance or superiority. Private injected-launcher tests are marked
`TEST_DOUBLE` and `NOT_EXECUTED`, never native pilot evidence.
