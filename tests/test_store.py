"""Tests for SQLite database creation and migrations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from switchcheck.store import SCHEMA_VERSION, database_path, initialize_database


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

    assert tables == {"replay_results", "replays", "runs"}
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
