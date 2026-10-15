# TASK-036 independent structured-method verification

- Evidence ID: EVIDENCE-DESIGN-METHODS-INDEPENDENT-001
- Tester: `/root/design_acceptance`, separate from engine and CLI implementation authors.
- Runtime work: `work-4722a15433ad4afc909452a4247e6da1`, attempt 2, claimed 2026-10-15T04:30:56Z.
- Result: PASS for the bounded checks below. Document State: DRAFT. Evidence Status: OBSERVED.
- No project Gate, human acceptance, business execution, remote integration, or superiority decision is made.

## Frozen subject and plan correction

Engine commit `e619c79`; CLI integration commit `8e6ab51`. No product source was edited by this tester.

| Input | SHA-256 |
|---|---|
| qa_master/design_methods.py | 63F12C1B36BB0F9DA2B8F13D1CFF687DD2CAC9DEBE1A71C963B5BDCE5378EE93 |
| qa_master/campaign_cli.py | 3D6DA1E1FC0F4B2EA5E0A54E42D4779F0BD7C0BC1EDFD5DF675605FF3E94A2CF |
| requirements v4 | 5638A3700F072BFFE5A58C212348966A263D60CDDBA17888314E22C1EBB4E99F |
| DES-033 v2 | F823304B68151A3127B0A4F0BC1F5479A69F7FE6A9664C95B328EB0449232CCC |
| tests/test_design_methods_independent.py | F250D0AA75AB5BD74E4F8570A6DF13587E036EA76D7D53952D1D12AFDD831F2B |

The older registered test-plan requirement hash is an erratum: this run uses the v4 hash above. Registered inputs were not changed during the claim. The old tester's seven preliminary tests are retained and supplemented by eleven independently authored acceptance tests; their prior run is not substituted for this execution.

## Independent test oracle and coverage

`tests/test_design_methods_independent.py` contains 18 tests. Expected finite points/classes and decision classes are declared in the test, not obtained by calling implementation helpers.

| Cases | Checks | Requirements |
|---|---|---|
| TC-DM-101–102 | Four open/closed integer combinations, exact ordered negative points and lower/upper origins; decimal negative fractional fixture; 34-digit integer and decimal neighbour overflow; exact deduplication, missing oracle versus genuine empty interval, both-invalid point, denominator and ratio | REQ-014, REQ-017 |
| TC-DM-103–105 | All six decision classes with exact count of linked obligations; true/1/string typed isolation; all six AST operators; 128/129 AST nodes, depth 8/9, 4096/4097 universe; ledger candidate/obligation IDs | REQ-015, REQ-017 |
| TC-DM-106–107,110 | Duplicate versus conflicting logical key; null-oracle edge preserves reachability; unreachable candidate obligation; terminal closed-world denials; 128/129 states, 512/513 records, 4096/excess pairs; self-loop, explicit invalid, one-state terminal empty graph; rule removal and all-excluded metamorphisms | REQ-016, REQ-017 |
| TC-DM-108 | Requirement/source/oracle digest drift changes every boundary ID; model/ref/domain/rule/state permutations preserve complete output; 100/101 models | REQ-013, NFR-005 |
| TC-DM-109 | Loader invalid UTF-8/JSON/nonfinite/duplicate keys; malformed decimal representations and types; bad locators; wrong oracle/guard/effect kinds; secret and float linked-requirement rejection; socket and child-process sentinels | REQ-013, NFR-005 |
| TC-DM-111 | Two fresh processes produce byte-identical canonical method JSON; legacy values preserved apart from input digest; CLI rejection leaves destination unchanged, leaks no secret, leaves no temp artifact | REQ-018, NFR-005 |

Candidate state assertions require DRAFT/PENDING/NOT_EXECUTED. Denominator and ledger links are checked; no semantic oracle content is inferred from referenced documents. Tests are finite representative contract checks, not exhaustive proof over all JSON inputs.

## Executed results

Commands ran on Windows using local Python, with ResourceWarning promoted to error:

```powershell
python -W error::ResourceWarning -m unittest tests.test_design_methods_independent -v
python -W error::ResourceWarning -m unittest discover -s tests -v
python -m pip wheel . --no-deps --no-build-isolation -w .qa-master/cr010-independent/wheels
python -m venv .qa-master/cr010-independent/venv
# Install the freshly built wheel into that venv with pip --no-index.
```

- Focused final: **18 tests PASS**, 1.126 seconds.
- Full strict regression: **510 tests PASS**, 21.677 seconds.
- Fresh wheel built and installed into a new venv with `--no-index`.
- Installed CLI executed from the evidence directory outside the repository import root. Its imported engine path was asserted to contain `site-packages`.
- Installed three-model fixture produced exactly 10 draft candidates and 3 obligations. Boundary missing-oracle metamorphism at the 34-digit maximum produced exactly 1 candidate and 2 obligations, one BOUNDARY_ORACLE_MISSING and one unrepresentable-neighbour obligation. Limit/AST rejection tests assert exact stable error codes.
- Three installed CLI scenarios PASS: valid methods, legacy bundle, secret-shaped-key rejection. Valid methods retained NOT_EXECUTED and campaign NOT_AUTHORIZED; legacy omitted method_design; rejection returned 2 and preserved exact destination bytes.
- Installed CLI was called with `socket.socket` and `subprocess.Popen` patched to fail if invoked, inside the installed process. No such invocation occurred. This detects these network/process paths, not every imaginable external API or adapter operation.

Raw local outputs are under `.qa-master/cr010-independent/`: `focused-first.txt`, `focused-final.txt`, `full-strict.txt`, `wheel-build.txt`, `wheel-install.txt`, `installed-wheel-results.json`, `installed-final.txt`, plus the installed runner `check-installed.py`. These are ignored local execution artifacts; this report and the independently executable test source are the Git-retained evidence summary.

## Preserved failures and corrections

1. First independent run: 16 tests, one failure. My test expected integer JSON output values while implementation emits canonical numeric strings. DES specifies canonical values but does not explicitly constrain integer output JSON type. The assertion now converts each value with exact `int()` before comparing ordered numeric values, retaining class/origin checks. This is a tester-oracle correction, not a product fix; the failed log remains `focused-first.txt`.
2. First installed-wheel checking script reached valid CLI output but failed to read it using Windows default GBK, because output is UTF-8. The tester script was corrected to read UTF-8. No product source changed. The final three installed cases succeeded.
3. DES prose mentions `reachability_basis`, whereas its exact analysis-key list excludes it. This run follows the exact key list; documentation clarification remains a reviewer concern and is not silently treated as a new schema field.

No product failure remained in these checks. Full V1 delivery, enterprise target validation, controlled paired comparison, and human acceptance remain outside this evidence and unresolved by it.
