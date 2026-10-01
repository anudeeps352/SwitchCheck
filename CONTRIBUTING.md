# Contributing to Switchcheck

## Local checks

Install development dependencies and the commit hooks as described in the
[README](README.md). Before opening a pull request, run:

```powershell
ruff format --check .
ruff check .
pyright
pytest
python -m build
```

## Pull requests

Keep pull requests focused, include tests for behavior changes, and update the
README plus `CHANGELOG.md` when a user-visible interface changes. Tests must not
need an LLM API key or network access.

## Commit hooks

`pre-commit install` enables lightweight formatting and file-hygiene checks
before each commit. CI remains the final authority and runs the complete suite.
