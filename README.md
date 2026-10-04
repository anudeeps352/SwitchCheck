# Switchcheck

Switchcheck determines whether changing an LLM model, prompt, or parameters
preserves expected behavior for a fixed set of repeatable, single-interaction
task types. Every evaluated case needs a predefined expected value,
deterministic constraint, supplied reference/context, or explicit observable
rubric.

Switchcheck is not a universal LLM grader. It does not claim that one model can
replace another for arbitrary applications, and it never silently falls back to
asking a judge model whether an answer is “good.” See the authoritative
[supported evaluation scope](docs/supported-evaluation-scope.md).

The core workflow through Stage 4 (reporting) and the Stage 5 release-readiness
example, smoke test, and operational guidance are complete. Active development
is the labeled-evaluation core: models are measured against explicit expected
outcomes rather than treating the original model response as ground truth. The
technical boundaries are in [architecture.md](architecture.md), and the roadmap
is in [development-plan.md](development-plan.md).

## Next milestone: labeled evaluations

The dataset foundation imports named JSONL datasets and can now run an initial
deterministic experiment against a candidate model. Task metrics and a dedicated
experiment report remain the next pieces. Calibrated criteria judging will be
added only for eligible free-text task types.

LLM judging intentionally follows labeled datasets. Without human-reviewed
examples, there is no reliable way to measure whether an automated judge is
making good decisions.

The first part of this milestone is available now. Create a UTF-8 JSONL file
with one labeled case per line:

```json
{"contract_version":1,"task_type":"extraction","messages":[{"role":"user","content":"Invoice INV-1001 totals USD 42.50."}],"expected":{"invoice_id":"INV-1001","total_usd":42.5},"evaluators":["schema","fields","numeric"],"metadata":{"difficulty":"easy"}}
```

Import it into the project-local database:

```powershell
switchcheck dataset import invoice-v1 cases.jsonl --description "Reviewed invoices"
```

The importer validates the complete file, including task types and declared
task/evaluator combinations, before writing any cases. Running an
imported dataset against a candidate model and reporting ground-truth metrics is
the next implementation step.

Check an imported dataset's eligibility without making provider calls:

```powershell
switchcheck dataset check invoice-v1
```

When all cases share a task type, declare it once instead of repeating it in
every JSONL row:

```powershell
switchcheck dataset import invoice-v1 cases.jsonl --task-type extraction
```

Run the initial deterministic experiment workflow:

```powershell
switchcheck evaluate --dataset invoice-v1 --model openai/gpt-4o-mini `
  --schema invoice-schema.json --numeric-tolerance 0.01
```

The command validates the complete dataset and evaluator setup before provider
calls, persists pending and terminal results, and reports counts for `PASS`,
`FAIL`, `REVIEW`, and `ERROR`. It also writes a self-contained experiment HTML
report with applicable field, tool, argument, and classification metrics.
Criteria judging and per-case evaluator configuration are not implemented yet.

Run the complete labeled-evaluation workflow offline:

```powershell
python examples/dataset_evaluation/demo.py --project .
```

The demo imports two extraction cases, runs a fake candidate with no credentials
or network, persists one pass and one failure, calculates metrics, and writes an
HTML report under `.switchcheck/reports/`.

Free-text task types additionally use structured `criteria` records and, where
required, `context` or `reference`. See the
[case contract](architecture.md#dataset-case-contract).

### Dataset creation: current and planned

Dataset import is currently manual: a developer or reviewer prepares JSONL and
runs `switchcheck dataset import`. The planned pipeline automates traffic
sampling, redaction, deduplication, coverage selection, enrichment from systems
of record/rules/trusted datasets, draft label and rubric suggestions, review
prioritization, approval, versioning, and refresh.

Automation does not make an incumbent or label-generating model authoritative.
Model-generated expectations remain `DRAFT`; only an approved case backed by
human review or configured authoritative provenance can be used as ground truth.
See the [assisted dataset-building pipeline](architecture.md#assisted-dataset-building-pipeline).

## Try the complete workflow offline

The synthetic invoice-extractor example records two calls, replays them with
deterministic JSON checks, and writes an HTML report. It uses no credentials or
network access, making it a useful installation and CI smoke test:

```powershell
python examples/invoice_extractor/demo.py --fake --project .
```

To use a real LiteLLM-supported provider instead, omit `--fake` and provide
the appropriate provider credentials in the environment. Start with a
low-cost model and a small sample because replay makes fresh provider calls.
See [privacy and provider limits](docs/privacy-and-provider-limits.md) before
recording application data.

For a concrete two-provider walkthrough, the
[support-ticket example](examples/support_ticket_classifier/README.md) records
five source-model calls and replays them with a second provider.

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

Run the local quality checks:

```powershell
ruff format --check .
ruff check .
pyright
pytest
python -m build
```

The initial CLI is available after installation:

```powershell
switchcheck --version
switchcheck init
switchcheck runs --tag invoice-extractor
switchcheck replay --tag invoice-extractor --model openai/gpt-4o-mini --dry-run
switchcheck report --replay REPLAY_ID
```

`switchcheck init` creates (or safely migrates) the local SQLite database at
`.switchcheck/switchcheck.sqlite3`.

## Recording a call

Install a LiteLLM-supported provider's credentials in your environment, then
route non-streaming chat completions through Switchcheck:

```python
from switchcheck import client

response = client.chat(
    model="openai/gpt-4o-mini",
    messages=[{"role": "user", "content": "Extract the invoice total."}],
    tag="invoice-extractor",
    temperature=0,
)
```

Successful calls and provider errors are stored locally. Treat the database as
sensitive because it can contain application prompts and outputs.

## Replaying recorded calls

Use `--dry-run` first to inspect the number of selected calls without contacting
a provider. A regular replay persists its session and every individual result,
including provider errors. Cost estimates are currently unavailable until local
pricing data is added.

Recorded source calls that ended in provider errors are kept in run history for
diagnosis but excluded from replay selection.

Add repeatable deterministic checks to decide whether each output is acceptable:

```powershell
switchcheck replay --tag invoice-extractor --model openai/gpt-4o-mini `
  --check exact --check json-schema:invoice-schema.json
```

Available checks are `exact`, `contains:TEXT`, `regex:PATTERN`,
`json-schema:FILE`, and `json-field:PATH`. All configured checks must pass; a
candidate provider error is always recorded as a failed result.

## Reporting a replay

Create a standalone HTML report after a replay completes:

```powershell
switchcheck report --replay REPLAY_ID
```

The default destination is `.switchcheck/reports/REPLAY_ID.html`; pass
`--output path/to/report.html` to choose another location. The report includes
failure-first output comparisons, field-specific checker reasons,
source-versus-candidate latency and token totals, provider-reported cost, and
the replay configuration. It contains recorded outputs, so handle it as
sensitive.

## Repository layout

```text
src/switchcheck/    Package source
tests/              Offline tests
.github/workflows/  Continuous integration
```

## License

MIT. See [LICENSE](LICENSE).
