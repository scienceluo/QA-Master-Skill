# GitLab CI attestation contract

**Task:** TASK-006. **Traceability:** REQ-007, REQ-012, NFR-001, NFR-003 and
NFR-004. **Evidence state:** local contract testing only; `NOT_EXECUTED` against
any GitLab deployment.

`assess_ci_job` binds a caller-pinned project, job, pipeline, 40-character commit
SHA, ref and environment to GitLab REST v4 responses. It requires successful job
and pipeline states, matching job/pipeline/ref/SHA metadata, and the job's boolean
`tag` field. It does not read a made-up `pipeline.ref_protected` attribute.

When ref protection is required, a branch job uses
`GET /projects/:id/protected_branches`; a tag job uses
`GET /projects/:id/protected_tags`. The expected ref must match a returned exact
or wildcard protected-ref name. Missing job `tag`, unsupported readers, lookup
errors, invalid records, or no matching protected ref fail closed. The GitLab API
documents the protected branch and protected tag collections and their wildcard
names; see [protected branches](https://docs.gitlab.com/api/protected_branches/)
and [protected tags](https://docs.gitlab.com/api/protected_tags/), consulted
2026-10-14.

`fetch_job_junit` can then retrieve a bounded ZIP through an injected artifact
transport, parse one bounded JUnit entry, bind its digest to the requested run and
pass it to the release gate. It retains `source_authenticated=False` and
`CI_ARTIFACT_FETCHED_NOT_ATTESTED`; even an evidence verifier callback cannot turn
this local metadata/artifact path into a release-ready result.

JUnit XML is decoded only as UTF-8/16/32, rejects DTD/entity declarations before
parsing, and rejects namespaces. Evidence binding reparses the raw artifact with
the supplied case map and rejects a caller-modified parsed outcome. ZIP artifacts
are processed in memory and temporary workspace only. Retention/deletion of GitLab
job artifacts is intentionally not implemented: service retention policy, legal
hold, storage class, and deletion authorization are deployment decisions requiring
an approved operational record.

Verification command: `python -m unittest tests.test_ci_attestation
tests.test_gitlab_ci_integration tests.test_junit_ingest tests.test_evidence_binding
-q`. This is not a production call, deployment result, or acceptance decision.
