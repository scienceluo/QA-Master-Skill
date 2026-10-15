# Enterprise adapter contract

**Task:** TASK-006 (enterprise adapter slice)  
**Requirements:** REQ-007, REQ-012, NFR-003, NFR-004 in the central RTM.  
**State:** development evidence only; no external deployment or acceptance is claimed.

## Requirements and acceptance criteria

| Derived acceptance | Requirement | Measurable acceptance |
| --- | --- | --- |
| AC-TASK-006-01 | Jira reads use only a validated HTTPS origin, bounded JSON responses, and never follow redirects with credentials. | Unsafe origins/paths are rejected; a redirect raises an adapter error; response size is capped. |
| AC-TASK-006-02 | Jira project and issue reads use the documented Jira REST v2 paths. | `GET /rest/api/2/project/{key}` and `GET /rest/api/2/issue/{key}` are issued through an injectable transport. |
| AC-TASK-006-03 | Jira issue create/update writes require a caller-supplied trusted approval verifier for the exact action, target and canonical JSON payload, plus a durable journal entry. | Omitted, false, or scope-tampered verification performs no request; response loss is `UNKNOWN` and never re-posted automatically. |
| AC-TASK-006-04 | Confluence page reads use a validated HTTPS origin and the documented REST v2 page route. | `GET /wiki/api/v2/pages/{id}` supports requested version/body expansions. |
| AC-TASK-006-05 | A write journal is durable and idempotency-safe. | Same key and same payload resumes; same key with changed action, target or payload is rejected; lost responses become `UNKNOWN` and are never retried implicitly. |
| AC-TASK-006-06 | SynapseRT is deployment/version specific. | No SynapseRT request can be made without an explicit, validated deployment API profile; unsupported actions fail clearly. |

## Design

`SafeJsonTransport` is the single standard-library HTTP boundary. It accepts an
injectable in-process transport for tests; its network implementation permits HTTPS
only, uses a fixed timeout and response limit, and rejects every redirect. The
network exception messages deliberately contain exception classes/statuses, not
request headers or tokens.

`JiraAdapter` owns Jira Cloud REST v2 path construction. Its public issue
create/update methods require a `WriteCoordinator`, idempotency key and verifier;
they cannot directly issue POST/PUT requests. Create additionally requires an
explicit trusted host reconciliation resolver. The resolver is deployment-specific
and must return exactly one candidate issue key using an approved correlation
lookup; QA Master does not invent a Jira custom field or search query. Without it,
the create method rejects before any network write. The coordinator journals and
claims the operation before it calls the adapter. Jira readback fetches the created
issue key returned by a create response, or the target issue for an update, and
only an exact match of requested Jira fields can satisfy
`JiraAdapter.matches_readback`. An HTTP 2xx response remains `SUBMITTED`, never
`VERIFIED`.

For Jira's enriched read representations, matching treats a submitted object as a
typed recursive subset: every submitted dictionary key must be present and match;
lists retain exact length and order; scalar type and value must match. Extra keys
returned by Jira do not invalidate an otherwise matching submitted object.

If a create response is lost and the resolver returns zero or multiple candidates,
automatic recovery is unavailable and the entry remains `UNKNOWN`; it is never
retried. `WriteCoordinator.reconcile_manual` supports a human-supplied exact
candidate key only after a separate verifier approval bound to that candidate. It
then performs a GET and the same payload match. A transient readback error records
the error separately and preserves an already-known remote result, including the
create key, for a later GET retry.

`OperationJournal` persists operation intent atomically in a local JSON file and
uses an exclusive lock file for mutation. `WriteCoordinator` claims the operation
as `UNKNOWN` before the remote call, so a crash at the irreversible boundary cannot
replay the write; a stale journal lock fails closed for operator review. A later
process can only use
`reconcile` with the adapter's readback result. `VERIFIED` needs an explicit matching
readback predicate. A mismatching readback records `READBACK_MISMATCH`.

`SynapseRTAdapter` is deliberately generic: an administrator must supply a reviewed
profile containing the exact deployment origin and action-to-method/path contract.
The adapter does not guess vendor endpoints, API versions, payload fields, or
readback semantics. A coordinator-created bound approval envelope must match the
profile's exact deployment ID, HTTP method and path before it can send a write.

## Limits and operational evidence

The built-in HTTP auth scheme is a bearer token passed by the caller or environment
integration; credential storage, identity verification, TLS pinning, rate-limit
policy, remote audit retention, and real Jira/Confluence/SynapseRT compatibility
testing are outside this task. Do not put secrets in profiles, journal payloads, or
logs. A local test pass proves only these contract guards. It is not production
connectivity, third-party write, or system acceptance evidence.

GitLab's `allow_http=True` exists only for unauthenticated local fixtures. Passing a
token with an HTTP origin is rejected, so `PRIVATE-TOKEN` cannot be sent in clear
text.

Jira paths and Confluence page route are based on Atlassian's official API references:
[Jira Projects](https://developer.atlassian.com/cloud/jira/platform/rest/v2/api-group-projects/)
and [Confluence Pages](https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-page/),
consulted 2026-10-14. The Jira issue endpoint contract should be rechecked against
its deployment's supported Jira API before enabling a real write.
