# Architecture and improvement decisions

Load this guide when assessing system structure or proposing a substantial remediation. Treat the rows as questions to investigate, not a list of mandatory patterns. Keep a well-structured small system simple; scalability requires a workload, resource model, and operating constraints.

## Decision procedure

1. State the observed problem and the invariant, workload, change scenario, or operational objective affected.
2. Identify where the current design already enforces the required guarantee. Verify all entry points before proposing another layer.
3. Compare the smallest local repair, a component-level improvement, and a larger architecture change only if the latter is plausible.
4. Explain implementation cost, operational burden, consistency/security effects, compatibility, migration sequence, and failure modes introduced.
5. Provide measurable acceptance criteria. Recommend a larger pattern only when its benefits justify its costs under stated assumptions.

Apply SOLID, separation of concerns, dependency inversion, DRY, KISS, and YAGNI as reasoning tools. A principle's name, folder layout, class length, or pattern count is not proof of code quality. Prefer explicit invariants, cohesive ownership, clear contracts, and understandable failure handling. Consolidate duplicated business rules when they actually must evolve together; preserve distinct concepts that merely look similar today.

## Problem-to-option matrix

These are engineering decision aids. Consult the exact official pattern documentation and stack-specific behavior through `sources.md` before attributing requirements to a source.

| Observed problem | Options to evaluate | Evidence and costs to check |
| --- | --- | --- |
| Business rules depend directly on volatile providers/frameworks | Cohesive modules, ports/adapters, dependency inversion, an anti-corruption layer | Show expensive coupling or inconsistent semantics; avoid interfaces and wrappers that only rename stable calls. |
| Ownership or business boundaries are unclear | Domain-oriented modules, bounded contexts, explicit API/data ownership | Trace actual change coupling, transactions, and team responsibilities. Do not split one invariant across services without a consistency plan. |
| A monolith has an isolated scaling or deployment bottleneck | Improve module boundaries and local bottlenecks first; consider selective service extraction | Measure workload and independent release needs. Account for network failures, distributed state, operations, and team capacity. |
| Many flags or branches allow invalid lifecycle transitions | Explicit state model, transition guards, a transition table/state machine | Model permitted transitions, terminal states, actors, atomicity, and recovery. Do not introduce a workflow engine for a trivial sequence. |
| Concurrent writers violate a shared invariant | Atomic conditional update, uniqueness/constraints, optimistic concurrency, locks or stronger isolation | Demonstrate the interleaving and required isolation; handle conflicts, lock ordering, contention, and retry units. |
| Retried writes can duplicate effects | Stable operation identity, natural idempotency, atomic admission/deduplication, reconciliation | Verify scope, payload binding, retention, concurrent duplicates, unknown outcomes, and external provider semantics. |
| Database state and event publication can diverge | Transactional outbox, change-data capture, or another atomic/recoverable mechanism | Verify both durability boundaries, replay, ordering, duplicate consumption, retention, and publisher recovery. |
| A multi-service business operation can stop halfway | Explicit orchestration/choreography, saga/compensation where appropriate | Compensations are new business actions, not a database rollback. Handle failed compensation, irreversible effects, and operator decisions. |
| Read workload differs materially from write workload | Query/index improvement, read models/materialized views, CQRS when justified | Measure query and update demands; model freshness, access-control propagation, rebuilds, dual-model maintenance, and rollout. |
| Auditable historical reconstruction is an essential requirement | Audit log or event sourcing according to reconstruction needs | An ordinary audit log may suffice. Event sourcing adds schema evolution, replay, snapshots, privacy/retention, and projection recovery obligations. |
| A slow dependency monopolizes shared resources | Deadline/cancellation, bounded concurrency, bulkheads, circuit breaker when justified | Check pool budgets, failure thresholds, fallback truthfulness, half-open recovery, fairness, and existing SDK/platform controls. |
| Bursty work overwhelms synchronous capacity | Admission control, throttling, bounded queues, load leveling, backpressure | Bound queue age/size and retries; define rejection, priority, catch-up capacity, poison-message handling, and user-visible semantics. |
| Repeated expensive reads dominate cost/latency | Query reduction, batching, cache-aside/read-through when appropriate | Measure reuse/hit rate; model staleness, invalidation, stampedes, tenant keys, eviction, memory, and stale authorization risk. |
| A large dataset exceeds query/instance capacity | Better access paths, bounded pagination, partitioning, replicas, sharding when necessary | Measure growth and hotspots. Check replica lag, cross-partition constraints, skew, resharding, and operational complexity. |
| Long-lived workers can resume after losing ownership | Fencing/version checks, bounded leases, explicit job ownership | Show a stale-worker write path and where the shared authority rejects it. A lease by itself does not necessarily prevent stale effects. |
| Mixed versions or migrations break releases | Expand/contract schema changes, tolerant readers, explicit API/event versioning, feature rollout gates | Check all active clients/writers, defaults, backfill progress, index/constraint validation, and rollback limits. |
| Failure is hard to locate or repair | Structured errors, context propagation, useful telemetry, reconciliation tools, runbooks | Demonstrate a detection/recovery gap; protect secrets, cardinality, operator permissions, and auditable repairs. |
| Tests require fragile internals or permissive mocks | Contract tests, dependency boundaries, invariant/property tests, deterministic fault injection | Verify tests fail on actual contract violations; avoid elaborate scaffolding and tests that only restate implementation. |
| AI or tool workflows can exceed scope or budget | Server-enforced capabilities, validated tool arguments, bounded execution, isolated effects, independent authorization | A prompt is not enforcement. Trace user identity and provenance; test untrusted retrieved content and agent-to-agent messages. |

## Primary references to inspect by question

- [Microsoft Cloud Design Patterns](https://learn.microsoft.com/en-us/azure/architecture/patterns/) gives a broad discovery catalog. Treat Azure examples as examples, not deployment requirements.
- [Circuit Breaker](https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker) and [Bulkhead](https://learn.microsoft.com/en-us/azure/architecture/patterns/bulkhead) describe failure containment options; verify whether existing limits already solve the problem.
- [CQRS](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs), [Event Sourcing](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing), and [Cache-Aside](https://learn.microsoft.com/en-us/azure/architecture/patterns/cache-aside) document useful options and their consistency/complexity trade-offs.
- [Martin Fowler: Monolith First](https://martinfowler.com/bliki/MonolithFirst.html) is original architectural commentary, not a universal rule. Compare its reasoning with the repository's domain maturity, deployment needs, and operational capacity.
- Use the AWS idempotency/outbox, PostgreSQL isolation/migration, Google SRE, and Google review guidance in `sources.md` for the corresponding guarantees.

## Finding versus decision

A known violated invariant is a finding. Missing requirements or workload evidence are questions or gaps. A substantial architectural change is a decision with alternatives; do not inflate it into a Critical defect to make it sound urgent. Include the smallest safe fix even when recommending a larger future change.

For each substantial proposal record: problem, evidence, options, chosen/recommended option, why now, effort/dependencies, new risks, migration/compatibility, acceptance metrics, and the condition under which the recommendation should be reconsidered.
