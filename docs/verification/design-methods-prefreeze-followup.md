# CR-010 prefreeze repair follow-up

- Artifact phase: `PREFREEZE_OBSERVATION`
- Document State: `DRAFT`
- Evaluation State: `IN_REVIEW`
- Evidence Status: `OBSERVED`
- Reviewer: `/root/workflow_review`
- Source SHA-256:
  `63F12C1B36BB0F9DA2B8F13D1CFF687DD2CAC9DEBE1A71C963B5BDCE5378EE93`
- Campaign CLI SHA-256:
  `3D6DA1E1FC0F4B2EA5E0A54E42D4779F0BD7C0BC1EDFD5DF675605FF3E94A2CF`
- Requirements SHA-256:
  `5638A3700F072BFFE5A58C212348966A263D60CDDBA17888314E22C1EBB4E99F`
- DES-033 SHA-256:
  `F823304B68151A3127B0A4F0BC1F5479A69F7FE6A9664C95B328EB0449232CCC`
- Date: 2026-10-15

This note follows the separately preserved prefreeze defect observation. It is
not the formal TASK-037 review, an independent TASK-036 result, acceptance, or
a Gate decision.

## Repair retest

No P0, P1, or P2 finding remained in this bounded prefreeze recheck. The
reviewer reproduced the earlier counterexamples and observed the repaired
behavior:

- boolean `true`, integer `1`, and string `"1"` remain separate in constraint,
  rule-match, admissibility, assignment-row, and candidate projection paths;
- 34-digit integer and decimal grid arithmetic is independent of ambient
  decimal context, and a 35-digit neighbour becomes one typed unrepresentable
  obligation;
- oracle removal does not fabricate an empty boundary domain;
- decision classifications form one mutually exclusive ledger and rows bind
  their emitted candidate or obligation IDs;
- exact method-specific coverage names, states, counts, and ratios are used;
- model and method digests bind linked requirements and all used resolved
  source/oracle objects;
- closed-world total pairs are capped before completion, structural state
  reachability is independent of oracle readiness, and state candidates and
  obligations retain affected state/transition/oracle links;
- reordering set-like registries and transition records is byte-stable and does
  not mutate the caller's bundle;
- grammar-valid opaque locators such as `docs/tokenization` are accepted.

The reviewer ran:

```text
python -m unittest -q tests.test_design_methods tests.test_campaign_design_methods
Ran 35 tests in 1.330s
OK
```

The current untracked independent-test draft has two stale expectations: it
orders flattened candidates numerically although DES-033 requires ID order, and
it expects `reachability_basis` although the exact state-analysis key list omits
that field. Those expectations must be corrected before TASK-036 execution;
they are not implementation defects.

## P3 documentation follow-up

DES-033 prose mentions `reachability_basis: STRUCTURAL_ONLY`, while its exact
state-analysis key list omits the field. The implementation follows the exact
schema and the required structural BFS semantics. A later controlled document
revision should remove the prose ambiguity or explicitly add the field to the
exact schema; it must not be inserted into candidate identity or obligation
subjects implicitly.

Formal review remains dependent on frozen TASK-034/TASK-035 subjects and the
completed independent TASK-036 evidence.
