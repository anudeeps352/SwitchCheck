"""SQLite storage and schema migrations for Switchcheck."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DATABASE_DIRECTORY = ".switchcheck"
DATABASE_FILENAME = "switchcheck.sqlite3"
SCHEMA_VERSION = 1

_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    tag TEXT,
    model TEXT NOT NULL,
    params_json TEXT NOT NULL,
    messages_json TEXT NOT NULL,
    tools_json TEXT,
    output_text TEXT,
    output_json TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd REAL,
    latency_ms INTEGER,
    error TEXT
);

CREATE TABLE IF NOT EXISTS replays (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    name TEXT,
    tag TEXT,
    target_model TEXT NOT NULL,
    prompt_override TEXT,
    params_json TEXT,
    checker_json TEXT NOT NULL,
    package_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS replay_results (
    id TEXT PRIMARY KEY,
    replay_id TEXT NOT NULL REFERENCES replays(id),
    run_id TEXT NOT NULL REFERENCES runs(id),
    output_text TEXT,
    output_json TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd REAL,
    latency_ms INTEGER,
    passed INTEGER CHECK (passed IN (0, 1)),
    score REAL CHECK (score >= 0 AND score <= 1),
    verdict_json TEXT,
    error TEXT,
    UNIQUE (replay_id, run_id)
);

CREATE INDEX IF NOT EXISTS idx_runs_tag ON runs(tag);
CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at);
CREATE INDEX IF NOT EXISTS idx_replay_results_replay_id ON replay_results(replay_id);
"""


def database_path(project_directory: Path) -> Path:
    """Return the project-local database path without creating it."""
    return project_directory.resolve() / DATABASE_DIRECTORY / DATABASE_FILENAME


def connect(path: Path) -> sqlite3.Connection:
    """Open a configured SQLite connection for Switchcheck data."""
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(project_directory: Path) -> Path:
    """Create or safely migrate the project-local Switchcheck database."""
    path = database_path(project_directory)
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = connect(path)
    try:
        with connection:
            connection.execute("PRAGMA journal_mode = WAL")
            version_row = connection.execute("PRAGMA user_version").fetchone()
            if version_row is None:
                raise RuntimeError("Unable to read the database schema version.")
            current_version = int(version_row[0])

            if current_version > SCHEMA_VERSION:
                message = (
                    f"Database schema version {current_version} is newer than this "
                    f"Switchcheck version supports ({SCHEMA_VERSION})."
                )
                raise RuntimeError(message)

            if current_version < 1:
                connection.executescript(_SCHEMA_V1)
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    finally:
        connection.close()
    return path
