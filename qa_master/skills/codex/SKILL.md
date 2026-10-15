---
name: qa-master
description: Review software requirements, derive source-linked test cases, or coordinate staged QA and regression in Codex. Use for QA tasks across Web/API, Linux systems and AI computing software, including work paused until a build is available.
---
# QA Master

Use Codex's reasoning and available tools to produce the requested QA work. This
skill includes professional guides and a local state helper; the helper alone is
not a semantic testing agent or an execution authority.

## Start with the requested outcome

Identify the project, requested stages, available sources, development stage,
expected deliverables and allowed side effects. Read supplied materials and saved
project answers before asking questions. Record an explicit "none" separately from
"unknown"; do not ask again unless the information changes.

- No materials: ask for a requirement, repository, deployed system, or description.
- Repository only: ask whether requirements exist. If not, read relevant code and
  dependencies in depth. Cite revision, path and symbols; observed behaviour is a
  candidate requirement, not its own correctness oracle.
- Deployed system only: agree the observation boundary, investigate within it,
  then derive and review requirements before formal testing.
- Development incomplete: review requirements and design cases now; save a
  `WAITING_FOR_BUILD` handoff. A missing build does not block design.
- One-stage request: finish that stage. Do not expand it into execution or imports.

Use [the work protocol](references/work-protocol.md) for deliverables, local state
commands, human decisions and cross-session continuation. Use
[domain guidance](references/domains.md) to select Web/API, Linux/system or AI
computing checks. Read only the sections relevant to the object.

## Select and apply professional methods

The installed helper is `scripts/qa.py`, relative to this SKILL.md. Resolve its
absolute path before invocation; keep the working directory in the user's project.
`python "<skill>/scripts/qa.py" skills` returns actual bundled guide paths. Read
the relevant guides and apply them to the supplied sources; listing guides is not
completing the work. If Python is unavailable, read the bundled guide files directly
under `scripts/qa_master/skills/professional/` and report the unavailable helper.

| Work | Guide under `scripts/qa_master/skills/professional/` |
| --- | --- |
| Sources, conflicts, reverse requirements, missing rules | `requirements-review.md` |
| Functional, boundary, state, API and negative cases | `functional-api.md` |
| Branches, conditions, integration and async behaviour | `structural-integration.md` |
| Performance, load, stress, stability and compatibility | `nonfunctional-compatibility.md` |
| Security, authorization, failure and recovery | `security-recovery.md` |
| Change impact, regression, defects and evidence | `regression-evidence.md` |

Check applicability of functional, API, white-box, integration, performance,
load/stress, stability, compatibility, negative, recovery, security and regression
coverage. Report applicable work completed, blocked work with the missing input,
or N/A with a concrete reason. Missing SLA means propose scenarios and ask for
thresholds; never invent a passing threshold. A scenario counts as designed only
when its actions and observables are specified, not when its category is listed.

## Preserve decisions and evidence

AI review precedes human confirmation of formal requirements and case baselines.
Draft cases may be created while questions remain; identify which expected results
are conditional or blocked. Human confirmation applies to an exact scope and
version. Saved approval text documents a decision, not authenticated production
execution authority.

Before SynapseRT imports or Plan/Cycle creation, resolve the project, names,
create/reuse strategy and approved cases. Before defect writes, resolve the assignee
or existing policy. Before execution, resolve source/build, target, permitted tests
and existing authorization. Preserve authorized scope; request additional decisions
only when they are actually missing. This local helper has no enterprise write or
remote execution transport; use a verified integration when available, otherwise
produce an import/execution packet and state the gap.

For continuation, read the handoff, verify source and artifact hashes, and update
only impacted work. Changed requirements/code invalidate dependent expectations,
case approvals or previous execution evidence as appropriate. Never relabel old
results as observations against a new build.

Report draft quality, unexecuted tests, actual observations, confirmed defects and
remaining risks separately. Process exit 0 is not a business PASS. Do not assert
coverage of uninspected paths, execution that did not occur, or superiority over
another skill without a defined comparison and actual outputs.
