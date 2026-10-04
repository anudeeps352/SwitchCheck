# Switchcheck product brief

> Will this model, prompt, or parameter change preserve the behavior my
> application explicitly depends on?

Switchcheck answers that question for ten supported categories of repeatable,
single-interaction LLM tasks. It is not a universal model grader and cannot
establish that one model can replace another for arbitrary applications.

The normative boundary is
[docs/supported-evaluation-scope.md](docs/supported-evaluation-scope.md). The
technical design is in [architecture.md](architecture.md), and delivery order is
in [development-plan.md](development-plan.md).

## Problem

Teams change models, prompts, and parameters to reduce cost, improve latency,
handle deprecations, or fix behavior. Comparing candidate output with incumbent
output is not enough: the incumbent can be wrong, and many valid responses are
worded differently.

Switchcheck turns known application expectations into repeatable cases, runs a
candidate configuration, evaluates only with permitted evidence, and reports
what passed, failed, needs review, or errored.

## Product promise

Switchcheck determines whether a change preserves expected behavior for
supported tasks whose outcomes or observable criteria were defined before the
candidate response was generated.

It supports:

1. classification;
2. structured extraction;
3. structured transformation;
4. one proposed tool/function call;
5. constrained discrete decisions;
6. factual QA with expected facts;
7. support/policy responses with supplied rules;
8. summaries with supplied source and criteria;
9. RAG answers with supplied retrieved context; and
10. single-turn free text with a concrete observable rubric.

If a proposed evaluation is not independently evaluable, has no predefined
notion of acceptable behavior, lacks required reference evidence, or falls
outside these task types, Switchcheck rejects it as unsupported. It does not
send it to a generic judge.

## User workflow

```text
record/import candidate inputs
    -> automatically redact, deduplicate, sample, and enrich
    -> create DRAFT cases with provenance
    -> review uncertainty or apply an authoritative approval policy
    -> freeze an APPROVED dataset version
    -> validate eligibility without provider calls
    -> run candidate model/prompt/parameters
    -> evaluate against expected evidence
    -> inspect PASS / FAIL / REVIEW / ERROR and task-specific metrics
```

Recorded application traffic is useful input for building a dataset, but the
recorded model output is never automatically ground truth.

Expected answers can be automated safely when they come from a configured
system of record, deterministic business rule/test oracle, or trusted versioned
dataset. An LLM may suggest labels and criteria to reduce reviewer effort, but
those suggestions remain drafts until independently confirmed. Review automation
focuses human attention on disagreements, low-confidence cases, novel clusters,
and a sample of automatically approved cases rather than requiring every value
to be typed manually.

## Evaluation principles

- Prefer deterministic checks whenever correctness can be represented directly.
- Never require an LLM judge for classification, extraction, structured
  transformation, one-call tool selection, or labeled decisions.
- Use a criteria judge only for eligible free-text tasks with explicit criteria
  and required reference/context.
- Blind the judge to model/provider identity, cost, latency, prestige, and which
  response came from the candidate.
- Treat supplied context—not judge world knowledge—as truth for policy,
  summarization, and RAG cases.
- Calibrate each complete judge configuration against human-reviewed labels
  before presenting it as trusted.
- Keep `REVIEW` and `ERROR` visible; neither counts as `PASS`.

## Current status

Implemented today:

- local recording of non-streaming LiteLLM chat calls;
- replay against a candidate model;
- legacy deterministic exact, contains, regex, JSON Schema, and JSON-field
  checks;
- project-local SQLite persistence and static HTML replay reports;
- labeled JSONL dataset import;
- the ten-value `TaskType` enum; and
- versioned reference/context/structured-criteria contracts, import-time
  rejection of unsupported cases, and provider-free dataset eligibility checks;
- a typed deterministic evaluator core and explicit four-state verdict model.
- initial sequential dataset execution with persisted candidate results.
- task-aware experiment metrics, self-contained reports, and an offline
  labeled-evaluation example.

Not yet implemented:

- wiring evaluator configurations into dataset experiments and reports;
- parallel/resumable execution and experiment-to-experiment comparison;
- four-state experiment results;
- calibrated criteria judging; and
- human-review and calibration workflows.
- assisted dataset drafting, authoritative enrichment, provenance, approval,
  immutable versioning, and automatic refresh.

This distinction must remain visible in user-facing documentation. Planned
capabilities must not be described as shipped.

## Explicit non-goals

The initial product does not support creative generation, pure style or
preference comparisons, open-ended brainstorming, autonomous multi-step agents,
coding-agent repository changes, generic reasoning/intelligence scores,
personalized long-running assistant quality, end-to-end retrieval quality, or
safety-critical certification.

A future feature can enter the supported set only after Switchcheck introduces
a named task type, defines its required evidence and evaluator contract, adds
rejection behavior for invalid cases, and validates it with representative
human-reviewed data.

## Product success criteria

Switchcheck succeeds when a developer can make a narrower, defensible statement:

> On this versioned dataset of supported application tasks, this candidate
> configuration preserved the predefined required behavior, with these failures,
> reviews, errors, metrics, and reproducibility details.

It should never encourage the broader claim:

> This candidate can replace the incumbent for any LLM use case.
