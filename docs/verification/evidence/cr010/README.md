# CR-010 independent execution evidence

These are text copies of the TASK-036 tester outputs, including the first
failed test-oracle run. Only CRLF-to-LF normalization was applied; the manifest
records both original byte hashes and retained LF hashes. The tester report
is ../../design-methods-independent.md. No new execution was performed while
archiving these records.

`check-installed.py` is the actual Windows installed-wheel probe. Run it from
the repository root after building/installing the wheel into
`.qa-master/cr010-independent/venv`; it retains results under that ignored
directory and asserts the imported engine is in site-packages. Its socket and
process sentinels cover those paths only, not all possible external effects.

The logs record bounded local verification, not Gate, enterprise, release,
human acceptance or competitive evaluation evidence.
