# Local execution adapter — permission and evidence boundary

**Task:** TASK-006
**Requirements:** REQ-008, NFR-001, NFR-003, NFR-004
**Design state:** IMPLEMENTATION_IN_PROGRESS. This document is not execution evidence or production authorization.

## Hardening design and acceptance scope

The local runner accepts only a fixed test command shape and runs it with `shell=False`. A `RunPermit` is a caller-provided scope assertion, not an authenticated identity or execution authorization. Before any process starts, `run_local` must receive a configured trusted execution provider. It receives a binding containing project, argv, resolved work directory, normalized evidence directory, timeout, caller artifact-version label, safe-PATH-resolved executable and its SHA-256, a bounded current-workspace digest manifest, and the child environment-name whitelist. It must return a `TrustedExecutionReceipt` with the exact binding digest and a nonempty provider, receipt ID and signature. An absent provider, boolean/caller assertion, malformed receipt, stale binding or throwing provider fails closed. Unit tests use a provider explicitly named `SyntheticTrustedExecutionProvider`; it is test scaffolding and cannot be used as a production trust provider.

The provider is the trust-port boundary: a production implementation must verify a host policy and a signature/receipt against a key or external identity service outside this process. The runner only checks receipt shape and exact binding equality; it does not cryptographically verify a signature, authenticate an operator, or sandbox the operating system. The launch argv replaces the requested executable with the same resolved absolute executable that was hashed and bound. The child `PATH` excludes empty entries, `.` and the workspace.

The current runner hashes a mutable workspace but does **not** copy it to isolated immutable staging or rehash immediately before every file open. Consequently it is not an untrusted-code sandbox: a repository owner or code running in the child can alter files or its own process after launch. The manifest is a provider input and audit reference only. A future staging feature must copy the approved manifest to a separate location, verify every copied hash, make it read-only where the host supports it, and bind the staging path; it must not claim this protection until independently validated. The host provider must also authenticate the target/environment identity and signature outside this module; the local receipt shape does not establish that identity.

The child receives a minimal allow-listed environment and only explicitly supplied injected variables. It does not inherit the parent environment wholesale. Every non-sensitive injected value is SHA-256 bound to the receipt without persisting its raw value, so changing `QA_TARGET=staging` to `QA_TARGET=production` changes the authorization binding. Sensitive-name injection is rejected in this runner; a future implementation may accept only an external opaque-secret reference/version or provider-controlled HMAC, never the raw secret or a plain unsalted secret hash. Known secret values inherited by the parent are redacted before stdout/stderr are persisted. Output streams are read concurrently in bounded chunks; the runner retains at most the documented per-stream cap while draining excess data, records truncation, and never uses unbounded `capture_output` buffers.

Secrets in command arguments are unsupported because requested argv is evidence metadata. The runner rejects common `--token`, `--password`, `--secret`, `--credential`, API-key/private-key flags and `Authorization:` arguments. Callers must not encode credentials in other argv forms either; use a provider-controlled opaque secret mechanism when it is implemented.

On timeout, the runner creates an isolated process group/session then terminates its descendants: POSIX uses the process group; Windows uses `taskkill /T /F`. It then waits to reap the direct child and falls back to direct kill/reap. Only a confirmed reaped child receives `TIMEOUT`; an unreaped child becomes `ENVIRONMENT_ERROR`. This is best-effort OS process control, not a sandbox or proof that every externally started process can be recovered. The evidence path is normalized and validated as an existing-or-creatable directory outside the workspace **before** `mkdir` is called.

Acceptance tests must show: no verifier prevents spawning; the system Python executable works; a synthetic verifier grants only test fixtures; output is bounded and redacted; parent-only variables are absent from the child; injected values are scoped; timeout returns `TIMEOUT` and uses the termination path; unsafe evidence locations are rejected before directory creation; and `PROCESS_SUCCEEDED` still leaves `business_result=NOT_ASSESSED`.

Implemented: `qa_master.local_runner.run_local`.

- Executes **local** trusted test commands with `shell=False`; permitted entrypoints are `pytest`, `python -m pytest`, or `python -m unittest`.
- Requires an explicit `RunPermit` matching project, full argv, absolute working directory and artifact-version label **and** a trusted execution provider receipt bound to the actual executable, source manifest and child environment names. The permit is a scope record, not a proof of authenticated identity.
- Captures bounded concurrent stdout/stderr, exit code, timeout and a unique evidence file; records SHA-256 checksums, truncation metadata and an audit JSON file after secret-value redaction.
- Reports `PROCESS_SUCCEEDED`, `PROCESS_FAILED`, `TIMEOUT` or `ENVIRONMENT_ERROR`, never pretends this is a passing business test: `business_result=NOT_ASSESSED`.
- Test code may perform arbitrary actions within the executor's OS permissions. **Only run approved, trusted test repositories in isolated environments**. This module is not a security sandbox.
- Output is written outside the test workspace; no network or remote host execution is performed by the adapter itself.

Usage sketch:

```python
from pathlib import Path
from qa_master.local_runner import RunPermit,run_local
import sys
cwd=str(Path('.').resolve())
command=(sys.executable,'-m','unittest','discover')
permit=RunPermit('demo',command,cwd,'approved-operator','test-tree-sha')
class TrustedProvider:
    def verify_execution(self, binding):
        # Production implementation: validate a signed provider receipt / trusted host policy.
        raise PermissionError("No production provider configured")
result=run_local('demo',list(command),cwd,'test-tree-sha',permit,'/tmp/qa-master-evidence',
                 trusted_execution_provider=TrustedProvider())
print(result['process_status'], result['business_result'])
```

Unit tests cover command scope, the fail-closed verifier, bounded/redacted output, sanitized/injected environment, timeout isolation, unsafe evidence paths and process/business-result separation. They are local synthetic checks, not cloud CI, Windows production-host validation, signed provider integration, or production isolation evidence.

## Remaining release work
Actual task queue and lifecycle persistence, authenticated approval workflow, remote SSH/WinRM agent, test-result parsing, browser runner, controlled load-test execution, and Jira/SynapseRT/Confluence CRUD operations are not present. Do not describe this as a completed enterprise platform.
