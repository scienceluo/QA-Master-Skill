# Offline QA Campaign CLI

This is the first combined, one-command path that actually wires the existing requirement quality checker, case generation engine, coverage matrix and case reviewer together. It is **not** an LLM, an API connector, or an automated test executor.

## Run (Windows / Linux)

```bash
python -m qa_master.campaign_cli --input examples/campaign.json --output campaign-report.json
python -m unittest discover -s tests -q
```

Review `campaign-report.json`:
- `requirement_review.findings`: source problems, ambiguity and acceptance gaps
- `test_cases`: structured **draft** cases with requirement trace IDs
- `case_review`: case quality issues and trace matrix
- `coverage`: 13 test dimensions explicitly marked DRAFT, BLOCKED, UNASSESSED or N/A
- `unresolved.design_gaps`: missing oracle/threshold/approval
- `workflow`: no execution or SynapseRT write authorized

## Safety boundary

The CLI reads one local JSON bundle of no more than 5 MB and writes a local JSON output atomically. It never connects to Jira, GitLab, SynapseRT or remote machines, never issues PASS, and never approves a requirements baseline. It does not perform semantic extraction of natural language requirements; inputs must be structured and any acceptance oracle must be supplied.

## Tests

Current independent execution records are in [verification](verification/).
Each record names its source version and scope. Historical test totals are not
evidence for a changed version.

## Structured design methods

For explicit finite domain/rule/state models, run:

```bash
python -m qa_master.campaign_cli --input examples/design-methods.json --output method-report.json
```

The example is illustrative input, not an approved requirements baseline.
It expands exact Decimal boundaries, a finite decision table and an order-state
model. The input must supply sources and expected-result references; the engine
does not read source documents or infer their meaning. The complete schema is
specified in [DES-033](04-design/DES-033-structured-test-design-methods.md).

`method_design.candidates` contains the resulting draft cases, with their input
values or assignments, source/oracle links, and `validation_action: NOT_EXECUTED`.
`method_design.obligations` retains missing oracles, uncovered or conflicting
rules, and unreachable transitions. `model_results` records the declared
coverage denominator and method-specific analysis. A coverage ratio measures
draft candidates against that finite model; it is not a test result or a quality
score. The original generic `test_cases` remain separate and unchanged.

Numeric models use explicit steps and exact arithmetic. Decimal values must be
canonical strings, not JSON floats. Decision rules use the bounded data grammar
in the design; no expressions or scripts are evaluated. State reachability is
structural and treats guards as potentially satisfiable, not proven executable.

Bundles without `design_models` preserve the legacy report shape. An empty
model array produces an explicit empty method report. Invalid method input,
duplicate JSON keys, non-finite numbers or sensitive-shaped method fields return
a stable `REJECTED` error and exit code 2 without replacing an existing output.
Supply only non-secret source and oracle locators: references are retained in
the full local report. The CLI summary never echoes those locators.

## Next release gates

Real integration work, an AI semantic requirements analyst, expert test design for each domain, credential vault, authenticated approvals, remote execution, SynapseRT writeback and the head-to-head Awesome QA Skills evaluation remain unfulfilled.
