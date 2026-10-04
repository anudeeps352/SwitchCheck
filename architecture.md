# Switchcheck architecture

## Purpose

The initial product compares multiple model or prompt configurations on a fixed
set of reviewed classification cases. The architecture optimizes for a small,
readable implementation and one public workflow:

```text
switchcheck.yaml -> switchcheck test -> HTML report
```

The authoritative product boundary is
[docs/supported-evaluation-scope.md](docs/supported-evaluation-scope.md).

## System flow

```text
                  switchcheck.yaml
                         |
                         v
               load and validate config
                         |
                         v
             render prompt for every case
                         |
                         v
             run each configured model
                         |
                         v
             parse scalar/JSON label output
                         |
                         v
              compare expected labels
                         |
                         v
            metrics + one comparison report
```

Validation completes before provider calls. Internal persistence is initialized
automatically and is not part of the normal user workflow.

## Public configuration contract

Version 1 intentionally contains few concepts:

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
    input: I was charged twice for my subscription.
    expected:
      category: billing
      subcategory: duplicate_charge
```

Required top-level fields are `version`, `task`, `prompt`, `models`, and `cases`.
For version 1, `task` must equal `classification`.

Each case contains:

- a stable `id`;
- one `input` value inserted into `{{input}}`; and
- `expected`, either a scalar label or a non-empty mapping of label fields.

Evaluator names, dataset IDs, experiment IDs, database paths, and report IDs are
not required configuration.

## Small component model

The target implementation has five understandable responsibilities:

| Component | Responsibility |
|---|---|
| `config` | Load `switchcheck.yaml`, validate its version and classification cases, and return typed values. |
| `provider` | Make one LiteLLM call and return normalized text/JSON, usage, latency, cost, or an error. |
| `runner` | Expand the model/case matrix and coordinate calls without containing evaluation rules. |
| `classification` | Parse candidate labels, compare expected fields, and calculate classification metrics. |
| `report` | Render one self-contained comparison report for the entire run. |

SQLite may retain reproducibility data for later inspection and UI use, but
storage details stay behind a narrow interface. The CLI should only compose the
components above.

## Classification evaluation

Evaluation is deterministic. A scalar expected label compares with a scalar
candidate label. A structured expected value compares every named field in the
candidate JSON object.

The initial normalizer may trim surrounding whitespace and JSON code fences.
It must not silently rewrite labels, guess aliases, or ask another model whether
two labels mean the same thing.

Each model/case attempt ends as:

```text
PASS   every expected label matches
FAIL   a label is missing or differs
ERROR  provider, parsing, configuration, or evaluation failed technically
```

Reports retain every attempt. Errors are never discarded or counted as passes.

## Persistence model

Persist only what is required to reproduce and inspect a comparison:

- config version and a snapshot of the resolved config;
- model identifier and parameters actually used;
- case ID, rendered prompt, and expected labels;
- raw and parsed candidate output;
- state and field-level reasons;
- latency, token usage, and provider-reported cost; and
- timestamps and package version.

The existing SQLite implementation may be adapted instead of replaced. New
tables or abstractions should be added only when the unified workflow needs
them.

## CLI boundary

The primary command is:

```powershell
switchcheck test [CONFIG]
```

With no argument, it discovers `switchcheck.yaml` in the current directory. It
validates, runs, persists, calculates metrics, and writes the report in one
operation.

Existing `dataset`, `evaluate`, `record/replay`, and standalone report commands
are prototype or advanced interfaces. They may remain temporarily for
compatibility, but new product behavior should not require them.

## Report boundary

One run produces one report containing:

- a model comparison summary;
- per-model classification metrics;
- latency, token, cost, failure, and error totals;
- case-level expected and candidate labels; and
- field-level failure reasons.

The future local UI must read the same persisted comparison data or call the
same application service. It must not implement a second runner or evaluator.

## Simplicity rules

- Do not add a generic evaluator interface for the MVP path.
- Do not expose internal class names in configuration.
- Do not create abstractions for hypothetical task types.
- Keep provider-specific behavior behind LiteLLM.
- Keep network-free tests by injecting a fake completion function.
- Prefer one obvious data flow over separate replay and dataset workflows.
- Delete superseded orchestration after compatibility needs end.

## Future extension rule

Structured extraction is the first candidate after classification. It should be
added as a separate, explicit contract only after the classification workflow
is validated with users. Other tasks follow the same rule.

A future task must define its config, evidence, parsing, deterministic or
calibrated evaluation rules, states, metrics, tests, and report sections before
being advertised.

## Privacy and safety

- Configs, prompts, expected labels, outputs, databases, and reports remain
  local by default.
- Never persist API keys or authorization headers.
- Provider calls occur only after a validated explicit `test` command.
- Reports can contain sensitive application data and must be handled
  accordingly.
- Switchcheck results are regression evidence, not safety certification.
