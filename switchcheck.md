# Switchcheck product brief

> Compare model or prompt changes on the classification behavior your
> application depends on.

Switchcheck is being simplified around one initial use case: classification.
The MVP will use one readable configuration file, one command, and one local
comparison report.

```text
switchcheck.yaml -> switchcheck test -> HTML report
```

Switchcheck is not a universal LLM grader and does not establish that one model
can replace another for arbitrary applications.

The normative MVP boundary is
[docs/supported-evaluation-scope.md](docs/supported-evaluation-scope.md). The
technical design is in [architecture.md](architecture.md), and delivery order is
in [development-plan.md](development-plan.md).

## Problem

Teams change models, prompts, and parameters to reduce cost, improve latency,
handle deprecations, or fix behavior. Public benchmarks do not prove that a
candidate still assigns the labels required by a particular application.

Switchcheck runs reviewed application examples against each configured model,
compares the returned labels with expected labels, and shows regressions,
accuracy, latency, usage, and errors in one report.

## Initial user

The first user is a developer maintaining a single-turn classifier such as:

- support category or priority classification;
- intent detection;
- sentiment classification;
- document routing;
- moderation or escalation labels; or
- another fixed-label business decision.

## MVP workflow

The user creates `switchcheck.yaml`:

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

Then runs:

```powershell
switchcheck test
```

The command discovers `switchcheck.yaml`, validates it before provider calls,
runs every case against every model, applies classification checks, persists the
run internally, and writes one HTML comparison report. There is no required
`init`, dataset import, eligibility command, evaluator selection, or separate
report command in the primary workflow.

## Product promise

For the MVP, Switchcheck answers:

> On these reviewed classification cases, which configured model or prompt
> preserves the expected labels?

It does not answer:

> Is this model generally better, or can it replace another model everywhere?

## Ground truth

Expected labels must exist before a candidate response is evaluated. Initially,
they are written in the configuration by the user or copied from a trusted
source. A model output is not automatically treated as correct.

Assisted case creation from production inputs may be added later. Suggested
labels must remain drafts until confirmed by a person or authoritative rule.

## MVP evaluation

The classification runner will:

- require a scalar label or a JSON object of label fields in `expected`;
- parse the candidate response;
- compare every expected field exactly;
- retain provider and parse errors;
- calculate case accuracy and per-field accuracy;
- calculate per-label precision, recall, and F1 where meaningful; and
- show every case and model in a single report.

Evaluator classes are an implementation detail. Users should not have to select
`ExactEvaluator`, `FieldEvaluator`, or `ClassificationMetricsEvaluator` for the
normal classification workflow.

## Later task types

Structured extraction is the leading candidate after classification because it
can also be evaluated deterministically. Structured transformation, tool
selection, constrained decisions, factual QA, support responses,
summarization, RAG answers, and rubric-based free text are research/backlog
items. They are not part of the MVP promise.

A task type becomes public only after it has a simple config contract, automatic
safe evaluator selection, tests, useful reports, and evidence of user demand.

## Current prototype status

The repository already contains record/replay commands, dataset import,
experimental task types, deterministic evaluator classes, SQLite persistence,
and HTML reports. These pieces are useful implementation material, but they do
not define the intended user experience.

During simplification:

- legacy commands remain available until the new workflow replaces them;
- no new features should be added to record/replay;
- experimental task types must not be advertised as supported;
- new development should serve `switchcheck test`; and
- internal abstractions should be removed when they do not make the primary
  classification flow clearer.

## Product success criterion

A new user should be able to copy one example config, add an API key, and obtain
a useful two-model classification comparison without understanding Switchcheck's
database, evaluator registry, or dataset lifecycle.
