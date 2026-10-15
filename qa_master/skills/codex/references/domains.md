# Object-specific QA guidance

Choose by evidence in the supplied project. These profiles guide design; they are
not installed browser drivers, hardware simulators, SSH workers or measured coverage.

## Web and API

Map actors, sessions, tenant boundaries, state changes, persistence and side effects.
Read OpenAPI/routes plus relevant implementation where available. Check parameter
types, null/omitted/empty distinctions, numeric and size limits, pagination and sort,
authorization on individual objects, tenant isolation, duplicate and concurrent
requests, retry/idempotency and partial failures. Expected HTTP status and error
schema come from the contract; flag disagreement with code rather than adopting it.

For UI, cover navigation and stateful workflows, failure feedback, accessibility and
supported browsers as applicable. When writing Playwright/pytest scripts, use the
project's actual fixtures, selectors and authentication mechanism. Separate compile
or collection success from executing against a system. Do not invent endpoints,
test accounts, element locators, cleanup permissions or returned fields.

## Linux and system software

Identify supported distro/kernel/architecture, install/upgrade/rollback paths,
services, privileges, ports, storage/network topology and persistent data. Inspect
stateful operations, concurrency, I/O error handling, filesystem capacity/inodes,
resource limits, process/service restart, configuration precedence and observability.

For distributed or storage systems, model membership, quorum/leadership where
applicable, partitions, reconnect/retry, replica/metadata invariants, data integrity,
recovery, degraded operation and rolling upgrade compatibility. Cite the promised
consistency/durability model. Do not infer an RPO/RTO, quorum or acceptable data loss
from the current implementation. Fault injection, disk filling and network disruption
require an explicit disposable target, bounded impact and recovery procedure before
execution. Design-only work must not run these operations.

## AI computing software and hardware interfaces

Ask for the actual card/server, driver/runtime/compiler/framework/model revisions,
supported operators/dtypes/shapes, deployment topology and reference implementation
when these facts affect the task. Separate driver/runtime correctness, numerical
results, workload performance and business acceptance.

Design supported and unsupported operator paths, shape/dtype limits, dynamic shapes,
memory allocation/release and OOM recovery, concurrency, device reset/error reporting,
multi-device synchronization and fallback where documented. Define numerical oracle,
input distribution, determinism/seed, absolute/relative tolerances and comparison
precision from an approved contract or explicitly pending proposal. Never invent an
acceptable accuracy drop.

For inference performance, distinguish prefill/decode, TTFT, inter-token latency,
throughput, batch/concurrency, prompt/output lengths, warmup, cache/quantization and
memory pressure. Record power/thermal/power-limit conditions if relevant and available.
Only compare equivalent workload and correctness settings. Missing device access
does not block scenario design, but it blocks claims of actual device validation.
