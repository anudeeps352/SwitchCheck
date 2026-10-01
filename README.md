# Switchcheck

Switchcheck helps developers decide whether changing an LLM model, prompt, or
parameters will break their application. It records real calls, replays them
against a candidate configuration, evaluates the outputs, and creates a local
report.

This repository is at the Stage 0 foundation milestone. The product scope and
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
```

`switchcheck init` currently creates the local `.switchcheck` directory. It
will create and migrate the SQLite database in Stage 1.

## Repository layout

```text
src/switchcheck/    Package source
tests/              Offline tests
.github/workflows/  Continuous integration
```

## License

MIT. See [LICENSE](LICENSE).
