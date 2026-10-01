"""Smoke tests for the public command-line entry point."""

from pathlib import Path

from typer.testing import CliRunner

from switchcheck import __version__
from switchcheck.cli import app

runner = CliRunner()


def test_version() -> None:
    """The CLI should expose the package version."""
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_init_creates_local_directory() -> None:
    """Initialisation should create the project-local data directory."""
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        assert Path(".switchcheck").is_dir()
