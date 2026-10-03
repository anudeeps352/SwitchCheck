"""Smoke tests for the public command-line entry point."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from switchcheck import __version__
from switchcheck.cli import app
from switchcheck.store import create_run

runner = CliRunner()


def test_version() -> None:
    """The CLI should expose the package version."""
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_init_creates_local_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Initialisation should create the project-local SQLite database."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0
    assert Path(".switchcheck/switchcheck.sqlite3").is_file()


def test_runs_lists_filtered_history(tmp_path: Path) -> None:
    """The CLI exposes selection by tag without requiring a provider."""
    create_run(
        tmp_path,
        model="fake/model",
        messages=[{"role": "user", "content": "Hello"}],
        params={},
        tag="included",
    )
    create_run(
        tmp_path,
        model="other/model",
        messages=[{"role": "user", "content": "Ignore"}],
        params={},
        tag="excluded",
    )

    result = runner.invoke(app, ["runs", "--path", str(tmp_path), "--tag", "included"])

    assert result.exit_code == 0
    assert "fake/model" in result.stdout
    assert "included" in result.stdout
    assert "other/model" not in result.stdout


def test_replay_dry_run_reports_selection(tmp_path: Path) -> None:
    """The CLI dry run never needs provider credentials."""
    create_run(
        tmp_path,
        model="fake/model",
        messages=[{"role": "user", "content": "Hello"}],
        params={},
        tag="included",
    )

    result = runner.invoke(
        app,
        [
            "replay",
            "--path",
            str(tmp_path),
            "--tag",
            "included",
            "--model",
            "candidate/model",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert "Selected 1 runs" in result.stdout
