# TASK-020 implementation record

- Change: CR-007
- Design: DES-019
- Requirements: REQ-001, REQ-002, REQ-003, REQ-006, NFR-001, NFR-003, NFR-004
- Document State: DRAFT
- Independent test and review: PENDING

The installed `qa-master` / `python -m qa_master` CLI now loads and mutates one
schema-v2 campaign through `CampaignApplicationService`. Existing command
spellings remain; `pause REASON` and `resume` persist the campaign mode.
Paused campaigns reject planning, answers, approvals and invalidation until
resumed. Planning can narrow task scope but cannot enable execution or external
writes. The legacy `approve` command records an unverified assertion only.

Legacy Campaign and Workflow JSON are projected in memory. Their full original
JSON values remain in `legacy_payload`; Workflow step metadata and old history
are retained. Old approvals never become authoritative. Historical completions
are visible as NEEDS_REVALIDATION or STALE in the canonical query projection.
The private snapshot is not returned by the CLI. Existing sensitive content is
not classified or scrubbed; preservation does not imply secret-free history.

The first mutation validates the source digest and revision inside the state
lock, creates a byte-exact `.legacy-<sha256>.json` backup beside the state, then
atomically replaces the file with schema v2. Read commands do not rewrite or
create backups. Initialization uses lock-protected create-if-absent, including
when an old file has no revision. New POSIX backup files have mode 0600;
Windows files inherit their directory ACL. Keep the state directory private.

Restore to an older executable by copying the legacy backup to a different
state path and inspecting it before use. This does not merge any changes made
after migration; there is no automatic downgrade or deletion of backups.

The legacy Python Campaign/Workflow APIs remain callable and are documented as
compatibility APIs. The installed CLI no longer uses Campaign. Workflow exact
evaluation checks bound ancestors before accepting a completed descendant;
invalidation records prior completion metadata before clearing active pointers.
Unbound legacy library behavior remains compatible and is not canonical trust.

Implementation validation: the existing 385-test suite passed after the initial
CLI/service change. Ten new unit checks cover migration preservation, read-only
queries, backup/idempotence, revisionless init, digest/CAS conflicts, pause/scope,
invalid formats, untrusted receipts, atomic-replace failure and recursive stale
evaluation. The first expanded run found a Windows-default-encoding error in a
test fixture; the fixture now reads UTF-8 explicitly. Fresh final counts and
independent evidence are recorded separately against the committed subject.

Remaining boundaries: no CLI completion/provider command, general command
idempotency ledger, production identity integration, remote scheduling, external
write dispatch or enterprise E2E is delivered by this change. The existing
typed receipt API is preserved without claiming re-verification on migration.
This record is not full-V1 acceptance or a Gate PASS.
