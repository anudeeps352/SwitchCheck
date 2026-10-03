# Switchcheck

Switchcheck helps developers decide whether changing an LLM model, prompt, or
parameters will break their application. It records real calls, replays them
against a candidate configuration, evaluates the outputs, and creates a local
report.

The core workflow through Stage 4 (reporting) is complete, and Stage 5 adds
the release-readiness example, smoke test, and operational guidance. The
product scope and delivery plan are in [architecture.md](architecture.md) and
[development-plan.md](development-plan.md).

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
failure-first output comparisons, checker reasons, aggregate metrics, and the
replay configuration. It contains recorded outputs, so handle it as sensitive.

## Repository layout

```text
src/switchcheck/    Package source
tests/              Offline tests
.github/workflows/  Continuous integration
```

## License

MIT. See [LICENSE](LICENSE).
