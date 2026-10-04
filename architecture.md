# Switchcheck architecture

## Purpose and boundary

Switchcheck is a local-first evaluation system for deciding whether a model,
prompt, or parameter change preserves acceptable behavior on supported,
repeatable LLM tasks. Acceptability must be defined before the candidate output
is seen.

The authoritative product contract is
[docs/supported-evaluation-scope.md](docs/supported-evaluation-scope.md). The
architecture must reject unsupported tasks and evaluator combinations; it must
never compensate for missing ground truth by invoking a generic judge.

## System context

```text
application traffic --> recorder --> local run store
                                      |
labeled dataset --> eligibility --> experiment runner --> candidate model
                     gate             |                    |
                     |                +-- candidate output-+
                     v
               evaluator registry --> case state + evidence --> report/review
```

The CLI is the composition layer. LiteLLM isolates provider-specific calls.
SQLite owns local experiment state. Reports are self-contained artifacts and
may contain sensitive application data.

## Eligibility and task model

Every dataset case declares one `TaskType`:

```python
class TaskType(str, Enum):
    CLASSIFICATION = "classification"
    EXTRACTION = "extraction"
    STRUCTURED_TRANSFORMATION = "structured_transformation"
    TOOL_SELECTION = "tool_selection"
    DECISION = "decision"
    FACTUAL_QA = "factual_qa"
    SUPPORT_RESPONSE = "support_response"
    SUMMARIZATION = "summarization"
    RAG_ANSWER = "rag_answer"
    RUBRIC_FREE_TEXT = "rubric_free_text"
```

Before making provider calls, the eligibility gate verifies that the case is a
single independently evaluable interaction, expected behavior was specified in
advance, the evidence is representable, and the task type is supported. It then
validates every configured evaluator against the task/evaluator allow-list.

Cases outside this contract receive `Unsupported evaluation task`; they do not
enter experiment aggregates.

## Core components

| Component | Responsibility |
|---|---|
| `client` | Record non-streaming application calls, usage, latency, and errors. Recording alone does not create ground truth. |
| `datasets` | Import versioned, human-reviewed cases; validate task type and case contract before persistence. |
| `eligibility` | Apply the hard product boundary and reject unsupported evaluations before model calls. |
| `experiments` | Run eligible dataset cases against one candidate configuration and persist each attempt independently. |
| `evaluators` | Execute only evaluators permitted for the case task type and return structured evidence. |
| `calibration` | Compare one complete judge configuration with human labels and report agreement/disagreement. |
| `store` | Own SQLite schema, migrations, data access, and reproducibility records. |
| `report` | Show case states, aggregate metrics, evidence, calibration status, errors, and candidate configuration. |
| `replay` | Preserve the foundation workflow for recorded calls; recorded output is a comparison baseline, not automatic truth. |
| `cli` | Validate configuration and orchestrate import, evaluate, calibrate, inspect, and report workflows. |

## Dataset case contract

The target logical schema is:

```json
{
  "id": "case-id",
  "task_type": "extraction",
  "messages": [{"role": "user", "content": "..."}],
  "expected": {"field": "value"},
  "reference": {"facts": {}},
  "context": "optional source, policy, or retrieved passages",
  "criteria": [
    {"id": "criterion-id", "requirement": "Concrete observable requirement"}
  ],
  "evaluators": ["schema", "fields"],
  "metadata": {},
  "source_run_id": null
}
```

Fields may be absent only when the task contract does not need them. Structured
and discrete tasks require `expected`. Factual QA requires expected/reference
facts. Support responses require policy/context and criteria. Summarization
requires source and criteria. RAG answers require retrieved context and expected
facts or criteria. Rubric free text requires concrete criteria.

The current importer persists a contract version, `task_type`, messages,
optional expected/reference/context evidence, structured criteria, declared
evaluators, metadata, and provenance. It validates the task-specific evidence
contract before writing anything.

A recorded run may seed a case, but a reviewer or trusted dataset must establish
its expected values, reference material, and criteria. An incumbent output is
never promoted to truth automatically.

## Evaluator registry

The registry contains these public families only:

- `ExactEvaluator`
- `FieldEvaluator`
- `SchemaEvaluator`
- `NumericEvaluator`
- `PatternEvaluator`
- `ClassificationMetricsEvaluator`
- `ToolCallEvaluator`
- `CriteriaJudgeEvaluator`
- optional `RequiredFactsEvaluator`

The allow-list lives in `switchcheck.task_types.PERMITTED_EVALUATORS` and mirrors
the authoritative scope document. Configuration loading and experiment startup
both validate it. There is no default evaluator and no `UniversalEvaluator`.

Deterministic evaluators run before a criteria judge. A judge cannot override a
failed expected value or labeled decision. Pattern checks are deterministic
building blocks for explicit constraints, not an escape hatch for arbitrary
tasks.

## Criteria judge isolation

Only factual QA, support responses, summarization, RAG answers, and rubric free
text can use `CriteriaJudgeEvaluator`. The judge request builder includes the
task input, candidate response, explicit criteria, and supplied reference or
context. It excludes model/provider identity, price, latency, and incumbent vs
candidate labels.

Judge output is schema-validated and contains an overall `pass | fail | review`
verdict plus per-criterion verdicts and reasons. Malformed output or provider
failure becomes `ERROR`; ambiguous evidence becomes `REVIEW`.

A judge configuration is identified by model, prompt version, rubric version,
parameters, and output-schema version. Reports label it uncalibrated until a
human-reviewed calibration set has produced agreement metrics.

## Result state and aggregation

Use one explicit enum for all evaluated cases:

```text
PASS    all required checks pass
FAIL    at least one required check clearly fails
REVIEW  evidence is insufficient for automatic acceptance
ERROR   candidate execution or evaluation failed technically
```

Aggregation uses the full denominator and separate counts for all four states.
`REVIEW` and `ERROR` never increase pass rate. Reports may show operational
error rate separately from behavioral failure rate.

Task-specific metrics include:

- classification/decision: accuracy, per-label precision/recall/F1, confusion
  matrix, and metadata-grouped failure rates;
- extraction/transformation: field-level and case-level accuracy;
- tool selection: tool-name and argument-level accuracy;
- judge tasks: per-criterion rates plus calibration agreement.

## Persistence and reproducibility

The existing local schema has runs, replays, replay results, datasets, and
evaluation cases. The evaluation schema evolves to add dataset/task contract
versions, reference/context and structured criteria, experiment configuration,
candidate attempts, evaluator versions, four-state outcomes, judge calibration
IDs, and aggregate metrics derived from retained case results.

Store normalized requests actually sent, warnings for dropped parameters,
package/schema versions, timestamps in UTC, and immutable configuration snapshots.
Interrupted experiments retain completed attempts and can be reported as partial.

## One-turn tool boundary

The supported flow is:

```text
input -> model proposes one tool call -> evaluate proposed call
```

Switchcheck does not execute a tool and continue a model trajectory in the
initial architecture. Multi-step tool use and agent traces require a later,
separate task contract.

## Privacy and safety

- Data and reports remain local by default; no telemetry.
- Prompts, context, outputs, and reports are sensitive and must be reviewed
  before sharing.
- Never store API keys or authorization headers.
- Provider calls happen only for explicit application calls, experiments, or
  calibration runs.
- A Switchcheck result is test evidence, not safety certification for
  high-stakes systems.

## Implemented foundation versus target core

Implemented: recording, local storage, recorded-call replay, deterministic
legacy checkers, static reports, versioned dataset import, explicit task types,
structured criteria/reference/context, task/evaluator compatibility checks, a
read-only dataset eligibility command, four-state verdict types, and a typed
deterministic evaluator core for exact, field, schema, numeric, pattern, tool
call, required-fact, and classification-metric evaluation.

Not yet implemented: dataset execution and evaluator configuration, four-state
experiment persistence, criteria judging, judge calibration, and task-specific
aggregate reports. The
roadmap defines the delivery order and must not describe these as current
capabilities.
