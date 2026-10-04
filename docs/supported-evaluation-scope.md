# Supported evaluation scope

This document is the authoritative public product boundary for the initial
Switchcheck release. If another document, example, CLI option, or prototype
implementation conflicts with it, this document wins.

## Product promise

Switchcheck determines whether a model, prompt, or parameter change preserves
expected classification behavior on reviewed, repeatable cases.

Switchcheck does **not** determine whether an arbitrary LLM output is good and
does not certify that one LLM can replace another for every application.

## Initial supported task

The MVP supports one task type:

```text
classification
```

The model receives one input and must return one known categorical value or a
fixed JSON object containing categorical fields.

Examples include support-ticket categories, intent detection, sentiment,
document routing, escalation decisions, and moderation labels.

### Scalar example

```yaml
input: The product arrived broken.
expected: negative
```

### Structured-label example

```yaml
input: I was charged twice for my subscription.
expected:
  category: billing
  subcategory: duplicate_charge
```

The structured form is still classification: every expected field represents a
label selected from an application-defined set. It is not arbitrary information
extraction.

## Eligibility rule

A case is eligible only when:

1. it is one independently evaluable model interaction;
2. its expected label or label fields are known before the candidate runs;
3. correctness can be decided through exact deterministic comparison; and
4. it is a classification case.

If any answer is no, the MVP returns `Unsupported evaluation task`. It must not
silently use a generic LLM judge.

## Evaluation rules

Classification is evaluated deterministically:

- the candidate response must be parseable in the configured output form;
- scalar labels use exact equality after documented basic normalization;
- structured labels require every expected field;
- each expected field must equal its expected value;
- unexpected output, missing fields, malformed output, and provider failures
  remain visible; and
- an LLM judge is never required.

The report may include:

- case accuracy;
- per-field accuracy;
- accuracy by model;
- per-label precision, recall, and F1;
- confusion data;
- latency, token usage, and provider-reported cost; and
- explicit error counts.

## Configuration boundary

The primary workflow uses one `switchcheck.yaml` containing the prompt, models,
cases, and expected labels. Switchcheck selects the classification evaluators
automatically. A normal user does not configure evaluator class names or import
the cases into a database before running them.

The primary command is:

```powershell
switchcheck test
```

It produces one report comparing all configured models. The command and config
contract are the next implementation milestone and must not be described as
shipped until their acceptance tests pass.

## Result states

Every attempted case/model pair ends in one state:

- `PASS`: all expected labels match.
- `FAIL`: at least one expected label clearly differs or is missing.
- `ERROR`: the provider, parser, configuration, or evaluator failed technically.

`ERROR` remains visible and never counts as `PASS`. `REVIEW` is reserved for a
future task contract that genuinely permits uncertain semantic judgment; it is
not needed for deterministic MVP classification.

## Ground-truth provenance

Initially, expected labels are supplied directly by the user or imported from a
trusted business source. The incumbent model response is not ground truth.

Future assisted case creation may collect production inputs, redact them,
deduplicate them, and suggest labels. Model-suggested labels must remain drafts
until confirmed by a human or an authoritative, versioned business rule.

## Future candidates, not current support

The following task families were explored in the prototype but are not in the
initial public contract:

- structured extraction;
- structured transformation;
- tool/function selection;
- constrained decisions distinct from fixed-label classification;
- factual QA;
- customer-support or policy prose;
- summarization;
- RAG answer evaluation; and
- rubric-based free text.

Structured extraction is the likely next addition. No future type becomes
supported merely because an enum, evaluator, test, or legacy CLI path exists in
the repository. It requires a deliberately released config contract, automatic
evaluator selection, tests, reporting, documentation, and demonstrated user
demand.

## Explicitly unsupported

- creative generation and open-ended brainstorming;
- generic style, personality, or preference comparisons;
- arbitrary free-text quality judging;
- autonomous multi-step agents and tool trajectories;
- coding-agent or whole-repository modification evaluation;
- generic reasoning or intelligence scoring;
- personalized, long-running assistant quality;
- end-to-end retrieval-system quality; and
- safety certification for medical, legal, financial, security, or other
  high-stakes systems.
