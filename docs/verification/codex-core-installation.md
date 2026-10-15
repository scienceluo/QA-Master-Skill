# Codex core installation verification — 2026-10-15

## Scope and source binding

Continuation base: remote development commit `7c445fe7e0877a8fa6dbfc519acf81c6bdc80314`,
PR #1, branch `codex/qa-master-v1-continuation`. The 195 text blobs were downloaded
through the GitHub connector and individually checked against Git blob SHA-1 before
writing. The historical binary configuration-page screenshot could not be downloaded
through the UTF-8-only connector; it is absent from the local text snapshot and is
would be preserved unchanged when constructing a remote commit from its existing base tree.
The local snapshot commit is not represented as the upstream commit or a full clone.

The existing upstream CI run 114 (`38687215800`) was reread as successful. This is
evidence for the upstream version only, not the changes described here.

## Changes and acceptance

The Python distribution now carries the canonical Codex skill and two focused
references. `python -m qa_master install-codex` installs a self-contained entry,
six professional guides and the local helper into project/user discovery locations.
It refuses unknown or locally modified installs, is idempotent for identical bytes,
and preserves a ZIP of the prior managed bundle during an explicitly requested update.
Publication failure restores the prior directory. ZIP backups are not discoverable
as additional active skills.

The old source-tree skill is a compatibility loader. The expanded canonical workflow
requires source-linked outputs, explicit missing-oracle questions, staged human
baselines, handoffs with actual hashes, change-impact review and object-specific
design for Web/API, Linux/system software and AI computing. These instructions have
not yet been validated through actual model tasks in this environment.

## Executed local checks

Environment: Windows managed sandbox, Python 3.12. Tests used a temporary directory
under the writable project rather than the sandbox's default redirected temp path.

| Check | Actual result | Boundary |
| --- | --- | --- |
| `tests/test_codex_skill.py` | 9 tests passed | Includes real helper subprocesses from a different CWD with Python `-I`, file hashes, scope/pause, idempotence, local-change refusal, ZIP backup and publication-failure rollback |
| Build wheel with no network/build isolation | Passed | Existing package-data rules include the new canonical skill and references |
| Install wheel into a separate target; run isolated Python from a different CWD | Passed | Six guides available under the installed skill, no checkout dependency; init/plan/pause/resume preserve no-execution scope |
| Selected strict regression | 493 tests passed, zero failures/errors | Includes the 9 new tests; excludes 52 tests in native-runner modules and 6 local-socket cases; not a full regression |
| First 499-test selected run | 6 errors | Local HTTP/socket tests rejected by sandbox socket permissions, including WinError 10013; original output retained |
| Native Codex feasibility probe | Blocked before model request | Exit 1, app-server client initialization denied with OS error 5; no READY message, no participant evaluation |
| Bundled skill-creator `quick_validate.py` | Not executed successfully | Validator dependency PyYAML is missing; no claim of official-validator PASS |

The first all-suite attempt used system Python 3.14 and an unwritable redirected temp
directory. It produced permission errors and is not a valid product baseline. A
subsequent full-suite attempt did not produce a completed result in this sandbox;
native subprocess capture emitted a ResourceWarning. Neither is relabelled PASS.
The socket-error run and native-module exclusions remain explicitly reported.

Machine-readable local summaries and raw logs are retained in ignored
`.qa-master/verification/`: `codex-install.txt`, `wheel-build.txt`, `wheel-smoke.json`,
`regression-core.txt`, `regression-selected.txt`, `regression-summary.json`,
`native-probe.json` and redacted native-probe output. They are developer observations,
not independent review, human approval, enterprise E2E or proof of superiority.

## Reproduce

```sh
python -m unittest discover -s tests -p test_codex_skill.py -v
python -m pip wheel --no-deps --no-build-isolation . --wheel-dir .qa-master/wheels
python -m qa_master install-codex --project <disposable-project>
python -I <disposable-project>/.agents/skills/qa-master/scripts/qa.py skills
```

Use an absolute helper path and a different working directory to verify that the
checkout is unnecessary. To test the wheel independently, install it with
`pip install --no-index --no-deps --target <isolated-site> <wheel>` and use Python `-I`
with only that site explicitly added to `sys.path` before calling `install_skill`.
All test targets must be disposable directories within permitted writable roots.

The existing CI matrix runs the complete suite on Windows/Ubuntu with Python
3.10/3.12. Its result for the new commit must be checked separately. Actual model
behaviour, installed discovery in a new Codex session, paired comparison, Linux SSH
workers and real Jira/SynapseRT/Wiki integration remain unverified.

## Remote synchronization blocker

Creating the remote Git tree returned HTTP 403 `Resource not accessible by
integration`. Repository metadata confirms `pull: true`, `push: false` for the
current connection. No remote commit or ref update was performed, and no CI for
these changes was triggered. The tested changes are committed locally and can be
transported as a Git patch. Restoring repository write access is required before
updating the existing draft PR and running its full matrix; changing ChatGPT's
confirmation frequency would not grant GitHub repository permission.

Follow-up: the authenticated account was verified as `scienceluo`; the upstream
repository belongs to a colleague (`leongibhub`). The user selected a fork under
`scienceluo/QA-Master-Skill`. The current GitHub App installation covers all
repositories owned by `scienceluo`, so the fork should normally be included; write
access must still be checked after creation. No fork-creation API is exposed and
the browser runtime failed to initialize twice. Fork creation is not yet complete.
The fork must include the existing `codex/qa-master-v1-continuation` branch, not
just `main`. The README target is prepared for that fork and is not a claim that
the fork or remote changes already exist.
