# Primary-source discovery registry

Initial verification: **2026-11-18**. Treat this registry as a starting index, not a permanent statement of the latest release. Re-open the relevant primary sources during each audit and match the repository's actual versions, deployment model, provider, and threat model. Prefer the publisher's stable/versioned documentation; label drafts, previews, experimental features, and living guidance explicitly.

## Contents

- [Research procedure](#research-procedure)
- [Application and supply-chain security](#application-and-supply-chain-security)
- [Failure handling and distributed state](#failure-handling-and-distributed-state)
- [Databases and migrations](#databases-and-migrations)
- [Operations and code quality](#operations-and-code-quality)
- [AI and agent systems](#ai-and-agent-systems)
- [Source ledger](#source-ledger)

## Research procedure

1. Identify the actual dependency/runtime version from lockfiles, image digests, supported-version declarations, and available runtime evidence. Distinguish a declared range from an installed version and an intended deployment from a verified running deployment.
2. Search generic technology names and failure mechanisms. Never submit private code, credentials, customer data, or private infrastructure identifiers to public search or external analyzers.
3. Retrieve the relevant official section, release note, or upstream advisory. Follow a moving `current`, `latest`, or `main` URL to the appropriate version when possible; retain both the inspected version and access date.
4. Check applicability, existing controls, compatibility, and alternatives before recommending a pattern. A provider's example is not a universal requirement; a newer article is not automatically more authoritative than an applicable stable specification.
5. When sources conflict, prefer the actual version's documented behavior and primary release/advisory evidence. Explain unresolved conflicts. If access is blocked, preserve the code review and label the guidance unverified; do not claim current verification.

## Application and supply-chain security

| Source | Status observed on initial verification | Use and important limits |
| --- | --- | --- |
| [OWASP ASVS](https://asvs.owasp.org/) | **5.0.0 stable**, published 2025-05-30 | Use applicable application-security requirements and version-qualified requirement IDs. Source review alone cannot establish an ASVS verification level or certification. |
| [OWASP API Security Project](https://owasp.org/projects/api-security-project) | Canonical project lists **API Security Top 10 2023** | Check object, property, and function authorization; resource consumption; inventory and third-party API boundaries. This risk list is not a complete verification checklist. |
| [OWASP Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html) | Living guidance | Verify authorization at each applicable boundary, deny-by-default behavior, tenant isolation, and explicit permitted public access. Authentication or opaque identifiers do not prove authorization. |
| [NIST SSDF publication register](https://csrc.nist.gov/Projects/ssdf/publications) | **1.1 Final** (2022-02-03); **1.2 Draft** (2025-12-17); SP 800-218A **Final** (2024-07-26) | Distinguish final guidance from proposed changes. Repository evidence may not establish organization-wide development, disclosure, or incident-response practices. |
| [SLSA specification](https://slsa.dev/spec/v1.2/) | **1.2 Approved/current**; 1.1 marked Retired | Evaluate applicable Source and Build track guarantees, provenance, expected identities, and verification policy. Attestation presence does not prove its validity or consumption. Do not assign levels without the required evidence. |
| [GitHub Actions secure use](https://docs.github.com/en/actions/reference/security/secure-use) | Living platform documentation | Trace workflow triggers, untrusted checkout/input/artifacts, token permissions, secrets, OIDC, runners, and release controls. Assess effective privilege and execution paths rather than flagging a trigger by name. |
| [GitHub workflow dependency lockfiles](https://docs.github.com/en/actions/concepts/security/workflow-dependency-lockfiles) | Living platform documentation | Check workflow enrollment and `.github/workflows/actions.lock` coverage. Enrolled lockfiles cover direct/transitive actions and repository identities; reusable workflow calls need separate revision control. Verify platform support. A tag can be safely locked; file existence alone does not prove enrollment. |
| [OpenSSF Scorecard checks](https://github.com/ossf/scorecard/blob/main/docs/checks.md) | Evolving `main` definitions | Use as leads for repository/supply-chain practices. Check limitations and actual settings: unsupported SAST can score poorly, and the signature-presence check does not verify signatures. Platform documentation can supersede older checker assumptions. |
| [OSV-Scanner source scanning](https://github.com/google/osv-scanner/blob/main/docs/scan-source.md) | Evolving `main` documentation; Rust call analysis **experimental** | Resolve real package versions, advisory ranges, ignored paths, and supported reachability evidence. Rust call analysis executes dependency build scripts. Match commands to the installed scanner version; a scan is not always passive. |

## Failure handling and distributed state

| Source | Scope/status | Use and important limits |
| --- | --- | --- |
| [AWS Builders' Library: timeouts, retries, backoff, and jitter](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/) | Original engineering guidance; evergreen article, initially published 2019 | Inspect end-to-end deadlines, connection/request timeouts, transient-error classification, bounded retry budgets, jitter, and retry multiplication. Check SDK and infrastructure defaults before claiming missing retries or timeouts. |
| [AWS Builders' Library: safe retries with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/) | Original engineering guidance | Trace stable operation identity, replay semantics, concurrent duplicates, ambiguous success, retention, and changed parameters. Merely accepting an idempotency header does not make a write idempotent. |
| [Google SRE: addressing cascading failures](https://sre.google/sre-book/addressing-cascading-failures/) | Original SRE book guidance | Review overload, retry amplification, resource exhaustion, queueing, load shedding, and recovery behavior. Require workload/resource evidence before prescribing bulkheads or circuit breakers. |
| [AWS transactional outbox pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html) | Living pattern guidance | Inspect atomic state/event persistence, publisher recovery, duplicate delivery, ordering, and idempotent consumption. Use when a relevant dual-write problem exists; an outbox does not establish end-to-end exactly-once effects. |

## Databases and migrations

The following PostgreSQL `current` pages resolved to **PostgreSQL 18** during initial verification. Use the equivalent `/docs/<actual-major>/...` pages for the audited database. Check vendor forks and managed-service differences separately; do not infer server version from a client library.

| Source | Use and important limits |
| --- | --- |
| [PostgreSQL transaction isolation](https://www.postgresql.org/docs/current/transaction-iso.html) | Trace transaction boundaries, anomalies, row locks, concurrent updates, and serialization-failure handling. Validate the actual isolation level and full retry unit; retrying an arbitrary statement can preserve an invalid assumption. |
| [PostgreSQL ALTER TABLE](https://www.postgresql.org/docs/current/sql-altertable.html) | Inspect lock requirements, existing data, constraint enforcement, validation, and rolling-version compatibility. `NOT VALID` constraints can still enforce new/updated rows; distinguish existing-data validation debt from absent enforcement. |
| [PostgreSQL CREATE INDEX](https://www.postgresql.org/docs/current/sql-createindex.html) | Evaluate size/write traffic, index validity, definition, and operational sequencing. Ordinary index creation can be appropriate for empty tables or planned downtime; concurrent creation has restrictions and failed builds can leave invalid indexes. `IF NOT EXISTS` does not validate an existing definition. |

## Operations and code quality

| Source | Scope/status | Use and important limits |
| --- | --- | --- |
| [OpenTelemetry Collector resiliency](https://opentelemetry.io/docs/collector/resiliency/) | Living documentation; page modification observed 2026-01-14 | Inspect retry/queue limits, exporter capabilities, disk persistence where needed, and failure telemetry. Match the Collector and component versions. Do not require persistent queues when loss tolerance and the operating model do not justify them. |
| [Kubernetes liveness, readiness, and startup probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/) | Living, Kubernetes-specific documentation | Apply only to an actual Kubernetes deployment; match the cluster version. Trace startup time, traffic readiness, liveness, and restart loops. A dependency outage should not automatically cause every healthy process to restart. |
| [AWS Well-Architected recovery testing](https://docs.aws.amazon.com/wellarchitected/latest/framework/rel_backing_up_data_periodic_recovery_testing_data.html) | Living AWS reliability guidance | Request or inspect recovery evidence, integrity checks, recovery objectives, and dependencies. Backups absent from source are an evidence gap, not proof that backups do not exist. Do not perform a live recovery exercise during an implicit audit. |
| [Google engineering practices: what to look for in review](https://google.github.io/eng-practices/review/reviewer/looking-for.html) | Living engineering guidance | Examine design, functionality, concurrency, understandable complexity, useful tests, naming, comments, documentation, and context. Distinguish local conventions and preferences from defects; justify refactors with actual costs and benefits. |

## AI and agent systems

Apply only when the repository uses the relevant capabilities; these are risk and engineering guides, not proof of legal compliance or certification.

| Source | Status observed on initial verification | Use and important limits |
| --- | --- | --- |
| [OWASP LLM application risks](https://genai.owasp.org/llm-top-10/) | Canonical page presents **2025** list | Inspect prompt/data boundaries, sensitive information, model/data supply chains, output handling, retrieval authorization, excessive agency, and resource limits. Model instructions do not replace server-side authorization. |
| [OWASP Agentic Applications Top 10](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/) | **2026** edition; resource dated 2025-12-09 | Use for agent goals, tools, identities, inter-agent trust, memory/context, and cascading failures. Map risks to actual capabilities and effects; additional agents do not inherently provide independent assurance. |
| [OWASP Securing Agentic Applications V2](https://genai.owasp.org/resource/securing-agentic-applications-v2/) | Published **2026-11-10**; guide landing page verified | Discover current architecture, access-control, runtime, supply-chain, and assurance guidance. Retrieve and inspect the guide itself before attributing detailed controls to it; the landing page alone establishes only its scope and publication. |

## Source ledger

For every material external claim, use the report contract fields `id`, `title`, `publisher`, `url`, `accessed_at`, `version_status`, `supports`, and `applies_to`. Keep additional version/revision and limitation details as extra metadata when useful. Record a publication/update date only when the source provides one. Keep the source's stated requirement separate from the auditor's inference about the repository. A citation supports a claim; it does not establish that the code violates it.

For a dependency advisory, also retain the advisory identifier, ecosystem/package, inspected installed version, affected range, fixed version if available, dependency scope, and reachability evidence. Prefer the upstream advisory and actual package release history over remembered vulnerability details or search snippets.
