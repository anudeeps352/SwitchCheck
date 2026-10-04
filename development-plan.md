# Switchcheck development plan

## Objective

Deliver a trustworthy evaluation workflow for the ten task types in the
[supported evaluation scope](docs/supported-evaluation-scope.md). The roadmap is
contract-first: each milestone expands implementation inside that boundary. A
new task type requires its own expected evidence, evaluator mapping, tests, and
documentation before it can be advertised.

## Current state

The foundation can record and replay non-streaming calls, run several legacy
deterministic checks, persist results, produce static reports, and import labeled
JSONL datasets. Dataset imports now require a supported `task_type` and reject
declared task/evaluator combinations outside the allow-list. Versioned cases now
store structured criteria, reference/context evidence, and presence information;
task-specific eligibility can be checked without a provider call.

The product now has an initial sequential `evaluate` path with four-state
persistence for configured deterministic evaluators. Criteria judging,
parallel/resumable execution, classification aggregates, dedicated experiment
reports, and the full task-specific metric set are planned—not shipped.

## Delivery roadmap

| Milestone | Outcome | Exit criteria |
|---|---|---|
| v0.1 foundation | Preserve the local record/replay/check/report workflow. | Offline tests, schema migrations, privacy guidance, package build, and example flow pass. |
| v0.2 contracts and deterministic evaluation | Run labeled classification, extraction, structured transformation, tool selection, and decision datasets. | Eligibility gate and evidence validation work; evaluator registry rejects invalid combinations; deterministic evaluator families run; every case is `PASS`, `FAIL`, or `ERROR`; task-specific metrics and reproducible reports are available. |
| v0.3 assisted dataset building | Reduce manual dataset work without manufacturing ground truth. | Recorded/imported inputs can be sampled, redacted, deduplicated, enriched from authoritative sources/rules, and turned into traceable drafts; LLM suggestions remain unapproved; approval policies create immutable runnable versions. |
| v0.4 facts and four-state results | Add factual QA and deterministic fact checks, plus human review routing. | Required/prohibited facts are versioned; `REVIEW` is persisted and never counted as pass; all aggregates retain errors; metadata-grouped analysis works. |
| v0.5 calibrated criteria judge | Add support response, summarization, RAG answer, and rubric free text. | Concrete criteria/context validation works; judge inputs are blinded; output schema is enforced; configurations are versioned; human calibration reports agreement and disagreements; uncalibrated judges are visibly marked. |
| v0.6 review workflow | Make draft approval and uncertain evaluation cases efficient to inspect. | A local or web workflow supports dataset lifecycle states, provenance/conflicts, approval, all four evaluation states, per-criterion evidence, human verdicts, and calibration-set curation. |
| Later: agent evaluation | Introduce a separate multi-step contract. | Work begins only after trajectory semantics, expected tool/task outcomes, and dedicated evaluators are designed; it is not an extension of the generic criteria judge. |

## Immediate implementation sequence

### 1. Complete the case contract (implemented)

- Versioned `reference`, `context`, and structured `criteria` fields are stored.
- Task-specific requirements are validated before persistence: expected labels for
  discrete tasks, expected fields for structured tasks, policy/source/retrieved
  context where required, and observable rubric criteria for judge tasks.
- A dataset contract version and migration path preserve existing local
  cases whose `task_type` is null; require explicit relabeling rather than
  guessing their type.
- `switchcheck dataset check` performs eligibility checks without provider calls.

### 2. Build the deterministic evaluator registry (core implemented)

- `ExactEvaluator`, `FieldEvaluator`, `SchemaEvaluator`,
  `NumericEvaluator`, `ClassificationMetricsEvaluator`, and
  `ToolCallEvaluator` now have typed, tested implementations.
- `PatternEvaluator` is implemented as a constraint primitive and
  `RequiredFactsEvaluator` checks only explicitly supplied facts.
- Validate configurations at import and again at experiment start.
- Remove reliance on an incumbent output as expected truth in dataset
  experiments; keep recorded replay as a separate comparison workflow.

### 3. Build the assisted dataset pipeline

Before completing the experiment runner, add the assisted dataset-building
pipeline so production traffic does not require fully manual conversion:

- Add dataset lifecycle states `DRAFT`, `IN_REVIEW`, `APPROVED`, and `RETIRED`.
- Persist immutable dataset versions and per-field label/reference provenance.
- Add `dataset draft` to sample recorded runs by tag, time, metadata, and failure
  strata without copying incumbent outputs into expected fields.
- Add configurable redaction before draft persistence and record the policy
  version used.
- Add exact and semantic deduplication, clustering, coverage selection, and
  selection-reason metadata. These guide curation; they do not determine truth.
- Add label-source adapters for systems of record, deterministic rules/test
  oracles, and trusted versioned datasets.
- Allow an LLM to suggest missing labels, facts, or observable criteria while
  recording its complete configuration and marking all output `llm_suggested`.
- Route source disagreements, missing evidence, low confidence, novel clusters,
  and audit samples to review.
- Add versioned approval policies. Only human-confirmed or policy-approved
  authoritative evidence can produce an `APPROVED` runnable dataset version.
- Add refresh jobs that compare new traffic with approved coverage and produce a
  new draft version rather than mutating historical datasets.

Suggested CLI progression:

```text
switchcheck dataset draft --tag support --sample 200
switchcheck dataset enrich support-draft --source resolved-tickets.jsonl
switchcheck dataset suggest support-draft --missing-only
switchcheck dataset review support-draft
switchcheck dataset approve support-draft --name support-v1
switchcheck dataset refresh support-v1 --tag support
```

### 4. Run dataset experiments (initial sequential slice implemented)

- A named dataset and candidate configuration can be selected with
  `switchcheck evaluate`.
- The experiment and pending case attempts are persisted before provider execution.
- Use bounded concurrency and retry only transient provider failures.
- Parse candidate text, structured output, or a single proposed tool call based
  on the declared task contract.
- Terminal state, evaluator evidence, latency, usage, and candidate output are
  stored. Parallelism, retry/resume, normalized request capture, and evaluator
  versions remain.

### 5. Introduce four-state outcomes and metrics

- Replace boolean-only experiment outcomes with `PASS | FAIL | REVIEW | ERROR`.
- Define aggregation denominators explicitly; never drop review/error cases.
- Add accuracy, per-label precision/recall/F1, confusion matrices, field/case
  accuracy, tool/argument accuracy, and metadata-grouped failure rates.
- Keep legacy replay reports honest about their boolean checker semantics until
  they migrate to the experiment result model.

### 6. Add factual QA before judging prose

- Represent required facts, prohibited facts, numeric values, and structured
  assertions explicitly.
- Evaluate them deterministically and expose failures at fact level.
- Permit a criteria judge only as an optional second layer; it cannot override a
  deterministic fact failure.

### 7. Add and calibrate the criteria judge

- Validate criteria as concrete observable requirements.
- Build task-specific prompt templates that always include supplied source,
  policy, or retrieved context when the task requires it.
- Blind the judge to model/provider names, cost, latency, and candidate status.
- Enforce the `pass | fail | review` per-criterion output schema.
- Persist the complete judge configuration with every result.
- Compare against human labels and report overall agreement, case count,
  disagreements, and criterion agreement before calling a judge trusted.

### 8. Reporting and user experience

- Lead every report with task type, dataset/version, evaluator configuration,
  calibration status, and counts for all four states.
- Show task-specific metrics only where meaningful.
- Make unsupported-task errors actionable and link to the scope document.
- Use product copy consistently: “preserves expected behavior for supported
  tasks,” never “determines whether any LLM output is good.”

## Required acceptance datasets

Maintain small offline fixtures for all ten task types. Each fixture includes
passing, failing, malformed/error, and boundary cases. Judge-task fixtures also
include `REVIEW`, unsupported-claim examples, and human verdicts for calibration.

At least these cross-cutting tests are required:

- every unsupported task type is rejected before provider execution;
- no `DRAFT`, `IN_REVIEW`, or `RETIRED` dataset can start an experiment;
- every expected field exposes its provenance and source version;
- incumbent and LLM-suggested outputs never become truth without independent
  confirmation or an explicitly validated approval policy;
- automated authoritative labels are reproducible from a versioned source or
  rule, and source disagreements route to review;
- refreshing a dataset creates a new version and cannot mutate past results;
- every disallowed task/evaluator pair is rejected;
- deterministic tasks run without an LLM judge;
- judge requests contain required context and exclude blinded metadata;
- `REVIEW` is not counted as pass;
- `ERROR` remains in the denominator and report;
- a source model response is never silently treated as ground truth; and
- one-tool-call evaluation never executes or continues the tool trajectory.

## Quality gates

Every change must pass Ruff formatting/linting, Pyright, offline pytest, package
build, schema migration tests, and the synthetic smoke flow. User-facing changes
must update README, the scope document when the contract changes, architecture,
roadmap, examples, and changelog as applicable.

Normal CI must not require provider credentials or network access. Live-provider
tests are manual, spend-capped, and excluded from correctness gates.

## Explicit non-goals

Do not schedule a universal evaluator, arbitrary “answer quality” score,
creative preference grader, end-to-end retrieval grader, autonomous coding-agent
grader, or safety certification feature. Do not use embeddings, clustering, or
learned evaluators as correctness verdicts unless a future scoped milestone
defines their task contract and validates them against labeled data.

Agent traces remain later work. Packaging, provider breadth, hosted accounts,
TypeScript support, price catalogs, and release automation are secondary to a
valid, reproducible evaluation core.
