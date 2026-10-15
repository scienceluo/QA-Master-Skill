# ADR-004 — Use deterministic structured models before model-driven QA generation

- Artifact ID: `ADR-004`
- Status: `PROPOSED`
- Date: 2026-10-15
- Change: `CR-010`
- Decision owner: architecture role; no human approval is represented

## Context

The current product can validate requirements and produce generic draft cases, but it cannot construct exact boundary points, exhaust a finite decision table, or analyze a supplied state graph. The comparator research also shows that catalog size and prompt presence are not behavioral quality evidence. CR-010 needs a useful local product increment whose correctness can be independently checked without an external model or target.

## Decision

Implement the three methods from explicit, finite, source-linked JSON models. Use exact integer/Decimal arithmetic, a non-executable declarative constraint AST, exhaustive bounded enumeration, and structural graph reachability. Missing semantic oracles remain obligations. Malformed structure or unsafe/over-limit computation fails the whole call.

Keep generated method cases in a separate `method_design` campaign projection. Do not merge them into legacy generic cases or the canonical Campaign state. All artifacts remain `DRAFT_UNAPPROVED` and `NOT_EXECUTED`.

## Alternatives

1. **Prompt an LLM directly.** This could handle narrative input but would make arithmetic/coverage nondeterministic, require a model runtime, and blur missing source/oracle gaps. It is deferred until a separately controlled evaluation exists.
2. **Add more generic templates.** This is small but repeats acceptance text and does not close the observed professional-method gap.
3. **Use arbitrary Python expressions for constraints and guards.** This is expressive but unsafe, difficult to canonicalize, and impossible to exhaustively validate as data. The bounded AST and reference-only guards are chosen.
4. **Merge method candidates into existing `test_cases`.** This would change legacy results and IDs and obscure which finite denominator was analyzed. A separate projection preserves compatibility and reviewability.

## Consequences

The chosen design produces user-visible, reproducible cases and gap ledgers and supports exact independent fixtures. It cannot infer business rules, nonnumeric boundaries, SLA values, guard satisfiability, or oracle content. Structured input preparation remains necessary. A future same-model paired evaluation can measure these outputs, but this decision creates no benchmark result or superiority claim.

The exhaustive limits bound CPU and artifact size but are not performance claims. Future schema changes require a new schema version; older method-enabled artifacts must fail clearly rather than degrade into legacy generic cases.
