# QA Master V1 independent review — 2026-10-14

## Review scope and decision

- Baseline reviewed: `main` at `77e3b5d4e8be8076720ebfd2f0338db73dac2079`.
- Review type: independent read-only code, architecture, security, correctness and evidence-integrity gate.
- Scope: staged intent, human requirement/case approval, design-only no-execution boundary, CI/JUnit evidence, Jira/SynapseRT integration foundations, local/remote execution foundations, professional skill depth and comparable evaluation readiness.
- External systems: `NOT_EXECUTED`. No company Jira, SynapseRT, GitLab, host or deployed test target was contacted.
- Decision: `FAIL`.
- P0 findings: none identified.
- Release recommendation: not approved while the P1 findings below remain unresolved and independently re-verified.

The working tree changed concurrently after the baseline was inspected. All initial findings below are anchored to committed baseline `77e3b5d`; in-progress changes are not treated as fixes until a frozen revision is re-reviewed and tested.

## P1 findings

### IR-P1-001 — Design-only and no-execution intent is not a durable authorization boundary

Evidence:

- `qa_master/intent.py:11-14,33-40` grants stages through finite substring matching and does not recognize common forms such as `严禁执行测试`.
- `plan_task("只生成用例，严禁执行测试")` returned both design and execution with `no_execution=False` on the baseline.
- Even a recognized no-execution plan is printed but not persisted by `qa_master/__main__.py:22-28`.
- The user-facing CLI later evaluates execution through the legacy `Campaign.next_action` at `qa_master/core.py:84-97`, without enforcing the preceding Task Contract.

Impact: a later command or orchestrator can cross an explicit human scope boundary without a new execution authorization. This violates the repository rule that a request to generate cases must not execute tests or create Jira/SynapseRT objects.

Required remediation: persist a default-deny capability contract for execution and external writes; enforce it at every state transition and adapter dispatch; require an explicit, fresh and artifact-bound authorization to widen scope. Add paraphrase, adversarial-negation and CLI plan/reload/check tests.

### IR-P1-002 — Side-effect approvals are not bound to the effective build, environment or target

Evidence:

- `qa_master/workflow.py:42-46` permits required answers to be replaced without automatic invalidation.
- `Workflow.approve_exact` at `qa_master/workflow.py:92-101` hashes any caller-selected object; it does not construct a required typed authorization payload from current workflow state.
- `evaluate_exact` and `complete_exact` at `qa_master/workflow.py:103-120` do not require build, environment, Jira project, plan/cycle, case set or risk class to be present and equal to current state.
- Reproduction: approve execution over `{}` while environment is staging, change the answer to production, then call `complete_exact` with the same `{}`. The baseline marked execution `DONE`.
- After a step is `DONE`, `evaluate_exact` returns early through `evaluate` and does not revalidate a changed artifact.

Impact: approval for one build or lab can be reused for another build or production target, and an arbitrary nonempty result reference can manufacture completion state.

Required remediation: use a server-built typed envelope containing project, action, build digest, environment identity, exact case set, plan/cycle, command, assignee, risk class, expiry and idempotency key. Invalidate authorization on every contributing change. Separate `AUTHORIZED`, `DISPATCHED`, `EXECUTED`, `EVIDENCE_VERIFIED` and `DRY_RUN`; require an authenticated executor or external-system receipt before completion.

### IR-P1-003 — Release review can accept self-asserted or unknown evidence provenance

Evidence:

- `qa_master/release_gate.py:29-42` rejects only the exact provenance value `UNVERIFIED_EXTERNAL_ARTIFACT`.
- Missing or arbitrary provenance is not rejected if `status` is `PASS` and `evidence` is any truthy string.
- Reproduction: one approved case with `status="PASS"` and `evidence="self-asserted"`, no provenance, and an empty defect list returned `READY_FOR_HUMAN_REVIEW` with no reasons.

Impact: fabricated evidence can appear review-ready. This breaks the fail-closed CI evidence requirement and can contaminate release decisions or SynapseRT writeback.

Required remediation: require a positive trusted-evidence verifier and a typed attestation record bound to provider, project, build, environment, run/job, case set and artifact digest. Missing or unknown provenance must remain blocked. Defect closure and waivers need equivalent authenticated evidence.

### IR-P1-004 — Token-bearing HTTP clients follow redirects and can disclose credentials

Evidence:

- `qa_master/gitlab_adapter.py:17-20,28-31`, `qa_master/enterprise.py:22-31` and `qa_master/ci_artifacts.py:15-20` use default `urllib.request.urlopen` with `PRIVATE-TOKEN` or `Authorization` headers.
- Python's active redirect handler follows 30x responses and copies non-content request headers to the redirected request, including these credentials.
- `GitLabReader` additionally permits credentialed cleartext HTTP when `allow_http=True` at `qa_master/gitlab_adapter.py:10-15`.

Impact: a compromised or misconfigured endpoint can redirect to another origin and receive the token; cleartext mode permits token and evidence interception.

Required remediation: centralize HTTP transport, require HTTPS whenever credentials are present, disable redirects or permit only validated same-origin HTTPS redirects, strip credentials on any origin change and validate the final origin. Add cross-origin, downgrade and credentialed-HTTP tests.

### IR-P1-005 — Local execution permits do not bind the code or effective command

Evidence:

- `qa_master/local_runner.py:13-15` compares caller-provided strings, including `artifact_version`; it never recomputes an artifact digest.
- `qa_master/local_runner.py:19,22-30` executes a PATH-resolved program from a mutable worktree and inherits ambient execution-control variables.
- A test file, PATH shim, pytest plugin setting or `PYTEST_ADDOPTS` can change after approval without changing approved `argv`.
- `qa_master/local_runner.py:29-30` passes all environment variables except `PYTHONSTARTUP` and `PYTHONPATH`, exposing Jira/GitLab/cloud credentials to test code.

Impact: unapproved code can execute under an apparently valid permit and can read host credentials.

Required remediation: execute from an immutable content-addressed checkout; bind absolute executable identity, tree/package digest, sanitized environment/config digest, timeout and evidence destination to an authenticated permit. Use a minimal environment and scoped secret broker. Add post-approval mutation, PATH-shim, plugin-injection and secret-isolation tests.

### IR-P1-006 — Mutating API generation accepts truthy non-boolean approval values

Evidence:

- `qa_master/api_codegen.py:19-20` uses truthiness for `approved` and `allow_mutation`.
- Reproduction: a DELETE scenario with both values set to the string `"false"` passed validation and was emitted as mutating.
- Runtime authorization at `qa_master/api_codegen.py:36-42` is an unbound environment string rather than an approval tied to target and generated artifact.

Impact: loosely typed JSON/YAML or caller input can enable mutating tests without a valid approval, and the same runtime flag can be reused against another target.

Required remediation: require exact booleans immediately, then require a verified permit bound to generated-source hash, method/path/body, target origin/environment and expiry. Add non-boolean and target-swap negative tests.

## P2 findings

### IR-P2-001 — The installed entry point uses a legacy state model

`pyproject.toml:9-10` maps the product command to `qa_master.__main__`, which imports legacy `Campaign`. `qa_master/core.py:49-54` stores free-text approvals, while the stronger `Workflow` is disconnected from the CLI. `campaign_cli` forms a third path. The current architecture therefore has incompatible planning, approval, persistence and invalidation models.

Required remediation: select one canonical aggregate and command service, migrate both CLI paths, version/migrate persisted schemas, and derive phase plans from one dependency graph.

### IR-P2-002 — Advertised specialist skills do not correspond to in-repository implementations

`qa_master/core.py:11-23` returns names such as `requirements-analysis`, `test-strategy`, `functional-testing` and `reliability-testing`, but only the `qa-master` skill exists in this repository. `skills/qa-master/SKILL.md:20-21` remains a V0.1 description and does not route the newer modules. `qa_master/coverage_design.py:25-31` emits the same generic two-step template across dimensions rather than implementing dimension-specific professional methods.

Required remediation: add a versioned capability registry backed only by importable in-repository implementations. Define common contracts for applicability, input prerequisites, case/evidence schema and limitations, then implement focused modules for functional/API/integration, white-box, performance/load/stress/stability, security, compatibility, recovery and regression.

### IR-P2-003 — SynapseRT dry-run authorization uses an ambiguous scope

`qa_master/enterprise.py:47-50` joins case IDs with commas and does not include assignee in authorization validation. Distinct sets such as `["A,B", "C"]` and `["A", "B,C"]` produce the same version string; changing assignee can retain `approval_verified=True`.

Required remediation: hash canonical typed JSON containing schema version, project, plan, cycle, exact case identifiers, assignee and action. Validate identifier types and delimiters.

### IR-P2-004 — JUnit parsing and binding can misstate outcomes

- `qa_master/junit_ingest.py:11-15` searches raw bytes for ASCII DTD markers; UTF-16 DTD/entity input bypassed the check.
- `qa_master/junit_ingest.py:30-35` recognizes only unnamespaced literal outcome tags; a namespaced failure was recorded as PASS.
- `qa_master/evidence_binding.py:26-40` binds file digest and case IDs but copies caller-controlled status/raw outcome. A parsed failure changed in memory to PASS was accepted.

Required remediation: use a hardened bounded XML parser with DTD/entities disabled, handle or reject namespaces explicitly, and parse the exact hashed bytes inside evidence binding or accept an immutable verified parser result. Add UTF-16/BOM/entity, namespace and outcome-mutation tests.

### IR-P2-005 — CI artifact acquisition fields can be self-asserted

`qa_master/ci_artifacts.py:23` accepts arbitrary injected transport; `:39-41` derives the manifest case set from the downloaded XML; `:42-44` reports `artifact_downloaded_from_job_api=True` even for injected bytes. Current `source_authenticated=False` limits release impact, but the audit fields are inaccurate for downstream use.

Required remediation: acquire through a single authenticated client that returns verified final-origin metadata; label injected transports as synthetic; compare against an independently stored expected manifest.

### IR-P2-006 — Runner output and timeout handling are not bounded end to end

`qa_master/local_runner.py:29` buffers complete stdout/stderr in memory and truncates only after process completion at `:39`. A timed-out direct process can leave descendants alive. Hashes at `:44-45` cover only truncated text.

Required remediation: stream through hard caps while hashing the accepted complete stream, terminate an OS process group/job object, record truncation and add oversized-output/descendant-timeout tests.

### IR-P2-007 — Persistence is vulnerable to lost updates and has no write idempotency ledger

`qa_master/core.py:110-117` and `qa_master/workflow.py:83-90` use a fixed temporary filename without locking, revision or compare-and-swap. The CLI saves after read-only commands. Concurrent commands can lose approvals/events. No durable request digest, remote object ID, retry state or reconciliation record exists for future Jira/SynapseRT writes.

Required remediation: add a lock and monotonically increasing revision/CAS, unique same-directory temporary files and no writes for read-only commands. Add a durable external-operation journal with canonical idempotency key, attempt state, remote ID and readback reconciliation.

### IR-P2-008 — The baseline regression suite was not green

An independent focused baseline run reported two errors in `tests/test_workflow.py`: stale expectations for the new `PermissionError` and a preflight that still called legacy completion for `test_plan`. This result is evidence of an integration gap, not closure of any product requirement.

Required remediation: update the stale tests to the current fail-closed contract and run the complete suite on the frozen revision. Unit success alone will not satisfy live adapter, remote execution or product acceptance gates.

## Missing V1 architecture and bounded implementation order

The V1 tracker already records that live Jira/SynapseRT calls, remote execution, authenticated authorization/audit, complete expert modules, project-level evidence and a comparable benchmark are unavailable. The next implementation slices should be serialized around trust dependencies:

1. Establish one canonical Task Contract/workflow, default-deny capabilities, typed approval envelopes and immutable evidence schemas. Close IR-P1-001, IR-P1-002, IR-P1-003 and IR-P2-001 before attaching side effects.
2. Harden common HTTP, secret isolation and immutable local execution. Close IR-P1-004, IR-P1-005, IR-P1-006, IR-P2-004, IR-P2-005 and IR-P2-006.
3. Implement Jira/SynapseRT adapters behind ports with explicit dry-run/read/write actions, least-privilege credentials, optimistic concurrency, operation journal, idempotency keys and API readback. Plan/Cycle/case/result/defect writes must remain unavailable until authorization and evidence receipts validate.
4. Implement a remote executor protocol using authenticated workers, immutable job manifests, environment allowlists, sandbox/resource limits, heartbeat/cancel/recovery, process-tree termination and content-addressed artifact upload. Treat scheduling success separately from executed and evidence-verified state.
5. Build professional modules behind the capability registry, each with prerequisites, applicability and oracle/threshold rules. Use separate implementation and independent test/review evidence.
6. Build a versioned evaluation harness before any superiority claim: same independent dataset and constraints for both systems, blinded expert rubric, seeded-defect recall, requirement/risk coverage, traceability, hallucination and authorization-boundary violations, reproducibility, time/cost, raw artifacts and version hashes. `docs/V1_ACCEPTANCE.md:27,37` remains `NOT_AVAILABLE` until this is executed comparably.

## Re-review entry criteria

- A frozen commit is provided after concurrent implementation stops.
- The complete automated suite is green with exact command, interpreter, commit and output recorded.
- Every P1 has a negative regression test demonstrating the former bypass and a positive test for the intended path.
- Adapter and executor claims distinguish mock, local, staging readback and production state.
- Missing live corporate targets remain `NOT_EXECUTED`; they must not be inferred from unit or mock results.
- Independent reviewer confirms the implementation path actually uses the hardened components.

Until those criteria are met, all findings remain open and the independent decision remains `FAIL`.

## Frozen-candidate re-review — 2026-10-14

### Subject and independent verification

- Source commit: `18e92b1432b190f122b42297cb9038f712b0b907`.
- Git tree: `2607e2c3891f16136ae0dceed491179d003d1888`.
- The only uncommitted path visible during the final run was the tester-owned `docs/verification/baseline-2026-10-14.md`; no source or test file differed from the subject commit.
- `python -W error::ResourceWarning -m unittest discover -s tests -q`: **384 tests, OK**, 14.515 seconds. The earlier subprocess warning did not recur.
- Safety-focused run covering API generation, runner isolation, workflow receipts, release governance and enterprise adapters: **95 tests, OK**, 6.555 seconds.
- `python -m compileall -q qa_master`: exit 0.
- A wheel was built with `pip wheel --no-deps --no-build-isolation`, installed into a new temporary virtual environment, and `python -m qa_master skills` returned `DISCOVERED` with all six bundled professional guides and no registry gap.
- External enterprise targets and remote machines remained `NOT_EXECUTED`.

An earlier frozen candidate, `c27cb4d`, was rejected because the full suite still expected the removed `AssertionError`; `c3b9aa0` corrected that test contract. Review then found that runner receipts omitted timeout and evidence destination. Commit `18e92b1` binds both values, rejects common secret-bearing command arguments, and adds replay-negative tests. These were independently re-run above.

### Finding reconciliation

The continuation closes the reproducible P1 implementation defects from the baseline within the documented local, trusted-host boundary:

- `IR-P1-001`: mitigated. The CLI persists a default-deny task contract, and design-only scope survives reload and denies execution.
- `IR-P1-002`: mitigated for the local workflow contract. Required answer changes invalidate the affected step and descendants; side-effect completion requires a typed host receipt bound to the current result and workflow inputs, and persists its audit metadata. Identity, signature and time validity remain duties of the absent production host verifier.
- `IR-P1-003`: mitigated. Release assessment fails closed without evidence and governance verifiers; release scope, waiver and defect-closure records are separately checked.
- `IR-P1-004`: mitigated. Credentialed HTTP requires HTTPS and standard network reads reject redirects. Generated API tests also reject credentialed HTTP.
- `IR-P1-005`: mitigated for the bounded local runner. It now binds the actual executable, source manifest, sanitized environment values, timeout and evidence destination; bounds output; reaps timed-out processes; and records process results separately from business outcomes. The mutable workspace limitation remains explicit.
- `IR-P1-006`: mitigated. Scenario approval flags require exact booleans, and runtime target/mutation/host/HTTPS guards use explicit exceptions that remain active with optimized Python.

The baseline P2 defects were either corrected or converted to explicit product limits: JUnit is reparsed from the hashed bytes and rejects DTD/entity and namespace inputs; synthetic artifact transports are labeled; SynapseRT dry-run scope uses canonical structured content; state writes use revision/CAS persistence; enterprise writes use a journal and readback; Jira readback uses submitted-value subset matching for enriched objects; and the local suite is green. `IR-P2-001` remains architecturally open because the installed CLI still uses the legacy `Campaign` aggregate while stronger workflow behavior lives in `Workflow`. The bundled professional files are real packaged planning guides, but they are not complete semantic specialist agents.

No unresolved P0 or reproducible P1 defect was found in the implemented local development increment at this frozen source tree. This is a bounded code-review conclusion, not V1 acceptance or release approval.

### Full V1 blockers and remaining major gaps

The overall independent V1 decision remains **FAIL**. The following missing capabilities are blockers against the stated full-V1 scope even though the local increment is materially safer:

1. **P1 capability blocker — authenticated authority is not delivered.** All production approval, evidence, governance and execution verifiers are host extension points. No production identity provider, signed receipt verifier, key management, expiry/revocation service or durable multi-user audit service is implemented. Side effects therefore remain unavailable by default.
2. **P1 capability blocker — remote execution is not delivered.** There is no SSH/WinRM/worker scheduler, authenticated remote worker, immutable job staging, resource policy, heartbeat/cancel/recovery protocol or content-addressed remote artifact return. `REQ-008` remains a traceability gap.
3. **P2 architecture gap — one canonical workflow is not complete.** `Campaign`, `Workflow` and campaign-generation paths still have distinct state and approval models. Schema migration and one application command service remain pending.
4. **P2 execution-isolation gap — the local workspace is mutable.** The manifest is a trust-provider input, not an immutable staging or hostile-code sandbox. The product correctly documents that it does not support untrusted workspace code.
5. **P2 enterprise-validation gap.** Jira, Confluence, SynapseRT and GitLab behavior is supported by local contract tests only. No authorized staging readback, compatibility matrix, rate-limit/retry exercise or deployment-specific SynapseRT contract has been verified.
6. **P2 professional-depth gap.** Six packaged guides improve planning coverage, but full multilingual semantic specialists, advanced oracle generation and executed nonfunctional methods are not implemented or evaluated.
7. **P2 evaluation and acceptance gap.** The paired benchmark validates submitted artifacts but no same-model paired outputs or independent expert ratings exist. Requirements remain inferred, RTM coverage is partial, project Gates remain blocked, and no human acceptance, release manifest, deployment/rollback evidence or closure record exists.

Accordingly, the current increment is suitable for continued local development and review. It must not be described as a completed QA Master V1, production-ready enterprise integration, authenticated execution service, proven remote runner, or superior system.

## CI portability follow-up re-review

- Scoped source commit: `73a86bb31f4348ce1fa40cf1b79d4c82b0b215e3`.
- Git tree: `5187d7d2097851069a7a2d52572a6ea402dad840`.
- The supplied remote counterpart is `d0ff0a...` with the same tree; this review used the local tree and did not infer CI execution from that mapping.
- Changed files: `.github/workflows/test.yml`, `qa_master/__main__.py`, `tests/test_intent_cli.py`, and `tests/test_runner_isolation.py` only.

The diff does not relax an authorization, execution, HTTPS or evidence check. CLI output now uses ASCII JSON escaping, which preserves Unicode values after JSON decoding and avoids legacy Windows pipe encoding failures. The runner change is confined to the synthetic test provider and compares against the same resolved executable path used by production code. CI now keeps all matrix cells running and promotes `ResourceWarning` to an error.

Independent verification used the later documentation-only `bc722f7` checkout after confirming its source and test files were identical to `73a86bb`:

- `python -W error::ResourceWarning -m unittest discover -s tests -q`: **385 tests, OK**, 11.058 seconds.
- `python -m unittest tests.test_intent_cli tests.test_runner_isolation -q`: **15 tests, OK**, 4.294 seconds.
- `python -m compileall -q qa_master`: exit 0.
- A fresh wheel was installed into a temporary virtual environment. With `PYTHONIOENCODING=ascii`, Chinese project initialization and a Chinese design-only plan both round-tripped through JSON; the persisted plan remained `PLANNING_ONLY` with `no_execution=true`.

No new P0, P1, P2 or P3 finding was identified in this four-file portability change. The bounded local-increment conclusion remains unchanged: no unresolved reproducible P1 implementation defect was found. The full V1 decision remains **FAIL** for the capability and lifecycle blockers listed above.
