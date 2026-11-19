# Adaptive coverage catalog

## Contents

- [Use the catalog](#use-the-catalog)
- [Audit domains](#audit-domains)
- [Boundary matrix](#boundary-matrix)
- [Lifecycle challenges](#lifecycle-challenges)
- [Legacy, generated, vendor, and excluded paths](#legacy-generated-vendor-and-excluded-paths)
- [Primary-source pointers](#primary-source-pointers)

## Use the catalog

Select domains from the discovered system, then specialize each row to actual components, paths, invariants, and owners. Split a large domain by subsystem. Record a reason when a domain does not apply; record inaccessible evidence as a gap. This catalog is a starting set, not a limit on findings or a claim of exhaustive coverage.

For each applicable row, retain the inspected paths, checks performed, evidence, verification result, exclusions, and remaining uncertainty in the coverage ledger. A checklist mark without evidence is not completed review. Trace call sites and downstream safeguards before declaring an omission. Use the finding and confidence rules in `report-contract.md`; distinguish a demonstrated defect from a future risk, hypothesis, or optional improvement.

Consult `sources.md` for current, version-matched documentation. Research platform-specific semantics before judging them. A missing local control may be enforced by a framework, database, SDK, gateway, or deployment policy; verify that enforcement and its scope.

## Audit domains

### 1. Correctness and domain invariants

- **Apply:** Every executable subsystem; prioritize money, inventory, identity, entitlements, irreversible actions, and other valuable state.
- **Check:** Null, omitted, empty, malformed, duplicate, stale, and boundary inputs; overflow and precision; rounding and units; time zones and daylight-saving transitions; inclusive/exclusive ranges; ordering and pagination. Trace legal state transitions, terminal states, ownership, conservation rules, and acknowledgment of durable success.
- **Find omissions:** Partial results treated as complete; errors converted to success; unchecked return values; stale operation records; cleanup skipped on early exits; impossible states accepted by one entry point; equivalent commands with inconsistent rules.
- **Require proof:** State the invariant, reachable caller, feasible input or event sequence, actual result, and consequence. Inspect validation and constraints on every relevant entry point, including jobs and administrative paths.
- **Avoid traps:** Do not invent business rules. Distinguish intentional eventual consistency from a broken invariant, and undefined requirements from code that demonstrably violates an established contract.

### 2. Security, authorization, and privacy

- **Apply:** Untrusted input, identities, tenant boundaries, sensitive information, privileged actions, or exposed services.
- **Check:** Server-side object and action authorization; tenant scoping on reads/writes/exports; session/token lifecycle; privilege changes; reauthentication where required by the actual policy; injection; unsafe deserialization; SSRF and redirect handling; path traversal; uploads; browser-origin controls; encryption/key management; safe error/log content; retention and deletion.
- **Find omissions:** Alternate routes bypassing middleware; workers trusting spoofable tenant identifiers; authorization before a mutable ownership change; secrets in client bundles; callbacks trusted without authenticity/replay checks; deletion missing derived stores or active credentials.
- **Require proof:** Trace attacker-controlled input to a reachable sensitive operation and identify the missing or ineffective enforcement. For a configuration risk, establish exposure and the active configuration. Redact sensitive evidence.
- **Avoid traps:** CORS is not authorization; client-side checks do not establish server protection. Conversely, absence of a check inside one function does not prove a bypass. Do not declare regulatory compliance or failure from a source scan. Use applicable [OWASP ASVS](https://asvs.owasp.org/) requirements as a verification reference.

### 3. Persistence, transactions, and migrations

- **Apply:** Databases, files, object stores, caches used as authorities, schema changes, or durable business state.
- **Check:** Atomicity across related writes; commit/rollback handling; isolation assumptions; uniqueness and referential integrity; lost updates; lock ordering; query parameterization; replica lag; read-after-write requirements; pagination stability; archival and deletion; backup restoration compatibility.
- **Find omissions:** Dual writes with no reconciliation; writes acknowledged before durability; constraints bypassed by alternate paths; backfills that cannot resume; destructive schema changes during mixed-version rollout; unsafe defaults; migration locks or rewrites incompatible with expected table size; missing validation of historical rows.
- **Require proof:** Identify transaction boundaries, database/version semantics, competing execution order, and the state left after failure. Validate migrations on disposable representative data when needed; distinguish source-defined schema from the deployed schema.
- **Avoid traps:** Do not infer constraint behavior from `NOT VALID` or another keyword alone; check the installed database's semantics and intended migration sequence. A migration file is not proof it ran. Missing indexes require relevant query/workload evidence. See [PostgreSQL ALTER TABLE](https://www.postgresql.org/docs/current/sql-altertable.html), selecting the installed version.

### 4. Concurrency, cancellation, and resource lifetime

- **Apply:** Threads, goroutines, asynchronous tasks, shared state, multiple processes, or overlapping requests/jobs.
- **Check:** Data races; check-then-act races; atomic state transitions; locking and lock scope; deadlocks; cancellation propagation; abandoned work; ownership of resources; cleanup on every exit; bounded parallelism; connection/file/socket/task leaks; lease expiry and stale owners.
- **Find omissions:** Process-local locks protecting shared distributed state; locks released before dependent work completes; canceled request contexts used for mandatory cleanup without a bounded alternative; stale owners able to write after lease expiry; detached tasks with no lifecycle owner.
- **Require proof:** Provide an interleaving or lifetime trace with the competing actors and violated invariant. Use the runtime's race/concurrency tooling when appropriate, and report what paths actually ran.
- **Avoid traps:** Concurrency is not itself a race. An intentional immutable object can be shared safely. A clean race-detector run cannot establish safety of unexecuted paths; see the [Go race detector documentation](https://go.dev/doc/articles/race_detector) for that tool's scope.

### 5. Timeouts, retries, and failure containment

- **Apply:** Network/storage calls, dependency chains, retriable operations, request deadlines, or recovery loops.
- **Check:** Overall deadline and per-attempt timeout; retryable error classification; bounded attempts and backoff; jitter where synchronized retries matter; server retry hints; cancellation; retry amplification across layers; admission limits; ambiguous outcomes; idempotency identity, scope, persistence, and expiry.
- **Find omissions:** Retrying non-idempotent writes after an unknown result; regenerating the operation key on retry; deterministic failures retried forever; deadlines reset per hop; queue retries outliving deduplication protection; recovery storms; a fallback that returns false success.
- **Require proof:** Trace all retry owners, SDK defaults, total attempt/time budget, side effects, and failure classifications. Show the duplicate effect, excessive work, unbounded wait, or unavailable recovery path; verify provider-specific guarantees.
- **Avoid traps:** Do not retry every error or mandate retries everywhere. A lower layer may already retry. Circuit breakers, hedging, and fallback caches need a concrete failure model and must not introduce unsafe writes or stale authorization decisions.

### 6. Queues, events, webhooks, and external integrations

- **Apply:** Brokers, background workers, schedulers, callbacks, payment/email providers, or other asynchronous/external effects.
- **Check:** Delivery and acknowledgment semantics; duplicate/out-of-order events; poison messages; bounded retries; dead-letter ownership; replay controls; deduplication; publication relative to transaction commit; visibility/lease duration; competing consumers; provider rate limits; reconciliation.
- **Find omissions:** Acknowledging before durable handling; assuming exactly-once effects from a transport feature; losing events after a local commit; replay triggering duplicate business actions; failing silently after the retry budget; operator recovery without an audit trail; scheduler overlap.
- **Require proof:** Trace producer, transport, consumer, state update, and external effect. Model failure between adjacent steps. Cite the actual provider contract and show which application-level guarantee is missing.
- **Avoid traps:** A named outbox or saga is not mandatory if the required guarantee is met another way. A dead-letter queue is insufficient without recoverability, but its absence is not automatically a defect in every system.

### 7. API, schema, and cross-layer contracts

- **Apply:** Multiple modules, clients, services, SDKs, database representations, or independently deployed producers/consumers.
- **Check:** Request/response/schema alignment; optional versus nullable fields; enums; identifiers; numeric limits; units; time encoding; error meanings; status transitions; pagination; ordering; feature negotiation; backward compatibility; generated client freshness.
- **Find omissions:** Client unable to decode a reachable server value; defaults changing meaning across boundaries; different validation limits; retryable errors mapped to terminal UI state; a provider response accepted without checking required fields; version skew during rollout.
- **Require proof:** Inspect both sides and the translation layer at the same snapshot. Provide an example payload or transition that crosses the boundary and identify the observed or provable failure.
- **Avoid traps:** Different names or types may be intentionally mapped. A documentation mismatch is not necessarily a runtime defect. Validate generated artifacts against their actual schema and generation pipeline before calling them stale.

### 8. Configuration, CI/CD, and supply chain

- **Apply:** Build/deploy workflows, environment settings, containers, infrastructure definitions, credentials, dependencies, or release automation.
- **Check:** Configuration parsing and fail-fast validation; defaults and environment precedence; dev/prod differences; permissions; network exposure; secret delivery; immutable artifact identity; dependency provenance and lockfiles; workflow trust boundaries; untrusted PR execution; runner isolation; release gates; rollout and rollback compatibility.
- **Find omissions:** Required checks configured but never running; environment variables renamed on only one side; testing one artifact and deploying another; privileged jobs consuming untrusted artifacts; unsupported dependencies; known affected versions without mitigation; deployment limits contradicting application assumptions.
- **Require proof:** Trace the active trigger/job/configuration path, artifact lineage, effective permissions, and pinned versions. For an advisory, verify affected versions and conditions; distinguish vulnerable dependency presence from established exploitability.
- **Avoid traps:** Repository YAML does not establish deployed settings or hosted policy. A failed test differs from a test that never started. A version lag alone is not a vulnerability, and adopting every new release is not automatically safer.

### 9. Performance, scalability, capacity, and cost

- **Apply:** Hot paths, growing data, fan-out, background work, shared dependencies, expensive computation, or constrained devices/infrastructure.
- **Check:** Algorithmic growth; repeated queries; unbounded scans/materialization; connection and worker pools; payload/upload limits; allocation and retention; cache effectiveness/invalidation; request fan-out; queue growth; backpressure; fairness; noisy neighbors; startup and steady-state resource budgets.
- **Find omissions:** No bound on user-controlled work; data-dependent quadratic behavior in a growth path; retries consuming reserved capacity; concurrency greater than downstream capacity; hidden synchronous work; high-cardinality telemetry; expensive operations without quotas or cancellation.
- **Require proof:** State workload, data size, growth assumption, bottleneck mechanism, and measured or inferred evidence. Give a benchmark/acceptance criterion and explain the proposed change's cost and failure modes. Label unmeasured improvement estimates as hypotheses.
- **Avoid traps:** Do not invent speedups or declare an index, cache, sharding, queue, or microservices necessary without a workload argument. A local benchmark does not establish production capacity; average latency does not establish tail behavior.

### 10. Observability, operations, and recovery

- **Apply:** Long-running services, jobs, critical workflows, durable data, or any operation requiring failure diagnosis and recovery.
- **Check:** Useful error context; correlation across boundaries; redaction; health/readiness behavior; actionable metrics/alerts; bounded log/metric volume; dependency failure visibility; stuck-operation detection; reconciliation; backup/restore evidence; operator tools and auditability; graceful shutdown.
- **Find omissions:** Errors swallowed or logged without a failed outcome; health reporting healthy while critical work is unavailable; failures visible only through customer reports; no safe repair for a persistent intermediate state; recovery actions bypassing invariants; rollback instructions incompatible with changed data.
- **Require proof:** Trace a specific failure to its detection and recovery route. Identify the operational impact of a missing signal or repair mechanism. Differentiate configured backup schedules from a demonstrated successful restore.
- **Avoid traps:** More telemetry is not inherently better. Do not require a named observability vendor or alert on every exception. Logs may already be emitted by a shared boundary; verify duplication and privacy effects.

### 11. Tests, maintainability, and architectural change risk

- **Apply:** All maintained code; prioritize boundaries and invariants with costly failure or frequent change.
- **Check:** Tests for critical behavior and negative paths; deterministic fixtures; assertions that verify outcomes; integration contract fidelity; meaningful concurrency/failure tests; test isolation; flaky or skipped gates; dependency cycles; duplicated business rules; hidden side effects; obsolete code; ownership and extension points.
- **Find omissions:** Mocks conceal provider/database behavior; a test passes despite a failed async operation; coverage excludes production entry points; duplication causes demonstrated drift; a module reaches through another's invariants; unused fallback code no longer compiles or violates current contracts.
- **Require proof:** Link a testing gap to an important unverified behavior. For maintainability advice, show a concrete change scenario, coupling/duplication evidence, expected benefit, migration cost, and acceptance criteria.
- **Avoid traps:** Missing tests do not prove a bug. Coverage percentages and complexity scores are indicators, not correctness proofs. Avoid stylistic rewrites, pattern mandates, or architecture migrations unsupported by present or credible future needs.

### 12. Web behavior and accessibility

- **Apply:** Browser interfaces and web content; include embedded admin tools and checkout flows.
- **Check:** Loading/empty/error states; double submission; stale requests; navigation races; client storage failure; cache/session leakage; hydration/rendering failures; keyboard access; focus and modal behavior; accessible names; form errors; contrast, reflow, zoom, and reduced-motion needs.
- **Find omissions:** Durable actions acknowledged only in local UI state; paid or deleted items restored from stale storage; optimistic updates never reconciled; dialogs trap focus incorrectly; validation feedback unavailable to assistive technology; essential actions inaccessible without a pointer.
- **Require proof:** Trace UI state to the actual network/storage result; inspect rendered behavior for interaction/layout claims. Cite the relevant [WCAG criterion](https://www.w3.org/TR/WCAG22/) and observed failure when reporting an accessibility issue.
- **Avoid traps:** Static markup alone cannot establish all interaction or contrast outcomes. Automated accessibility scans do not establish full conformance. A cosmetic preference is an enhancement, not necessarily a usability defect.

### 13. Mobile, offline, and device lifecycle

- **Apply:** Native/hybrid mobile apps, installed web apps, offline operation, background work, or device-specific integrations.
- **Check:** App suspension/process death; foreground/background transitions; interrupted uploads; offline queues; conflict resolution; local schema migrations; secure storage; account switching; token refresh; permissions; deep links; notifications; platform-supported API versions; client/server release skew.
- **Find omissions:** Queued writes replay under a different account; offline actions bypass current server rules; stale persisted data revives completed operations; process death loses an idempotency key; push treated as a durable source of truth; local failure silently clears pending work.
- **Require proof:** Identify the platform/version and lifecycle or connectivity sequence. Trace persisted state, server reconciliation, and user-visible outcome; use an emulator/device only where the claim depends on runtime behavior.
- **Avoid traps:** A background task's timing may be platform-controlled. Do not infer delivery guarantees from notification configuration or claim store-policy violations without current official policy and matching facts.

### 14. AI, ML, retrieval, and agent tools

- **Apply:** Model inference/training, retrieval, embeddings, generated code, autonomous tools, or decisions materially influenced by model output.
- **Check:** Data/model/version lineage; training-serving consistency; leakage in evaluation; split quality; drift assumptions; reproducibility; privacy; retrieval authorization; tool permissions; prompt-injection boundaries; output validation; execution isolation; budget/loop limits; model timeout/fallback behavior.
- **Find omissions:** Retrieved text gains instruction authority; model output reaches SQL/shell/HTML without appropriate handling; user identity is lost in retrieval; cross-tenant caches; tools execute privileged actions from untrusted model arguments; retries multiply paid calls; a metric hides important failure slices.
- **Require proof:** Trace untrusted input through model/retrieval/tool boundaries to a concrete action or decision. For quality claims, inspect representative evaluation evidence and stated acceptance thresholds; distinguish model uncertainty from deterministic application defects.
- **Avoid traps:** A prompt is not an authorization boundary. A jailbreak demonstration alone does not prove privileged execution. Do not equate a benchmark score with real-world reliability or mandate RAG, fine-tuning, or a particular model without a task-specific evaluation.

## Boundary matrix

Trace both ends and every adapter. Assign an owner to each applicable boundary, even when each component already has a specialist.

| Boundary | Compare | Challenge |
| --- | --- | --- |
| Client ↔ API | Identity, enums, nullability, units, limits, errors, versions | Accepted input or emitted state cannot be represented on the other side |
| API ↔ domain ↔ database | Validation, invariants, authorization, transaction ownership | Alternate entry point or concurrent write bypasses the intended rule |
| Transaction ↔ external effect | Durability, operation key, acknowledgment, reconciliation | Effect succeeds but local commit/response fails, or commit succeeds before publication |
| Producer ↔ consumer | Schema, ordering, delivery, retries, deduplication, retention | Delayed replay or duplicate arrives after protection expires |
| Application ↔ provider | Contract version, permissions, timeouts, rate limits, ambiguous results | SDK behavior contradicts assumed retries or success meaning |
| Code ↔ config ↔ deployment | Names, defaults, feature flags, credentials, limits, runtime versions | Configuration is valid syntactically but activates an unsafe behavior |
| Migration ↔ old/new binaries | Read/write compatibility, defaults, constraints, backfills | Mixed-version rollout writes data the other version cannot handle |
| Cache/local state ↔ authority | Ownership, TTL, invalidation, versioning, reconciliation | Stale state overwrites or revives a durable terminal state |
| Documentation/tests ↔ enforced behavior | Claimed guarantee, exercised path, actual enforcement | A stated guarantee exists only in documentation or a permissive mock |

## Lifecycle challenges

Apply these to critical stateful operations; record cases not reviewed and why.

| Transition or interruption | Evidence to seek |
| --- | --- |
| Startup with missing/invalid dependencies | Validation, bounded initialization, readiness, cleanup after partial startup |
| Concurrent duplicate requests | Stable operation identity, atomic admission, safe repeated result |
| Timeout after unknown external outcome | Status lookup/reconciliation, duplicate prevention, truthful user state |
| Crash between durable steps | Recoverable state, replay safety, acknowledgment order, retained evidence |
| Cancellation or client disconnect | Deadline ownership, bounded necessary cleanup, no silent orphaned effect |
| Lease expiry, restart, or delayed worker | Stale-owner rejection where needed, ownership renewal, replay rules |
| Dependency outage and recovery | Bounded work, retry coordination, backpressure, catch-up capacity |
| Deploy, schema change, and rollback | Compatibility across active versions, resumable backfill, data-safe rollback limits |
| Expired/rotated credentials or account change | Refresh/revocation, least privilege, work retaining the correct identity |
| Retention expiry, deletion, or restore | Consistent derived stores, preserved invariants, recoverable references, authorization after restore |

## Legacy, generated, vendor, and excluded paths

- Identify generated sources and their generators, schemas, checked-in outputs, and drift checks. Usually fix the source of generation; inspect generated runtime behavior when it is on a critical path.
- Record vendored libraries, binaries, submodules, and large external trees with versions/provenance and relevant exposure. Dependency scanning can supplement review; it does not prove application-level safety.
- Distinguish unreachable legacy code from still-deployed older clients, compatibility adapters, scheduled jobs, maintenance commands, and disaster-recovery scripts. Verify reachability before reducing priority.
- Exclude build outputs, caches, fixtures, or vendor internals from broad reading only with a stated reason. Include them when they establish a relevant contract, vulnerability, deployed artifact, or regression.
- Record inaccessible repositories, runtime configuration, infrastructure, secrets-backed settings, and unavailable external service behavior as evidence gaps. Never mark them safe because they were not inspected.

## Primary-source pointers

The links above are starting points, not frozen requirements. Select the installed version and recheck status during each audit. Use the expanded source ledger in `sources.md` for retries, delivery, supply chain, security standards, and provider-specific guarantees; record the exact sources actually used in the report.
