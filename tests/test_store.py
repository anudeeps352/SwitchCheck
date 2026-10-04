"""Tests for SQLite database creation and migrations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from switchcheck.contracts import Criterion
from switchcheck.store import (
    SCHEMA_VERSION,
    create_dataset,
    create_evaluation_case,
    create_run,
    database_path,
    initialize_database,
    list_evaluation_cases,
    list_runs,
)
from switchcheck.task_types import EvaluatorType, TaskType


def test_initialize_database_creates_schema(tmp_path: Path) -> None:
    """Initialisation should create the database, tables, indexes, and version."""
    path = initialize_database(tmp_path)

    assert path == database_path(tmp_path)
    assert path.is_file()

    with sqlite3.connect(path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            )
        }
        indexes = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index' ORDER BY name"
            )
        }
        version_row = connection.execute("PRAGMA user_version").fetchone()
        assert version_row is not None
        version = version_row[0]

    assert tables == {
        "datasets",
        "evaluation_cases",
        "replay_results",
        "replays",
        "runs",
    }
    assert {
        "idx_replay_results_replay_id",
        "idx_runs_created_at",
        "idx_runs_tag",
    }.issubset(indexes)
    assert version == SCHEMA_VERSION


def test_initialize_database_is_idempotent(tmp_path: Path) -> None:
    """Initialisation should be safe to repeat for an existing database."""
    first_path = initialize_database(tmp_path)
    second_path = initialize_database(tmp_path)

    assert second_path == first_path


def test_initialize_database_rejects_newer_schema(tmp_path: Path) -> None:
    """An older package must not write to a newer database schema."""
    path = initialize_database(tmp_path)

    with sqlite3.connect(path) as connection:
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")

    try:
        initialize_database(tmp_path)
    except RuntimeError as error:
        assert "newer" in str(error)
    else:
        raise AssertionError("Expected initialize_database to reject a newer schema.")


def test_initialize_database_migrates_v1_database(tmp_path: Path) -> None:
    """Existing replay databases gain dataset tables without losing their runs."""
    path = database_path(tmp_path)
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE runs (
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, tag TEXT,
                model TEXT NOT NULL, params_json TEXT NOT NULL,
                messages_json TEXT NOT NULL, tools_json TEXT, output_text TEXT,
                output_json TEXT, input_tokens INTEGER, output_tokens INTEGER,
                cost_usd REAL, latency_ms INTEGER, error TEXT
            )
            """
        )
        connection.execute("PRAGMA user_version = 1")

    initialize_database(tmp_path)

    with sqlite3.connect(path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            )
        }
        version = connection.execute("PRAGMA user_version").fetchone()[0]
    assert {"datasets", "evaluation_cases"}.issubset(tables)
    assert version == SCHEMA_VERSION


def test_initialize_database_migrates_v3_cases_as_explicit_legacy_rows(tmp_path: Path) -> None:
    """Pre-scope cases remain readable but are not assigned a guessed task type."""
    path = database_path(tmp_path)
    initialize_database(tmp_path)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("DROP TABLE evaluation_cases")
        connection.execute("DROP TABLE datasets")
        connection.executescript(
            """
            CREATE TABLE datasets (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                name TEXT NOT NULL UNIQUE,
                description TEXT
            );
            CREATE TABLE evaluation_cases (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                dataset_id TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
                messages_json TEXT NOT NULL,
                expected_json TEXT NOT NULL,
                criteria TEXT,
                metadata_json TEXT NOT NULL,
                source_run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
                task_type TEXT,
                evaluator_json TEXT NOT NULL DEFAULT '[]'
            );
            """
        )
        connection.execute("PRAGMA user_version = 3")

    initialize_database(tmp_path)

    with sqlite3.connect(path) as connection:
        case_columns = {row[1] for row in connection.execute("PRAGMA table_info(evaluation_cases)")}
        dataset_columns = {row[1] for row in connection.execute("PRAGMA table_info(datasets)")}
    assert {"contract_version", "context_json", "criteria_json"}.issubset(case_columns)
    assert "contract_version" in dataset_columns


def test_dataset_and_evaluation_cases_round_trip(tmp_path: Path) -> None:
    """Labeled cases retain their truth, criteria, metadata, and provenance."""
    source = create_run(
        tmp_path,
        model="source/model",
        messages=[{"role": "user", "content": "Invoice 42"}],
        params={},
    )
    dataset = create_dataset(tmp_path, name="invoices-v1", description="Reviewed invoices")
    case = create_evaluation_case(
        tmp_path,
        dataset_id=dataset.id,
        task_type=TaskType.EXTRACTION,
        messages=[{"role": "user", "content": "Invoice 42"}],
        expected={"invoice_id": "42", "total": 10.5},
        criteria=(Criterion(id="all_fields", requirement="Must extract every invoice field."),),
        metadata={"difficulty": "easy"},
        source_run_id=source.id,
        evaluators=(EvaluatorType.SCHEMA, EvaluatorType.FIELDS),
    )

    cases = list_evaluation_cases(tmp_path, dataset_id=dataset.id)

    assert cases == [case]
    assert cases[0].expected == {"invoice_id": "42", "total": 10.5}
    assert cases[0].metadata == {"difficulty": "easy"}
    assert cases[0].task_type is TaskType.EXTRACTION
    assert cases[0].evaluators == (EvaluatorType.SCHEMA, EvaluatorType.FIELDS)


def test_create_evaluation_case_rejects_disallowed_evaluator(tmp_path: Path) -> None:
    dataset = create_dataset(tmp_path, name="labels-v1")

    with pytest.raises(ValueError, match="not permitted"):
        create_evaluation_case(
            tmp_path,
            dataset_id=dataset.id,
            task_type=TaskType.CLASSIFICATION,
            messages=[{"role": "user", "content": "Classify this"}],
            expected="billing",
            evaluators=(EvaluatorType.CRITERIA_JUDGE,),
        )


def test_list_runs_filters_tag_and_orders_newest_first(tmp_path: Path) -> None:
    """Run history supports the selection required by the replay workflow."""
    first = create_run(
        tmp_path,
        model="first-model",
        messages=[{"role": "user", "content": "first"}],
        params={},
        tag="first",
    )
    second = create_run(
        tmp_path,
        model="second-model",
        messages=[{"role": "user", "content": "second"}],
        params={},
        tag="second",
    )

    assert [run.id for run in list_runs(tmp_path)] == [second.id, first.id]
    assert [run.id for run in list_runs(tmp_path, tag="first")] == [first.id]
    assert list_runs(tmp_path, tag="missing") == []


def test_list_runs_can_exclude_provider_errors(tmp_path: Path) -> None:
    successful = create_run(
        tmp_path,
        model="source/model",
        messages=[{"role": "user", "content": "successful"}],
        params={},
        tag="comparison",
    )
    failed = create_run(
        tmp_path,
        model="source/model",
        messages=[{"role": "user", "content": "failed"}],
        params={},
        tag="comparison",
        error="NotFoundError: invalid model",
    )

    assert [run.id for run in list_runs(tmp_path, tag="comparison")] == [
        failed.id,
        successful.id,
    ]
    assert [run.id for run in list_runs(tmp_path, tag="comparison", include_errors=False)] == [
        successful.id
    ]
