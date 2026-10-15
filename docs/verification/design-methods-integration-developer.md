# TASK-035 integration developer verification

Date: 2026-10-15. Change: CR-010. Requirements: REQ-013, REQ-017, REQ-018,
NFR-005. Contract: DES-033 v2. Evidence Status: OBSERVED.

The Campaign CLI now invokes the design-method engine for explicitly supplied
models, stores its draft under `method_design`, and preserves the generic
requirement-by-dimension cases. Method-free inputs do not call the engine or
gain method-result fields. The shared JSON loader rejects malformed, duplicate
and non-finite input; failed generation leaves the previous report unchanged.
CLI errors contain stable codes. No execution or external adapter is invoked.

The public fixture `examples/design-methods.json` includes all three methods
and links its illustrative sources/oracles to a real local notes file. These
are fictional draft requirements, not approved production requirements.

Developer command:

`python -W error -m unittest tests.test_campaign_design_methods tests.test_campaign_cli -q`

Observed: 19 tests passed in 1.485 seconds after v2 integration. This covers
11 new integration tests plus 8 legacy tests. Syntax compilation and diff check
also completed successfully. The tests cover separate draft projection, legacy
behavior, empty models, no-oracle obligations, failed-write preservation, strict
intake, redacted errors, and process/network-call sentinels.

This is integration developer evidence only. TASK-034 engine algorithm findings
were still undergoing repair at this checkpoint; the passing integration cases
do not close them. Independent exact-model validation, installed-wheel smoke
and final full regression must run on the combined frozen implementation before
any bounded acceptance conclusion. No competitor result or project Gate is
established by this record.
