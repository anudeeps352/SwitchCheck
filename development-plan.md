# Switchcheck development plan

## Objective

Deliver the smallest useful Switchcheck: one configuration file, one command,
and one report for comparing models or prompts on classification cases.

```text
switchcheck.yaml -> switchcheck test -> comparison report
```

The MVP supports classification only. Other task families remain backlog items
until the classification workflow is easy to install, understand, modify, and
use successfully.

## Product-development rules

- Optimize the primary workflow before adding evaluator breadth.
- Keep user-visible concepts to prompt, models, cases, expected labels, and
  report.
- Infer deterministic evaluators from `task: classification`.
- Do not require users to initialize storage, import a dataset, select evaluator
  classes, copy experiment IDs, or run a second report command.
- Prefer small functions and ordinary data structures over frameworks and deep
  abstraction layers.
- Preserve legacy commands only while they help migration or reuse tested code.
- Do not advertise prototype task types as supported.
- Add the UI only after the config and runner contract are stable.

## Reference project

[Promptfoo](https://github.com/promptfoo/promptfoo) is the primary external
reference for configuration-driven LLM evaluation, multi-model execution, CLI
usability, and result presentation. Use it to study established workflows and
terminology, not as a feature checklist Switchcheck must reproduce.

Switchcheck intentionally remains smaller: the MVP implements only deterministic
classification regression testing through one config, one command, and one
report.

## Current state

The repository contains useful prototype pieces: LiteLLM provider calls,
record/replay, SQLite persistence, JSONL dataset import, deterministic
evaluators, classification metrics, and HTML reports. It also exposes more task
types and workflow steps than the MVP needs.

The next work is simplification and composition, not another evaluator family.

## Delivery roadmap

| Milestone | Outcome | Exit criteria |
|---|---|---|
| v0.1 unified classification workflow | One config and one command compare multiple models and write one report. | `switchcheck test` discovers or accepts a config, validates before calls, runs the complete model/case matrix, exits non-zero on configured regression failure, and writes one self-contained report. |
| v0.1 usability hardening | A new user can succeed from the README without learning internals. | `switchcheck init` optionally creates an example config, errors name the exact config location, dry-run shows planned calls, credentials are checked clearly, and the offline example uses the same command. |
| v0.2 classification dataset assistance | Reduce manual case maintenance without inventing labels. | Import/export and production-input drafting feed the same config/case model; suggested labels are visibly unapproved; trusted labels retain provenance. |
| v0.3 local UI | Browse the same runs and reports through a local interface. | The UI calls the same application service as the CLI and introduces no separate evaluation semantics. |
| Later: structured extraction | Add the next deterministic task only after classification demand is validated. | A simple config contract, automatic schema/field checks, representative tests, and useful field metrics exist. |
| Later: other task contracts | Add one task at a time in response to evidence. | Each task has predefined evidence, safe automatic evaluator selection, tests, reports, and a clearly documented boundary. |

## Immediate implementation sequence

### 1. Freeze the MVP config contract

Use a single `switchcheck.yaml`:

```yaml
version: 1
task: classification
prompt: |
  Classify the request. Return only JSON.
  Request: {{input}}
models:
  - openai/gpt-4o-mini
  - anthropic/claude-haiku-4-5
cases:
  - id: duplicate-charge
    input: I was charged twice.
    expected:
      category: billing
```

Keep version 1 deliberately small. Optional model parameters and report output
path may be added only if they do not complicate the common example.

### 2. Add `switchcheck test`

The command must:

1. discover `switchcheck.yaml` or accept an explicit path;
2. parse and validate the whole config before provider calls;
3. initialize internal storage automatically;
4. render `{{input}}` for every case;
5. run every configured model against every case;
6. parse scalar or JSON label output;
7. evaluate expected labels deterministically;
8. calculate classification metrics;
9. write one comparison report; and
10. print the report path and a compact model summary.

### 3. Consolidate the runner

Reuse tested provider, persistence, metric, and report code where it remains
clear. Introduce no generic orchestration framework. The preferred core is:

```text
load_config -> validate -> build_cases -> run_matrix -> evaluate -> write_report
```

Functions should accept explicit typed values and return ordinary dataclasses.
Keep file parsing, provider calls, evaluation, persistence, and HTML rendering
separate so each can be tested without network access.

### 4. Produce one comparison report

The report leads with a table containing one row per model:

- pass rate and case count;
- failures and errors;
- field and label metrics;
- total latency, tokens, and provider-reported cost; and
- regression details by case.

Every failed case shows input, expected labels, candidate labels, and a direct
reason. No experiment ID should be needed to find the report from the normal
command output.

### 5. Make the example use the real UX

Replace the multi-command support-ticket walkthrough with a checked-in example
config and one offline-capable command. The README quickstart and automated
smoke test must exercise the same public path.

### 6. Reduce exposed complexity

After the unified workflow is stable:

- mark dataset import/check/evaluate and record/replay/report as advanced or
  legacy;
- stop adding functionality to those command paths;
- remove duplicate orchestration where `switchcheck test` supersedes it; and
- retain internal persistence only when it helps reproducibility or the future
  UI.

## Acceptance tests for v0.1

- a minimal classification config runs offline with fake completions;
- two models and two cases create four retained results;
- malformed config fails before any provider call;
- an unsupported `task` fails with an actionable message;
- scalar labels and structured label fields are evaluated correctly;
- malformed model output is visible as `ERROR` or a documented failure state;
- missing or incorrect labels fail;
- provider errors remain in totals;
- one HTML report compares every configured model;
- CLI exit status can gate CI; and
- README commands match the tested behavior.

## Code-quality gates

Every change must pass Ruff formatting/linting, Pyright, offline pytest, package
build, and the public workflow smoke test. Normal CI must not require provider
credentials or network access.

Prefer deleting obsolete complexity over maintaining parallel implementations.
Avoid speculative abstractions for future task types.

## Explicitly deferred

- extraction and all other task families;
- LLM judges and judge calibration;
- autonomous dataset enrichment pipelines;
- multi-step agents and traces;
- hosted accounts and collaboration;
- production observability;
- a web UI before the CLI/config contract stabilizes; and
- universal evaluation or model-replacement claims.
