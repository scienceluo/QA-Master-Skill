# CR-007 negative-test repair record

- Task: TASK-023 (BUG-003/004/005), related review findings BUG-006/007
- Document State: DRAFT
- Evidence Status: OBSERVED for the reproduced findings and developer checks below
- Independent retest: PENDING

The first independent run against `830d231` failed. Its report remains in
`schema-migration-test-results.md`; it is not rewritten as a success.

| Finding | Repair | Verification boundary |
|---|---|---|
| BUG-003: saved legacy answers were echoed by status | All PROVIDED answer values display `[stored]`; CONFIRMED_NONE displays null. Private persisted values stay intact. | Synthetic marker only; no real credentials used. |
| BUG-004: pending questions were lost after reload | Persist the questions list; refresh it after an answer. Earlier development schema-v2 documents lacking this optional field load without destructive rewriting. | Only deterministic planner questions are created. |
| BUG-005: malformed task contracts loaded | Require the exact contract keys, schema version 1, boolean capabilities and recognized string stages. | Unknown/unsupported schema stays rejected. |
| BUG-006: old DONE status remained authoritative-looking on disk | Migrate historical DONE to NEEDS_REVALIDATION, retaining all metadata and the original source in legacy_payload. | No historical completion is authenticated by migration. |
| BUG-007: POSIX directory rename durability | fsync the parent directory after atomic replacement on POSIX. | Windows keeps its existing replace semantics; no power-loss simulation is claimed. |

Developer checks: 13 application tests passed in 0.356s; 11 configuration
tests passed in 2.631s. An earlier full-suite attempt had an independent-test
expectation that still expected raw answer echo, and a Windows oversized-POST
socket abort. The tester corrected the expectation to the agreed redacted
projection; the configuration tests passed on the targeted rerun without a
configuration-code change. Final full-suite and independent results belong to
the new fixed subject, not the original failed subject.

No production identity, remote execution, external writes, enterprise E2E,
full-V1 acceptance or Gate PASS is claimed by these repairs.
