# Developer verification — structured design engine

- Artifact ID: `DOC-DESIGN-METHODS-DEVELOPER-001`
- Change / task: `CR-010` / `TASK-034`
- Requirements: `REQ-013`–`REQ-017`, `NFR-005`
- Subject: `qa_master/design_methods.py` and `tests/test_design_methods.py`
- Evidence status: `OBSERVED` developer verification only

## Scope

This task implements the pure local engine specified by `DES-033` and
`ADR-004`. It deliberately excludes `campaign_cli.py`, installed-CLI checks,
external adapters, runners, approval, execution, paired comparison, and any
claim about superiority over Awesome QA Skills. Those items require separate
task ownership and independent evidence.

The public API is `load_bundle_json`, `design_methods`, and the stable-code
`DesignMethodError`. The engine accepts finite source/oracle-linked models and
returns only `DRAFT_UNAPPROVED` / `NOT_EXECUTED` artifacts. It uses no process,
network, runner, approval, or enterprise-adapter implementation.

## Developer checks

Run from the repository root with the platform Python environment and
`PYTHONPATH` set to the repository:

```powershell
$env:PYTHONPATH='D:\QA-Master-Skill'
D:\codex-rd-platform\.venv\Scripts\python.exe -m unittest tests.test_design_methods -v
D:\codex-rd-platform\.venv\Scripts\python.exe -m py_compile qa_master\design_methods.py
```

Historical first-developer observation, insufficient to establish conformance: 9 focused engine unit tests plus
11 Campaign integration tests passed (20 total), and compilation passed.
The tests cover deterministic set-order normalization across all three methods,
exact Decimal boundary handling and missing-oracle suppression, decision
gap/overlap/conflict/constraint accounting, state closed-world and absent
invalid semantics, strict JSON duplicate/NaN/secret rejection, and atomic
structural rejection. This is not independent test, review, Gate, release, or
acceptance evidence.

## Remaining verification

Independent testing must execute the DES-033 matrix, including exact boundary
limits, full decision/state limit fixtures, process/restart canonical bytes,
secret non-disclosure in CLI errors, legacy campaign equality, atomic CLI
failure, and installed-package smoke after the separately owned CLI task is
complete. Independent review must assess the resulting fixed revision.


## Root corrective verification - 2026-10-15

Actual developer: `/root`, TASK-034 attempt 3. Source freeze: `e619c79`.
The earlier ready claim was rejected by prefreeze review: typed scalar
matching, decimal arithmetic, coverage ledgers, reference binding and kind
checks were faulty. The initial passing tests did not cover these defects.

The repair uses scaled integers for decimal arithmetic and a single typed
assignment ledger for decision generation and accounting. It fixes
oracle-independent empty-domain checks, distinct unrepresentable neighbours,
exact coverage mappings, complete linked requirement/reference digests,
nested set normalization, reference kinds, closed-world total-pair limits,
and complete state source/oracle links. Regression cases include arbitrary
condition names, malformed types, permutations and 34-digit arithmetic.

Source SHA256:
`63F12C1B36BB0F9DA2B8F13D1CFF687DD2CAC9DEBE1A71C963B5BDCE5378EE93`

Unit-test source SHA256:
`C450F268D0262EB650F3DDB17CBC84A8F3D46D3FBAAE46364291573A0E229264`

Observed developer verification on frozen source:

- `python -W error -m unittest tests.test_design_methods tests.test_campaign_design_methods tests.test_campaign_cli -q`: 43 tests PASS, 1.523 seconds.
- `python -m py_compile qa_master/design_methods.py`: exit 0.
- `git diff --check`: exit 0; configured line-ending warnings only.
- Earlier complete-suite run: 490 tests PASS in 21.598 seconds before final state-link and loader repairs; not evidence for the final revision.
- Broad frozen-source run including the tester's then-unfrozen preparation file: 497 tests, one failure and one error in 22.056 seconds. These were stale test expectations: flattened candidates expected numeric rather than ID order, and a state-analysis field absent from the exact schema. The tester corrected both expectations afterward. Fresh independent validation remains required; no final full-suite PASS is claimed here.
- A stress run exposed repeated domain validation per assignment and was interrupted without a test result. Evaluation now traverses the already validated AST; the 4096-assignment / 128-node regression passes in the focused run.

The prose `reachability_basis: STRUCTURAL_ONLY` conflicts with the exact state
analysis key list in DES-033 v2. Implementation follows the exact list and
structural BFS semantics. This is a P3 documentation ambiguity; no extra
schema field was introduced.

TASK-036 independent testing and TASK-037 formal review are pending at this
handoff. This record is not Gate, release, acceptance, or comparison evidence.
