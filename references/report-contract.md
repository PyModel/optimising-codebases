# Audit report contract

## Contents

- Evidence and classification
- Severity and priority
- JSON shape
- Coverage and completion
- Report quality gate

## Evidence and classification

A finding must connect source evidence to a consequence. A candidate from a regex, complexity metric, dependency scanner, or model intuition is a lead until its context is verified.

Use separate dimensions:

| Field | Values | Meaning |
|---|---|---|
| kind | defect, risk, improvement | Current incorrect behavior; conditional future failure; optional justified improvement |
| verification | reproduced, static-verified, hypothesis | Executed evidence; complete code/contract reasoning; unresolved assumption |
| confidence | high, medium, low | Strength of available evidence, independent of impact |
| severity | critical, high, medium, low, info | Consequence under stated feasible conditions |
| priority | P0, P1, P2, P3 | Urgency and sequencing in this project |
| effort | S, M, L, XL, unknown | Rough implementation/validation scope, not a promised duration |

A `static-verified` item requires reachable code evidence and checked counterevidence. A `reproduced` item additionally references an actually executed command and describes its result. If external enforcement or deployment state is unknown, retain the issue as a hypothesis unless the conclusion is valid without that fact.

Verified defect totals include only `kind=defect` with `verification=reproduced` or `static-verified`. Present risks, hypotheses, and improvements separately. Never count the same item in multiple primary totals. Conditional high-impact hypotheses must be clearly labeled and excluded from verified defect counts.

For optimizations, use `kind=improvement` unless there is an independently demonstrable correctness/resource-limit failure. Put workload assumptions in `preconditions`, mechanism in `failure_sequence`, evidence/measurement limits in `verification_detail`, and benefit trade-offs in `tradeoffs`. Unmeasured speedup claims cannot be `reproduced`.

## Severity and priority

Calibrate against exposure, likelihood, blast radius, recoverability, sensitivity, and existing controls:

- **Critical:** A feasible path to catastrophic compromise, widespread irrecoverable loss, or equivalent project-specific impact. Require strong evidence and independent review; do not use the label for a merely scary possibility.
- **High:** Serious unauthorized access, money/data integrity loss, sustained important outage, or equivalent reachable impact with material exposure.
- **Medium:** Meaningful correctness/reliability/security degradation with bounded scope, additional prerequisites, or an effective recovery path.
- **Low:** Limited effect or a small, localized robustness issue.
- **Info:** Evidence-backed improvement or informational observation without a demonstrated harmful failure.

These are qualitative guides, not a security scoring standard. Do not invent CVSS numbers. Cite an advisory's published score separately if relevant.

P0 means urgent containment; P1 means an important near-term repair; P2 means planned remediation; P3 means optional/later improvement. Priority can differ from severity because of exposure, prerequisites, and repair dependencies; explain that difference in the impact or next action. Effort must never lower severity.

## JSON shape

Start from `assets/audit-template.json`. Replace its illustrative metadata; keep empty arrays only when the audit established there are no entries. Use schema version `1.0`. Extra metadata is allowed; defined fields must obey the contract. All textual evidence must be redacted. Times must be ISO 8601 with a timezone; source access dates use YYYY-MM-DD.

### Top-level fields

| Key | Required shape |
|---|---|
| schema_version | `1.0` |
| audit | Metadata object below |
| coverage | Nonempty list of coverage rows |
| findings | List of findings, including clearly classified hypotheses and improvements |
| commands | List of verification command records, including blocked/not-run planned checks |
| sources | Source ledger, or empty with a limitation if online verification was unavailable/unneeded |
| adjudication | Discarded, duplicate, and deferred candidate records |
| next_actions | Remediation/verification plan ordered by priority and dependency |
| resume | Object with `pending_tasks` and `notes` string arrays |

### audit

Required: `id`, `repository`, `snapshot`, `started_at`, `completed_at`, `mode`, `completion`, `working_tree`, `scope`, `exclusions`, and `limitations`.

- `snapshot`: full revision plus dirty-tree fingerprint description when applicable; for non-Git input use inspected-file hashes. Distinguish source snapshot from live deployment identity.
- `mode`: `full`, `focused`, or `delta`.
- `completion`: `complete` or `partial`; this describes the review plan, not bug-free software.
- `working_tree`: `clean`, `dirty`, `not-git`, or `unknown`.
- `scope`: nonempty string array. `exclusions` and `limitations`: string arrays.
- `baseline` identifies the prior report or snapshot. Delta mode requires a nonempty string. The field is optional in other modes.

### coverage[]

Required: `id`, `area`, `paths`, `owner`, `status`, `checks`, `evidence`, `gaps`.

- `status`: `reviewed`, `partial`, `blocked`, `not-reviewed`, or `not-applicable`.
- `paths`, `checks`, `evidence`, `gaps`: string arrays. Use exact relative paths/symbols in evidence.
- A reviewed row needs paths, checks, evidence, and an owner. Other statuses need an explicit reason and next step in `gaps`; not-applicable needs a reason, not a fictional next task.
- Coverage is a record of performed checks, not a claim that all lines or all bugs were examined. Describe sampling in gaps and mark partial when planned breadth remains unmet.

### findings[]

Required scalar strings: `id`, `title`, `kind`, `category`, `severity`, `confidence`, `verification`, `priority`, `fingerprint`, `invariant`, `impact`, `recommendation`, `verification_detail`, `effort`.

Required arrays: `locations`, `preconditions`, `failure_sequence`, `counterevidence`, `validation`, `tradeoffs`, `coverage_ids`, `command_ids`, `sources`. The first six need at least one entry; `tradeoffs` can state that a proposed small change has no identified material trade-off. ID references must exist in their ledgers. Every finding must reference at least one coverage row, and `coverage_ids` must exclude rows marked `not-applicable`.

- `id`: stable `AUD-001`-style identifier; do not renumber persistent findings merely to sort them.
- `category`: descriptive domain such as security, correctness, data-integrity, resilience, contract, configuration, performance, scalability, supply-chain, privacy, testing, accessibility, or maintainability.
- `fingerprint`: stable description of invariant + cause + remediation boundary. Duplicate fingerprints require adjudication/merging.
- `locations[]`: objects with `path`, `start_line`, `end_line`, `symbol`, `observation`. Use repository-relative, traversal-free paths; lines are positive integers. Inspect both sides of a cross-layer mismatch. Never cite invented lines or a different snapshot.
- `preconditions`: feasible input, state, permissions, workload, or deployment conditions.
- `failure_sequence`: ordered concrete steps from trigger to violated invariant. For improvements, explain the observed cost and mechanism of benefit.
- `counterevidence`: specific controls/callers/configuration examined and why they do or do not defeat the candidate.
- `validation`: acceptance checks for the proposed fix; prefer reproduction of the actual failure.
- `command_ids`: executed verification references; required for `reproduced`, may be empty for static verification.
- `sources`: IDs of directly supporting sources; local evidence alone can support a simple code defect.

Required `independent_review` object: `status`, `reviewer`, `reason` strings. Status is `accepted`, `revised`, `unavailable`, or `not-required`. Non-hypothesis Critical/High findings require accepted/revised independent review or an explicit unavailable reason also reflected in audit limitations. Do not describe a self-review as independent; name the self-review and capacity limitation honestly. Keep rejected candidates in adjudication.

### commands[]

Required: `id`, `command`, `environment`, `status`, `exit_code`, `summary`.

Status is `passed`, `failed`, `blocked`, `not-run`, or `inconclusive`. `exit_code` is an integer for completed commands, otherwise null. A passed command must have exit code zero. Record where execution occurred and whether code ran against disposable resources. Do not log secrets or credentials in commands. Optional fields: tool versions, duration, artifact path, bounded output, and side effects. A failing assertion can reproduce a bug; do not mislabel it as an infrastructure failure.

### sources[]

Required nonempty strings: `id`, `title`, `publisher`, `url`, `accessed_at`, `version_status`, `applies_to`, `supports`. Use an actual HTTP(S) URL, date YYYY-MM-DD, version/status such as stable, draft, living, or exact runtime version. State exactly which claim the source supports and how the installed technology matches. Preserve source limitations and conflicting evidence in `applies_to` or extra fields. Do not attach a source merely because its title sounds relevant.

### adjudication[] and next_actions[]

Adjudication records require `candidate`, `decision` (`rejected`, `duplicate`, `deferred`), `reason`, and `related_finding` (existing finding ID or null).

Next actions require `id`, `priority`, `action`, `finding_ids`, `depends_on`, and `acceptance`. `finding_ids` references findings; `depends_on` references other actions. State rollout, compatibility, and operator/product prerequisites in the action. The dependency graph must be acyclic. An action can address a coverage gap with an empty finding list. The validator warns for each P0 or P1 finding that no action references in `finding_ids`.

## Coverage and completion

Use partial completion whenever applicable coverage remains blocked, partial, or not-reviewed, or pending tasks remain. A full-mode partial report is an incomplete full audit, not a completed sample. Final coverage may be reviewed or justified not-applicable only when completion is complete. Running every possible tool is unnecessary; state which verification methods were chosen and why.

Record unavailable online guidance, deployment settings, runtime workload, backups, credentials, or external controls as limitations rather than inventing values or interpreting absence as failure. At least one limitation should describe the source/runtime evidence boundary even when the planned review is complete.

## Report quality gate

Run `scripts/check_report.py audit.json --render report.md`. It checks schema consistency, references, duplicate IDs/fingerprints, completion, reproduction records, and action dependencies; it calculates totals. It cannot establish truth, severity, actual coverage, or whether a reproduction is meaningful. Review those manually.

Confirm the final report contains exact scope/snapshot, separate classifications and counts, evidence and counterevidence, actual command outcomes, primary-source claims, independent-review limits, and a dependency-aware remedy plan. Do not replace the full report with a top-five list. The chat summary can highlight the most consequential items and link to the complete artifacts.
