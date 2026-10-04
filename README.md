# Switchcheck

Switchcheck is becoming a simple local tool for comparing models or prompts on
reviewed classification cases:

```text
one config -> one command -> one comparison report
```

It is not a universal model grader and does not claim that one model can replace
another for every LLM application.

## Target MVP experience

Create `switchcheck.yaml`:

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

  - id: cancellation
    input: I want to cancel my subscription.
    expected:
      category: account
      subcategory: cancel_subscription
```

Run:

```powershell
switchcheck test
```

Switchcheck will validate the complete config, run every case against every
model, compare the returned labels deterministically, and write one HTML report.
The report will show model accuracy, failures, errors, latency, usage, cost, and
case-level differences.

`switchcheck test` is the next implementation milestone and is not available on
the current branch yet. This README documents the product direction so new work
converges on the intended workflow instead of expanding the prototype APIs.

## Why classification first?

Classification is common, useful, and objectively testable. Typical cases are:

- support-ticket category and priority;
- intent detection;
- sentiment;
- document routing;
- escalation decisions; and
- moderation labels.

Expected labels are known before evaluation, so no LLM judge is necessary. That
lets the first release remain understandable and trustworthy.

Structured extraction is the likely next task after the classification workflow
has been validated with users. Other task types are deferred rather than claimed
as initial support. See the
[supported evaluation scope](docs/supported-evaluation-scope.md).

## Ground truth

The user or a trusted business source supplies expected labels. Switchcheck does
not treat the current model's output as truth.

Assisted case creation from recorded inputs may be introduced later, but
model-suggested labels will require confirmation before they can affect pass or
fail results.

## Current prototype

The repository currently contains lower-level building blocks developed before
the workflow was simplified:

- project-local SQLite persistence;
- LiteLLM calls and recorded-call replay;
- JSONL dataset import and eligibility checks;
- deterministic evaluator classes;
- classification metrics; and
- self-contained HTML reports.

Existing commands such as `dataset import`, `dataset check`, `evaluate`,
`replay`, and `report` remain prototype or advanced interfaces. They are not the
target onboarding experience, and new development should not require users to
combine them manually.

For the exact delivery sequence, see [development-plan.md](development-plan.md).
For the small target component design, see [architecture.md](architecture.md).

For prior art and workflow inspiration, see
[Promptfoo](https://github.com/promptfoo/promptfoo). Switchcheck is not trying to
match its complete feature set; the initial goal is a smaller classification-only
learning project.

## Development setup

Switchcheck supports Python 3.10 through 3.12. Create and activate a virtual
environment, then install the package and development tools:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
pre-commit install
```

Run local quality checks:

```powershell
ruff format --check .
ruff check .
pyright
pytest
python -m build
```

Normal tests and examples must run without provider credentials or network
access. Live-provider checks should use a small case set and explicit API keys
from environment variables.

## Privacy

Configs, prompts, expected labels, candidate outputs, local databases, and HTML
reports may contain sensitive application data. They remain local by default,
but users must review them before sharing. Never place API keys in configuration
or commit them to source control.

## Repository layout

```text
src/switchcheck/    Package source
tests/              Offline tests
examples/           Prototype and future public examples
docs/               Product boundary and operational guidance
```

## License

MIT. See [LICENSE](LICENSE).
