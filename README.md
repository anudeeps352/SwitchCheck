# Switchcheck

Switchcheck helps developers decide whether changing an LLM model, prompt, or
parameters will break their application. It records real calls, replays them
against a candidate configuration, evaluates the outputs, and creates a local
report.

This repository is in Stage 1 (recording). The product scope and
delivery plan are in [architecture.md](architecture.md) and
[development-plan.md](development-plan.md).

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

## Repository layout

```text
src/switchcheck/    Package source
tests/              Offline tests
.github/workflows/  Continuous integration
```

## License

MIT. See [LICENSE](LICENSE).
