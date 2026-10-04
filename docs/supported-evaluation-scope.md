# Supported evaluation scope

This document is the authoritative product boundary for Switchcheck. If another
document, example, CLI option, or implementation detail conflicts with it, this
document wins.

## Product promise

Switchcheck determines whether changing a model, prompt, or parameters preserves
expected behavior for supported, repeatable LLM tasks with outcomes or evaluation
criteria defined before the candidate output is seen.

Switchcheck does **not** determine whether any arbitrary LLM output is good, and
it does not certify that one LLM can replace another for every use case.

## Eligibility gate

An evaluation is supported only when every answer below is yes:

1. Is this one independently evaluable model interaction?
2. Is acceptable behavior known before the candidate output is seen?
3. Can correctness be represented by expected values, structured fields,
   deterministic constraints, supplied reference/context, or explicit observable
   criteria?
4. Is it one of the ten supported task types below?

If any answer is no, Switchcheck must return `Unsupported evaluation task`. It
must not silently invoke a generic LLM judge.

## Ground-truth provenance and automation

The requirement that acceptable behavior is known in advance does not require
every case to be typed and labeled manually. Switchcheck may automate input
selection, redaction, deduplication, enrichment, draft labeling, review
prioritization, approval, versioning, and refresh.

Every expected value, reference fact, context block, and criterion must retain
its provenance. Initially supported provenance classes are:

- `human_reviewed`: entered or confirmed by an identified reviewer;
- `authoritative_system`: copied from a configured system of record;
- `deterministic_rule`: calculated by a versioned rule or test oracle;
- `trusted_dataset`: imported from a named, versioned source; and
- `llm_suggested`: proposed by a model but not yet trusted.

An incumbent model output is also untrusted unless independently confirmed. An
LLM suggestion or incumbent output may create a `DRAFT` case, but it must not
become evaluation ground truth merely because it exists or has high model
confidence.

Dataset lifecycle states are separate from evaluation result states:

- `DRAFT`: automatically collected or suggested; not runnable as ground truth.
- `IN_REVIEW`: awaiting human confirmation or authoritative resolution.
- `APPROVED`: provenance and approval policy permit evaluation.
- `RETIRED`: retained for audit but excluded from new experiments.

Cases backed by an authoritative system, deterministic rule, or trusted dataset
may be approved automatically when a versioned approval policy explicitly
allows it. Human review is required for LLM-suggested expectations unless a
future calibrated labeling policy is separately validated and explicitly
enabled. Dataset reports must expose provenance and approval coverage.

## Supported task types

| `task_type` | Contract | Evaluation |
|---|---|---|
| `classification` | Choose one value, or a fixed set of fields, from known labels. | Exact/field equality and classification metrics. |
| `extraction` | Extract known fields from supplied unstructured or semi-structured input. | Schema, fields, normalization, numeric checks, required/null checks, and configured array/set equality. |
| `structured_transformation` | Transform input into a predefined structured representation. | Schema, fields, normalized values, numeric tolerance, enums, required fields, and extra-field policy. |
| `tool_selection` | Propose exactly one tool/function call for the request. | Tool name, argument names/values, required arguments, argument schema, and configured normalization/tolerance. Tool execution is not evaluated. |
| `decision` | Make a labeled discrete decision from known rules or supplied context. | Exact/field equality and classification metrics; explanations may be evaluated separately. |
| `factual_qa` | Produce a short answer while preserving facts supplied in the case. | Required/prohibited facts and deterministic assertions; an optional calibrated criteria judge may assess wording. |
| `support_response` | Answer one support/policy request against supplied policy and explicit criteria. | Deterministic facts first, then an optional calibrated criteria judge. |
| `summarization` | Summarize supplied source material against explicit criteria. | Required facts plus a calibrated criteria judge for faithfulness, omissions, unsupported claims, and relevance. |
| `rag_answer` | Answer using retrieved context supplied with the case. | Expected facts plus a calibrated criteria judge that treats the supplied context—not model world knowledge—as truth. Retrieval quality is separate. |
| `rubric_free_text` | Produce one free-text answer assessed against concrete, observable criteria. | Calibrated criteria judge with per-criterion results. |

No other task type is officially supported in the initial architecture.

## Evaluator families and permitted mapping

The initial public evaluator families are `ExactEvaluator`, `FieldEvaluator`,
`SchemaEvaluator`, `NumericEvaluator`, `PatternEvaluator`,
`ClassificationMetricsEvaluator`, `ToolCallEvaluator`, and
`CriteriaJudgeEvaluator`. `RequiredFactsEvaluator` is an optional convenience
composition over deterministic field/value/pattern checks. There is no
`UniversalEvaluator`.

| Task type | Permitted evaluator IDs |
|---|---|
| `classification` | `exact`, `fields`, `classification_metrics` |
| `extraction` | `schema`, `fields`, `numeric`, `exact` |
| `structured_transformation` | `schema`, `fields`, `numeric`, `exact` |
| `tool_selection` | `tool_call`, `schema`, `fields` |
| `decision` | `exact`, `fields`, `classification_metrics` |
| `factual_qa` | `required_facts`, `exact`, `fields`, optional `criteria_judge` |
| `support_response` | `required_facts`, `criteria_judge` |
| `summarization` | `required_facts`, `criteria_judge` |
| `rag_answer` | `required_facts`, `criteria_judge` |
| `rubric_free_text` | `criteria_judge` |

`PatternEvaluator` is a deterministic primitive used by configured fact and
constraint checks; it is not a loophole for accepting an unsupported task.
Unsupported task/evaluator combinations must be rejected before model calls.

## Deterministic evaluation rules

Use deterministic evaluators wherever the expected outcome can be expressed
directly. They cover exact label/value equality, JSON validity and schema,
field equality, normalized strings, numeric equality/tolerance, enums, required
and null fields, explicitly configured array/set equality, required/prohibited
facts, and one proposed tool call.

Classification and decision reports may include accuracy, per-label precision,
per-label recall, F1, confusion matrices, and metadata-grouped failure rates.
Extraction and transformation reports may include field-level and case-level
accuracy. A human-labeled expected decision always takes precedence over an LLM
judge's opinion.

## Criteria judge contract

The LLM judge is allowed only for `factual_qa` (optional), `support_response`,
`summarization`, `rag_answer`, and `rubric_free_text`. A secondary explanation
attached to a deterministic task may be represented and judged as a separate
free-text output contract; this does not allow the judge to override the
deterministic result.

The judge receives only the original task input, candidate response, explicit
observable criteria, optional expected/reference facts, and optional supplied
source, policy, or retrieved context. It must not receive model names, price,
latency, provider prestige, or whether a candidate is cheaper. It must not use
external world knowledge as the source of truth.

```json
{
  "verdict": "pass | fail | review",
  "score": 0.0,
  "criteria": [
    {
      "criterion_id": "observable_requirement",
      "verdict": "pass | fail | review",
      "reason": "Evidence from the candidate and supplied reference"
    }
  ],
  "reason": "Overall explanation"
}
```

Criteria such as “good answer,” “high quality,” or “sounds intelligent” are
invalid. Criteria must state observable requirements such as “must explain X,”
“must not claim Y,” or “must mention Z.” `review` is required when evidence is
insufficient for a reliable automatic decision.

## Judge calibration

A judge configuration is the tuple of judge model, judge prompt version, rubric
version, parameters, and output-schema version. It must be stored with every
result. Switchcheck must not present a configuration as trusted until it has
been compared with human-reviewed labels.

At minimum calibration reports overall agreement, calibration-case count,
disagreement count, and agreement by criterion where criterion labels exist.

## Final case states

Every evaluated case ends in exactly one state:

- `PASS`: all required checks are satisfied.
- `FAIL`: at least one required check clearly fails.
- `REVIEW`: automatic evidence is insufficient.
- `ERROR`: the candidate or evaluator failed technically.

`REVIEW` never counts as `PASS`. `ERROR` remains visible in aggregate metrics
and is never silently dropped.

## Explicitly unsupported initially

- creative generation and open-ended brainstorming;
- pure style, personality, or preference comparison unless converted into
  explicit observable criteria;
- autonomous multi-step agents, tool trajectories, and workflow completion;
- coding-agent or whole-repository modification evaluation;
- generic reasoning, intelligence, or logical-quality scoring without a
  verifiable answer or explicit rubric;
- personalized, long-running assistant quality;
- end-to-end retrieval architecture quality unless expected document IDs are
  separately labeled; and
- safety-critical certification for medical, legal, financial, security, or
  other high-stakes systems.

Generated code may later be evaluated through explicit compilation/tests, and
multi-step agents may later receive their own task and trace contracts. Neither
is supported merely by routing output to an LLM judge.
