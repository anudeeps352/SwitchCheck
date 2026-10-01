# Switchcheck development plan

## Goal and definition of done for v0.1

Ship an installable Python package that lets a developer record a small set of
non-streaming LLM calls, replay them on a different model, check the results,
and open an HTML report. The workflow must run locally with a fake provider in
CI and with a real provider in the example.

v0.1 is done when the following works from a clean environment:

```text
install package → init → record sample calls → replay with fake/real model
→ evaluate deterministic checks → generate report
```

## Delivery stages

| Stage | Outcome | Exit criteria |
|---|---|---|
| 0. Foundations | Repository can be installed, checked, and tested. | `pyproject.toml`, `src/` layout, CLI shell, test tooling, formatting/linting and CI are green. |
| 1. Recording | Real calls become durable runs. | `init`, SQLite migrations, client wrapper, token/latency/error capture, and `runs` listing are tested. |
| 2. Replay | Recorded inputs can be run against a candidate model. | Selection, dry-run cost estimate, bounded concurrency, retry policy, partial-result persistence, and fake-provider tests work. |
| 3. Evaluation | A replay answers whether outputs remain acceptable. | Exact, contains, regex, JSON Schema checks; structured verdicts; errors count as failures. |
| 4. Reporting | Results are understandable without a server. | Self-contained HTML report with aggregate metrics, regressions, output comparison, and reproducibility footer. |
| 5. Release readiness | Others can install and trust v0.1. | Example app, documentation, security/privacy notes, package build, smoke test, changelog, and tagged release. |

Work stages in order. Do not start an LLM judge, agent traces, web UI, or
additional language SDKs until Stage 5 is accepted.

## Initial work breakdown

### Stage 0 — Foundations

- Create package skeleton and `pyproject.toml` for Python 3.10+.
- Choose and configure: `pytest`, Ruff (lint + format), MyPy or Pyright, and
  pre-commit hooks.
- Add an MIT license, contribution guide, supported-Python policy, and a minimal
  README with development setup.
- Create GitHub Actions CI before feature work.

### Stage 1 — Recording

- Implement migrations and repository-owned SQLite access.
- Implement `switchcheck init` and clear project-location discovery.
- Add `client.chat()` over LiteLLM with safe request normalization.
- Persist successful responses and provider errors consistently.
- Add unit tests for migrations, serialization, and `runs` filtering.

### Stage 2 — Replay

- Build a provider interface that tests can replace with a deterministic fake.
- Implement selecting runs by tag, IDs, and sample size.
- Implement replay session/result persistence before model execution.
- Add concurrency control, retry classification, cancellation/interruption
  behavior, and a dry-run estimate.
- Test timeouts, invalid parameters, partial failures, and resume behavior.

### Stage 3 — Evaluation

- Define checker protocol and verdict schema.
- Add exact, contains, regex, JSON Schema, and JSON field checks.
- Validate checker configuration at command start.
- Calculate aggregate pass rate without hiding errors.

### Stage 4 — Reporting

- Create a static Jinja2 report template with inline assets.
- Include summary metrics, regression-first case list, detailed checker reasons,
  and reproducibility configuration.
- Add golden-file and accessibility-oriented HTML checks.

### Stage 5 — Release readiness

- Build a synthetic invoice-extractor example with no sensitive data.
- Add an end-to-end smoke test using the fake provider.
- Document quickstart, price-data limits, privacy/redaction, provider limits,
  and troubleshooting.
- Publish release notes, tag the version, build artifacts, then publish to PyPI.

## Versioning and release policy

Use Semantic Versioning from the first public package release.

| Version range | Meaning | Examples |
|---|---|---|
| `0.y.z` | Pre-1.0: minor versions may introduce planned breaking changes; patches are backward-compatible fixes. | `0.1.0` MVP; `0.2.0` agent traces. |
| `1.y.z` | Stable public API: breaking public changes require a major version. | Future stability milestone. |
| prerelease | Explicitly unstable release candidate. | `0.1.0rc1`. |

Version source of truth: one value in `pyproject.toml`; package metadata, CLI
`--version`, report footer, and release artifacts derive from it. Use annotated
Git tags named `vX.Y.Z`. Keep a human-readable `CHANGELOG.md` under the Keep a
Changelog structure, with an `Unreleased` section.

Release rules:

- `main` is always releasable and should be protected by required CI checks.
- Feature work lands through focused pull requests.
- A release PR updates the version and changelog, then produces an `rc` when
  external testing is useful.
- A tag on the approved release commit builds immutable distributions and
  publishes them. Never rebuild or overwrite an existing version.
- Patch releases require a regression test for the fixed behavior.

## Branching and rollout strategy

Use trunk-based development while the project is small. `main` is the single
integration branch and must remain installable and releasable. Do not create a
long-lived `develop` branch or environment branches.

| Branch | Purpose | Lifetime |
|---|---|---|
| `main` | Reviewed, working integration branch. | Permanent; protect it once CI is established. |
| `feat/<topic>` | One focused capability, such as `feat/stage1-store`. | Create from `main`; delete after merge. |
| `fix/<topic>` | A focused bug fix, with a regression test. | Create from `main`; delete after merge. |
| `docs/<topic>` | Documentation-only work. | Create from `main`; delete after merge. |
| `chore/<topic>` | Tooling, dependency, or repository maintenance. | Create from `main`; delete after merge. |
| `release/<version>` | Optional coordinated release preparation. | Short-lived; merge or tag, then delete. |

### Feature workflow

```text
main ? create focused branch ? commit small, tested changes ? push ? pull request
? required CI passes ? review ? squash merge to main ? delete feature branch
```

Start new work from an up-to-date `main`:

```powershell
git switch main
git pull origin main
git switch -c feat/<topic>
git push -u origin feat/<topic>
```

Use conventional-style commit subjects (`feat:`, `fix:`, `docs:`, `chore:`) so
the history and future release notes stay readable. Keep a pull request limited
to one outcome; if a change needs unrelated work, split it into separate
branches and PRs.

### Main-branch protection

Configure GitHub branch protection for `main` when the repository is ready:

- Require pull requests before merging.
- Require the Python 3.10, 3.11, 3.12, and package-build CI checks to pass.
- Block force pushes and branch deletion.
- Require at least one approval when collaborators join; until then, use a
  deliberate self-review before merging.

### Release rollout

```text
merged PRs on main
  ? optional release-candidate tag (v0.1.0rc1)
  ? TestPyPI validation and manual live-provider smoke test
  ? final version/tag (v0.1.0)
  ? immutable GitHub release and PyPI publication
```

Until the first package release, deploying means merging a CI-green pull request
to `main`; no production service is being deployed. Roll back a merged change
with a new `fix/` branch and a reverting commit, rather than force-pushing
`main`.
## CI/CD pipeline

### Pull-request CI (required)

Run on supported Python versions (initially 3.10, 3.11, and 3.12):

1. Install locked development dependencies.
2. Run Ruff format check and lint.
3. Run static type checking.
4. Run unit and integration tests with no provider credentials and no network.
5. Run coverage and enforce a gradually raised threshold (start at 75%; target
   85% for core modules).
6. Build source distribution and wheel; verify package metadata and install the
   wheel in a fresh virtual environment.
7. Run the example's fake-provider smoke flow and verify report output.

### Main-branch CI (required)

Run the same checks plus dependency/security auditing. Upload test results and
coverage as build artifacts; do not publish packages from ordinary `main`
builds.

### Release CD (tag/manual approval)

1. Verify the tag matches the package version and changelog.
2. Re-run the complete quality gate from a clean runner.
3. Build once and attach the wheel and sdist to the GitHub release.
4. Publish first to TestPyPI for release-candidate validation if needed, then
   publish the exact built artifacts to PyPI through trusted publishing.
5. Create the GitHub release from the matching changelog section.

Use least-privilege GitHub Actions permissions, dependency pinning, and PyPI
trusted publishing (OIDC) instead of long-lived upload tokens. Provider API keys
must never be needed in ordinary CI. Any optional live-provider smoke test is a
manually approved workflow using repository secrets and a strict spend cap.

## Quality gates

| Gate | Applies to | Requirement |
|---|---|---|
| Functional | Every PR | Tests pass without network access. |
| Compatibility | Every PR | Supported Python matrix is green. |
| Packaging | Every PR and release | Wheel installs and CLI starts in a clean environment. |
| Security | `main` and releases | Dependency audit clean or explicitly documented exception. |
| Documentation | Feature/release PRs | User-facing CLI/API changes update README and changelog. |
| Release | Tags | Version, tag, report footer, and changelog agree. |

## First implementation sequence

1. Create the Python project skeleton and GitHub Actions CI.
2. Add the SQLite store plus `init` and `runs` commands.
3. Add a fake LLM adapter and tests before connecting the real LiteLLM adapter.
4. Implement recording, then replay, then deterministic checks, then the report.
5. Use the invoice example as the end-to-end acceptance test throughout.

## Deferred backlog

- LLM-as-a-judge and human review workflow.
- Redaction presets and encrypted-at-rest options.
- GitHub Action that comments on prompt-related pull requests.
- Streaming, tool calls, multi-turn traces, and agent replay.
- TypeScript SDK and framework-specific adapters.
