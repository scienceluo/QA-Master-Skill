# CR-008 / CR-009 CI readback

Date: 2026-10-15. Evidence Status: OBSERVED. Read via GitHub API.

Published commit `7eb8025035da4201d37b29089d2ea79a003eab7f` has tree
`3e9e86f9a671e7ec7ba6cfccef8cdee1fa06d14d`, equal to the tested local
snapshot `5c0bfea25340f792334dfabe0b1ae80868737678`. The remote commit was
created through the connector; its metadata differs from the local commit.

The tester subsequently corrected the report header's overlay hash in local
`4f6e05a1ae3b6eba039016b183ec571578d8cbe1`; source and executable tests are
unchanged. Final documentation publication includes that correction.

Push run [38676544230](https://github.com/leongibhub/QA-Master-Skill/actions/runs/38676544230)
returned completed/success for all four jobs:

| Platform / Python | Job ID | Install / strict tests |
| --- | --- | --- |
| Ubuntu / 3.12 | 116231350674 | success / success |
| Windows / 3.10 | 116231350883 | success / success |
| Windows / 3.12 | 116231350892 | success / success |
| Ubuntu / 3.10 | 116231350927 | success / success |

Each job ran `python -m pip install .` and
`python -W error::ResourceWarning -m unittest discover -s tests -v`.
Local independent test counts and wheel evidence remain in
[the independent report](job-scheduler-test-results.md).

This readback establishes cross-platform local-package checks only. It does
not establish real transport, worker, IAM, enterprise execution, a project Gate,
release readiness, or full-V1 acceptance. The pull request remains a draft.
