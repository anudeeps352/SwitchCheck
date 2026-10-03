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
## 0.1.0a0 - 2026-10-01

### Added

- Initial project scaffolding, local development checks, and CI.
