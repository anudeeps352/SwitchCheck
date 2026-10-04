# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

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
