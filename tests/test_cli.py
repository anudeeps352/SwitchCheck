"""Smoke tests for the public command-line entry point."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from switchcheck import __version__
from switchcheck.cli import app
from switchcheck.replay import replay
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


def test_dataset_import_command_creates_labeled_cases(tmp_path: Path) -> None:
    """The CLI imports a human-reviewed JSONL dataset without a model call."""
    source = tmp_path / "cases.jsonl"
    source.write_text(
        json.dumps(
            {
                "task_type": "extraction",
                "messages": [{"role": "user", "content": "Invoice 1"}],
                "expected": {"invoice_id": "1"},
                "metadata": {"category": "invoice"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "dataset",
            "import",
            "invoice-v1",
            str(source),
            "--path",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "Imported 1 case into dataset invoice-v1" in result.stdout

    check = runner.invoke(
        app,
        ["dataset", "check", "invoice-v1", "--path", str(tmp_path)],
    )
    assert check.exit_code == 0
    assert "1/1 cases eligible" in check.stdout


def test_dataset_import_accepts_one_task_type_for_all_cases(tmp_path: Path) -> None:
    source = tmp_path / "cases.jsonl"
    source.write_text(
        json.dumps(
            {
                "messages": [{"role": "user", "content": "Classify this"}],
                "expected": "billing",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "dataset",
            "import",
            "labels-v1",
            str(source),
            "--task-type",
            "classification",
            "--path",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "Imported 1 case" in result.stdout


def test_evaluate_command_runs_imported_dataset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "cases.jsonl"
    source.write_text(
        json.dumps(
            {
                "messages": [{"role": "user", "content": "Classify this"}],
                "expected": "billing",
                "evaluators": ["exact"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    imported = runner.invoke(
        app,
        [
            "dataset",
            "import",
            "labels-v1",
            str(source),
            "--task-type",
            "classification",
            "--path",
            str(tmp_path),
        ],
    )
    assert imported.exit_code == 0

    monkeypatch.setattr(
        "switchcheck.experiments._load_litellm_completion",
        lambda: lambda **_: {"choices": [{"message": {"content": "billing"}}]},
    )
    evaluated = runner.invoke(
        app,
        [
            "evaluate",
            "--dataset",
            "labels-v1",
            "--model",
            "fake/candidate",
            "--path",
            str(tmp_path),
        ],
    )

    assert evaluated.exit_code == 0
    assert "1/1 passed (100%)" in evaluated.stdout


def test_report_writes_html(tmp_path: Path) -> None:
    """The CLI renders a persisted replay without provider credentials."""
    create_run(
        tmp_path,
        model="fake/model",
        messages=[{"role": "user", "content": "Hello"}],
        params={},
    )
    summary = replay(
        tmp_path,
        target_model="candidate/model",
        completion=lambda **_: {"choices": [{"message": {"content": "Hello"}}]},
    )

    result = runner.invoke(app, ["report", "--path", str(tmp_path), "--replay", summary.replay_id])

    assert result.exit_code == 0
    assert "Wrote report to" in result.stdout
    assert (tmp_path / ".switchcheck" / "reports" / f"{summary.replay_id}.html").is_file()
