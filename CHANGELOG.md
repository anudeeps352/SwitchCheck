# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Changed

- Narrowed the public MVP to classification and made the planned primary UX one
  `switchcheck.yaml`, one `switchcheck test` command, and one multi-model report.
  The other prototype task families are now explicitly future candidates rather
  than initial support claims.
- Reordered development around workflow simplification and deferred the UI
  until the CLI/config contract is stable.
- Added the planned assisted dataset-building lifecycle: automated sampling,
  redaction/deduplication, authoritative enrichment, LLM drafts, provenance,
  review routing, approval policies, immutable versions, and refresh.
- Defined the ten supported evaluation task types, explicit evaluator mapping,
  calibrated-judge boundary, four final case states, and unsupported use cases.
- Dataset imports now require `task_type` and reject declared evaluator/task
  combinations outside the product contract.
- Added versioned case contracts with task-specific evidence validation,
  structured criteria, reference/context persistence, safe legacy migration,
  and a provider-free `dataset check` command.
- Added typed exact, field, schema, numeric, pattern, tool-call, required-facts,
  and classification-metrics evaluators plus `PASS`, `FAIL`, `REVIEW`, and
  `ERROR` verdict composition.

### Added

- Dataset-level `--task-type` defaults and an initial `switchcheck evaluate`
  workflow with preflight validation and persisted four-state results.
- Task-aware experiment metrics, self-contained HTML reports, automatic report
  generation, and an offline labeled-evaluation demo.

- SQLite database initialization, schema versioning, and migration safeguards.
- LiteLLM chat recording wrapper, durable run history, and `switchcheck runs`.
- Candidate-model replay with dry-run selection, bounded concurrency, transient
  connection retries, and independently persisted results.
- Deterministic exact, contains, regex, JSON Schema, and JSON-field checks with
  persisted explainable verdicts; candidate provider errors count as failures.
- Self-contained replay reports with aggregate metrics, failure-first output
  comparisons, checker details, and reproducibility metadata.
- A synthetic invoice-extractor example and offline end-to-end smoke test.
- A two-provider support-ticket example for recording one model and replaying
  the same cases against another.
- Source-versus-candidate latency, token, cost, and pass-rate metrics in replay
  reports.
- Privacy, price-data, and provider-limit guidance for local recordings and
  generated reports.

### Fixed

- JSON Schema and JSON-field checks now accept responses wrapped in a complete
  Markdown JSON code fence.
- Replay selection now excludes recorded provider errors, while run history
  continues to retain and display them for diagnosis.
- Report checker labels identify configured JSON-field paths.

## 0.1.0a0 - 2026-10-01

### Added

- Initial project scaffolding, local development checks, and CI.
