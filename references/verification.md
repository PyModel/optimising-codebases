# Verification without changing the product

Use the smallest check that resolves a material uncertainty. Match commands to the detected stack, pinned versions, repository instructions, actual resources, and existing authorization. This guide is a selection aid, not a command list to execute indiscriminately.

## Contents

- [Set the execution boundary](#set-the-execution-boundary)
- [Classify the check](#classify-the-check)
- [Select by stack](#select-by-stack)
- [Prove the failure mechanism](#prove-the-failure-mechanism)
- [Challenge common false positives](#challenge-common-false-positives)
- [Record evidence and stop conditions](#record-evidence-and-stop-conditions)

## Set the execution boundary

1. Record the inspected snapshot and dirty paths before running checks. Preserve user changes. Run temporary reproductions in a disposable directory/worktree or the project's established test environment, without changing application sources or fixtures in report-only mode.
2. Inspect scripts, hooks, build files, test setup/teardown, analyzer plugins, dependency lifecycle scripts, and external endpoints before execution. A command named `test`, `lint`, `check`, `validate`, or `plan` can execute arbitrary code or contact live systems.
3. Reuse installed, pinned tooling and cached dependencies where possible. Inspect tool versions and help locally. Avoid blind package installation, upgrades, remote bootstrap scripts, `audit --fix`, formatter/linter fix modes, migrations, and generated-file regeneration. If required tooling is unavailable, use a safe alternative or record a blocked check.
4. Use appropriate isolation for code-executing checks: disposable working files, least privilege, no production credentials, bounded CPU/memory/time, and controlled network access. Set explicit local test targets and test credentials. Do not assume a container alone isolates host mounts or a Docker socket.
5. Use offline/no-download/locked modes when supported and compatible with the project's setup. Do not fabricate passing results when offline execution lacks dependencies. Record the limitation; do not change lockfiles or tool versions to get a green result.
6. Do not run production mutations, live exploit probes, charge/refund/email/SMS actions, destructive migrations, restore drills, chaos experiments, or network load tests as an implicit audit step. Keep safe local verification moving without repeatedly asking for permission already granted.
7. Redact command output and repro data. Do not place secrets, customer records, private URLs, or credentials in artifacts, shell history, public searches, or scanner uploads. Verify a scanner's data handling before allowing network use.

## Classify the check

| Class | Typical examples | Required handling |
| --- | --- | --- |
| Passive inspection | `rg`, bounded file reads, manifest/lockfile review, schema text, workflow/config review | Keep reads in scope; include relevant hidden configuration directories; avoid dumping credentials. Searches identify leads, not completed behavioral coverage. |
| Local analysis with executable extensions | Linters/type checkers with plugins, framework analyzers, build systems, code generation, compiler plugins | Inspect configuration and extensions, then isolate as necessary. Do not label these inert merely because they do not intentionally change application code. |
| Executable validation | Unit/integration tests, application import/startup, race detectors, builds, Rust build scripts/procedural macros, migrations | Inspect fixtures and lifecycle behavior; use disposable state, explicit endpoints, safe credentials, and resource bounds. Capture actual exit and completion status. |
| Network-dependent analysis | Advisory queries, registry resolution, remote analysis services, cloud configuration reads | Establish what leaves the environment and whether the destination/use is authorized. Prefer local/offline evidence when sufficient. Public technology research never needs private code. |
| Operational experiment | Load/chaos/failover/restore testing, deployment changes, production schema/data changes | Outside implicit report-only verification. Describe a concrete proposed validation plan if evidence requires this class; preserve existing explicit authorization. |

Do not run competing heavy checks simply because agent slots are available. Coordinate use of shared databases, ports, caches, CPU, memory, simulators, and service limits; sequence incompatible checks and give each isolated test a unique state namespace.

## Select by stack

| Detected stack | Useful checks after inspecting configuration | Specific cautions and evidence |
| --- | --- | --- |
| Go | Inspect `go.mod`, `go.sum`, toolchain, build tags, and actual call paths. Use focused existing `go test` cases, `go vet`, available pinned static analysis, and `govulncheck` when appropriate. Run targeted `-race` tests for reachable concurrency risks where supported. | Tests and cgo can execute code; toolchain/module resolution can download dependencies. Consider `GOTOOLCHAIN=local` and `GOPROXY=off` in an offline environment. A passing race run covers exercised schedules only; an unavailable toolchain is blocked evidence. |
| TypeScript/JavaScript | Inspect package-manager lockfiles, workspace graphs, `package.json` scripts, compiler and lint configuration. Use installed no-emit type checks, focused tests, and non-fixing lint/static analysis. Trace runtime validation across client/server contracts. | Package scripts, test setup, plugins, loaders, and builds execute code. Avoid commands that download a missing CLI implicitly. Type-check success does not validate external JSON; incremental/composite builds can write caches or generated outputs. |
| Python | Inspect `pyproject.toml`, dependency locks, supported interpreters, import paths, and test configuration. Use available pinned lint/type analysis and focused tests where useful. | Test collection and imports execute application code; plugins and fixtures can reach services or mutate data. Do not install or resolve new packages implicitly. Treat dynamic dispatch and optional imports as limits on static reachability conclusions. |
| Rust | Inspect `Cargo.toml`, `Cargo.lock`, features, targets, `build.rs`, and procedural-macro dependencies. Use appropriate focused `cargo check`, `clippy`, or tests with `--offline --locked` when feasible. | Compilation/checks can execute build scripts and procedural macros. OSV Rust call analysis is experimental and executes build scripts. Check feature/target coverage and unsafe/FFI boundaries; unsupported reachability is inconclusive. |
| JVM/.NET and other compiled stacks | Inspect build wrappers, pinned SDKs, build scripts, plugins, profiles, annotation/source generators, and framework configuration. Select established compilation/static analysis and focused tests. | Gradle/Maven/MSBuild and plugin/generator execution may perform arbitrary work. Confirm wrapper/tool integrity and cached dependencies; avoid broad lifecycle tasks before inspecting their effects. |
| iOS/Android/mobile | Inspect manifests/entitlements, permissions, transport configuration, storage, deep links, signing/release setup, API models, and supported platform versions. Use available targeted unit/UI tests and builds in the established local environment. | Xcode build phases and Gradle plugins execute code. Simulators/emulators and test accounts must be isolated. Static checks cannot verify app-store configuration, device-only behavior, push delivery, or production signing availability. |
| SQL/database | Inspect actual migrations, schema constraints, indexes, queries, isolation boundaries, and intended old/new application compatibility. Use a disposable database of the correct engine/version with representative non-sensitive data for focused migration/concurrency/query tests. | `EXPLAIN ANALYZE` executes the statement; even reads may invoke side-effecting functions. Never run it against production implicitly. Empty-table plans do not establish real-scale performance. Capture locks, data volume assumptions, and rollback/forward-recovery limits. |
| IaC/containers/CI | Review workflow triggers/permissions, image references, Dockerfiles, manifests, module/provider locks, and deployment configuration. Use already available parsers/policy checks or sandboxed validation. | Terraform plans/refreshes and providers can access real services; init can download code. Container builds run commands; Helm plugins and similar extensions can execute code. Missing remote settings are evidence gaps, not proven misconfiguration. |
| API/schema/async contracts | Compare both producers and consumers: OpenAPI/GraphQL/protobuf schemas, generated clients, event types, serializers, database columns, flags, and actual implementations. Use focused contract/round-trip/replay tests. | Specification conformance does not prove business invariants. Verify null/absent semantics, enums, error types, pagination, ordering, units, timestamps, and backward compatibility against actual deployed-version assumptions. |

Choose additional platform-specific checks only when scouts identify a relevant component. Document unavailable SDKs, operating systems, cloud settings, or device access without claiming those surfaces passed.

## Prove the failure mechanism

- Start with the caller, reachability conditions, input/state, and violated invariant. Inspect the entire relevant control path, including shared middleware, persistence guarantees, wrappers, SDK defaults, and effective deployment configuration.
- Prefer an existing focused regression test. If it cannot distinguish the behavior, build a minimal disposable reproduction with explicit expected versus observed results. Keep hypotheses separate from executed outcomes.
- For concurrency, use a controlled interleaving/barrier where possible; record ordering, shared state, transaction boundaries, and the invariant violation. Arbitrary sleeps or one successful run cannot prove race freedom.
- For retries and external effects, simulate timeout-before-acceptance, timeout-after-acceptance, lost response, duplicate delivery, reordered messages, and restart after each durability boundary as applicable. Do not contact a payment or messaging provider to manufacture a failure.
- For errors and cleanup, inspect each exit path and use fault injection locally when it resolves a real uncertainty. Verify cancellation propagation, resource release, error preservation, and operator-visible outcomes.
- For performance, state the suspected bottleneck and target workload before measuring. Capture environment, data size/distribution, concurrency, warm/cold state, repeated-run variability, and meaningful latency/throughput/resource measurements. Do not infer a production speedup from a toy benchmark or optimized-away work.
- Compare alternatives against a baseline using the same workload and correctness requirements. Report an unmeasured optimization as an opportunity with a validation plan, not a promised improvement.
- An independent reviewer should receive the claim and raw evidence, not an expected verdict. Reconcile counterevidence and severity explicitly. The report checker verifies report structure, not code correctness or empirical truth.

## Challenge common false positives

| Candidate | Required countercheck |
| --- | --- |
| Missing retry or timeout | Inspect inherited context/deadlines, SDK defaults and configuration, gateways, operation semantics, and total retry amplification. Some writes must not be retried without safe operation identity. |
| Empty `catch`, ignored error, or generic error | Trace whether error ownership intentionally moves to a caller, deferred cleanup, async reporter, or documented best-effort path. Establish a concrete lost outcome or observability failure. |
| Missing local auth or validation | Inspect shared enforcement, actual route exposure, object/tenant scoping, schemas, and database constraints. Client checks never substitute for a required server boundary. |
| PostgreSQL `NOT VALID` | Distinguish validation of existing rows from enforcement of new/updated rows; inspect the exact constraint type, migration phase, data census, and planned validation. |
| Blocking index creation | Check table size, write traffic, rollout timing, and allowed downtime. Concurrent creation has its own transaction/cleanup restrictions and is not universally preferable. |
| GitHub action referenced by a tag | Check platform support and workflow enrollment in the dependency lockfile. Inspect reusable workflow revisions separately; a lockfile merely existing is insufficient. |
| Dependency vulnerability alert | Verify ecosystem/package/version/advisory range and dependency scope. Separate affected-package presence from demonstrated vulnerable-call reachability. Unsupported or failed analysis is not proof of absence. |
| Missing tests, coverage threshold, or pattern | Identify the invariant at risk and existing assurance. A missing mechanism or low metric alone is an improvement/gap, not a proven runtime defect. |
| Missing backups, rate limits, or access controls in repo | Inspect accessible infrastructure and external enforcement evidence. If unavailable, state a verification gap; do not invent an operational fact. |
| Duplicate code, long function, or architectural inconsistency | Demonstrate divergent behavior, costly change propagation, unsafe coupling, or concrete maintenance impact; distinguish deliberate boundaries from accidental drift. |

## Record evidence and stop conditions

Use the report contract's ledger. For each check, retain a stable identifier, purpose, command or inspection method, working directory, snapshot, relevant tool versions/configuration, start/end or duration, exit status, redacted result location, interpretation, and limitations. Associate checks with the findings and coverage rows they support.

Use honest outcomes such as **passed**, **failed**, **blocked**, **inconclusive**, and **not-run**. A timeout, crash, missing dependency, skipped test, unavailable service, or permission failure cannot become a pass. Record meaningful test selection and excluded targets; distinguish a test assertion failure from an environment/setup failure. Preserve the original outcome when rerunning under changed conditions.

Assign findings `reproduced`, `static-verified`, or `hypothesis` as defined in the report contract. A complete, reachable static failure path can establish a defect without executing it; label it accurately. A successful reproduction proves that scenario, not all deployments or inputs. Never infer bug-detection completeness from file or test counts.

Before delivery, re-read the cited code and reconcile source changes with the inspected snapshot. Stop expanding verification once the remaining material uncertainty is resolved or accurately bounded, applicable coverage is reconciled, and significant findings have been challenged. Preserve concrete blocked next steps instead of repeating unchanged failing commands.
