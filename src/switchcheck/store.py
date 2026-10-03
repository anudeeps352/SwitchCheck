"""SQLite storage and schema migrations for Switchcheck."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from switchcheck import __version__

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


@dataclass(frozen=True)
class Run:
    """A recorded non-streaming chat-completion request and its outcome."""

    id: str
    created_at: str
    tag: str | None
    model: str
    params: dict[str, Any]
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None
    output_text: str | None
    output_json: Any | None
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    latency_ms: int | None
    error: str | None


@dataclass(frozen=True)
class ReplayResult:
    """One candidate-model attempt for a recorded run."""

    id: str
    replay_id: str
    run_id: str
    output_text: str | None
    output_json: Any | None
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    latency_ms: int | None
    passed: bool | None
    score: float | None
    verdict: list[dict[str, Any]] | None
    error: str | None


@dataclass(frozen=True)
class Replay:
    """The configuration captured when a replay session was started."""

    id: str
    created_at: str
    tag: str | None
    target_model: str
    params: dict[str, Any]
    checkers: list[dict[str, Any]]
    package_version: str


@dataclass(frozen=True)
class ReportCase:
    """A replay result paired with its recorded source output for reporting."""

    run: Run
    result: ReplayResult


def database_path(project_directory: Path) -> Path:
    """Return the project-local database path without creating it."""
    return project_directory.resolve() / DATABASE_DIRECTORY / DATABASE_FILENAME


def connect(path: Path) -> sqlite3.Connection:
    """Open a configured SQLite connection for Switchcheck data."""
    connection = sqlite3.connect(path, timeout=30)
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


def create_run(
    project_directory: Path,
    *,
    model: str,
    messages: list[dict[str, Any]],
    params: dict[str, Any],
    tag: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    output_text: str | None = None,
    output_json: Any | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_usd: float | None = None,
    latency_ms: int | None = None,
    error: str | None = None,
) -> Run:
    """Persist and return one application call, including a provider error if any."""
    path = initialize_database(project_directory)
    run = Run(
        id=str(uuid4()),
        created_at=datetime.now(timezone.utc).isoformat(),
        tag=tag,
        model=model,
        params=params,
        messages=messages,
        tools=tools,
        output_text=output_text,
        output_json=output_json,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        error=error,
    )
    with connect(path) as connection:
        connection.execute(
            """
            INSERT INTO runs (
                id, created_at, tag, model, params_json, messages_json, tools_json,
                output_text, output_json, input_tokens, output_tokens, cost_usd,
                latency_ms, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.id,
                run.created_at,
                run.tag,
                run.model,
                _dump_json(run.params),
                _dump_json(run.messages),
                _dump_json(run.tools) if run.tools is not None else None,
                run.output_text,
                _dump_json(run.output_json) if run.output_json is not None else None,
                run.input_tokens,
                run.output_tokens,
                run.cost_usd,
                run.latency_ms,
                run.error,
            ),
        )
    return run


def list_runs(project_directory: Path, *, tag: str | None = None, limit: int = 20) -> list[Run]:
    """Return newest recorded runs, optionally limited to an exact tag."""
    if limit < 1:
        raise ValueError("limit must be at least 1")
    path = database_path(project_directory)
    if not path.is_file():
        return []
    query = "SELECT * FROM runs"
    parameters: tuple[object, ...] = ()
    if tag is not None:
        query += " WHERE tag = ?"
        parameters = (tag,)
    query += " ORDER BY created_at DESC LIMIT ?"
    with connect(path) as connection:
        rows = connection.execute(query, (*parameters, limit)).fetchall()
    return [_run_from_row(row) for row in rows]


def create_replay(
    project_directory: Path,
    *,
    target_model: str,
    tag: str | None,
    params: dict[str, Any],
    checker_config: list[dict[str, Any]] | None = None,
) -> str:
    """Create a replay session before any candidate provider call is made."""
    path = initialize_database(project_directory)
    replay_id = str(uuid4())
    with connect(path) as connection:
        connection.execute(
            """
            INSERT INTO replays (
                id, created_at, tag, target_model, params_json, checker_json, package_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                replay_id,
                datetime.now(timezone.utc).isoformat(),
                tag,
                target_model,
                _dump_json(params),
                _dump_json(checker_config or []),
                __version__,
            ),
        )
    return replay_id


def create_replay_result(project_directory: Path, *, replay_id: str, run_id: str) -> ReplayResult:
    """Persist a pending result so interrupted replays can be resumed."""
    path = initialize_database(project_directory)
    result = ReplayResult(
        id=str(uuid4()),
        replay_id=replay_id,
        run_id=run_id,
        output_text=None,
        output_json=None,
        input_tokens=None,
        output_tokens=None,
        cost_usd=None,
        latency_ms=None,
        passed=None,
        score=None,
        verdict=None,
        error=None,
    )
    with connect(path) as connection:
        connection.execute(
            "INSERT OR IGNORE INTO replay_results (id, replay_id, run_id) VALUES (?, ?, ?)",
            (result.id, result.replay_id, result.run_id),
        )
        row = connection.execute(
            "SELECT * FROM replay_results WHERE replay_id = ? AND run_id = ?", (replay_id, run_id)
        ).fetchone()
    if row is None:
        raise RuntimeError("Unable to create replay result.")
    return _replay_result_from_row(row)


def update_replay_result(
    project_directory: Path,
    *,
    result_id: str,
    output_text: str | None = None,
    output_json: Any | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_usd: float | None = None,
    latency_ms: int | None = None,
    passed: bool | None = None,
    score: float | None = None,
    verdict: list[dict[str, Any]] | None = None,
    error: str | None = None,
) -> ReplayResult:
    """Save one completed candidate outcome without affecting other results."""
    path = initialize_database(project_directory)
    with connect(path) as connection:
        connection.execute(
            """
            UPDATE replay_results
            SET output_text = ?, output_json = ?, input_tokens = ?, output_tokens = ?,
                cost_usd = ?, latency_ms = ?, passed = ?, score = ?, verdict_json = ?, error = ?
            WHERE id = ?
            """,
            (
                output_text,
                _dump_json(output_json) if output_json is not None else None,
                input_tokens,
                output_tokens,
                cost_usd,
                latency_ms,
                int(passed) if passed is not None else None,
                score,
                _dump_json(verdict) if verdict is not None else None,
                error,
                result_id,
            ),
        )
        row = connection.execute(
            "SELECT * FROM replay_results WHERE id = ?", (result_id,)
        ).fetchone()
    if row is None:
        raise ValueError(f"Unknown replay result: {result_id}")
    return _replay_result_from_row(row)


def list_replay_results(project_directory: Path, *, replay_id: str) -> list[ReplayResult]:
    """Return replay results in a stable order for display and resume."""
    path = database_path(project_directory)
    if not path.is_file():
        return []
    with connect(path) as connection:
        rows = connection.execute(
            "SELECT * FROM replay_results WHERE replay_id = ? ORDER BY id", (replay_id,)
        ).fetchall()
    return [_replay_result_from_row(row) for row in rows]


def get_replay(project_directory: Path, *, replay_id: str) -> Replay | None:
    """Return a replay configuration, if it belongs to this project."""
    path = database_path(project_directory)
    if not path.is_file():
        return None
    with connect(path) as connection:
        row = connection.execute("SELECT * FROM replays WHERE id = ?", (replay_id,)).fetchone()
    return _replay_from_row(row) if row is not None else None


def list_report_cases(project_directory: Path, *, replay_id: str) -> list[ReportCase]:
    """Return replay cases with their source runs, failures first and order stable."""
    path = database_path(project_directory)
    if not path.is_file():
        return []
    with connect(path) as connection:
        rows = connection.execute(
            """
            SELECT rr.*, r.id AS source_run_id, r.created_at AS run_created_at, r.tag AS run_tag,
                   r.model AS run_model, r.params_json AS run_params_json,
                   r.messages_json AS run_messages_json, r.tools_json AS run_tools_json,
                   r.output_text AS run_output_text, r.output_json AS run_output_json,
                   r.input_tokens AS run_input_tokens, r.output_tokens AS run_output_tokens,
                   r.cost_usd AS run_cost_usd, r.latency_ms AS run_latency_ms,
                   r.error AS run_error
            FROM replay_results AS rr
            JOIN runs AS r ON r.id = rr.run_id
            WHERE rr.replay_id = ?
            ORDER BY CASE WHEN rr.passed IS 1 THEN 1 ELSE 0 END, rr.id
            """,
            (replay_id,),
        ).fetchall()
    return [
        ReportCase(run=_run_from_report_row(row), result=_replay_result_from_row(row))
        for row in rows
    ]


def _dump_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _run_from_row(row: sqlite3.Row) -> Run:
    return Run(
        id=row["id"],
        created_at=row["created_at"],
        tag=row["tag"],
        model=row["model"],
        params=json.loads(row["params_json"]),
        messages=json.loads(row["messages_json"]),
        tools=json.loads(row["tools_json"]) if row["tools_json"] is not None else None,
        output_text=row["output_text"],
        output_json=json.loads(row["output_json"]) if row["output_json"] is not None else None,
        input_tokens=row["input_tokens"],
        output_tokens=row["output_tokens"],
        cost_usd=row["cost_usd"],
        latency_ms=row["latency_ms"],
        error=row["error"],
    )


def _replay_result_from_row(row: sqlite3.Row) -> ReplayResult:
    return ReplayResult(
        id=row["id"],
        replay_id=row["replay_id"],
        run_id=row["run_id"],
        output_text=row["output_text"],
        output_json=json.loads(row["output_json"]) if row["output_json"] is not None else None,
        input_tokens=row["input_tokens"],
        output_tokens=row["output_tokens"],
        cost_usd=row["cost_usd"],
        latency_ms=row["latency_ms"],
        passed=bool(row["passed"]) if row["passed"] is not None else None,
        score=row["score"],
        verdict=json.loads(row["verdict_json"]) if row["verdict_json"] is not None else None,
        error=row["error"],
    )


def _replay_from_row(row: sqlite3.Row) -> Replay:
    return Replay(
        id=row["id"],
        created_at=row["created_at"],
        tag=row["tag"],
        target_model=row["target_model"],
        params=json.loads(row["params_json"] or "{}"),
        checkers=json.loads(row["checker_json"]),
        package_version=row["package_version"],
    )


def _run_from_report_row(row: sqlite3.Row) -> Run:
    return Run(
        id=row["source_run_id"],
        created_at=row["run_created_at"],
        tag=row["run_tag"],
        model=row["run_model"],
        params=json.loads(row["run_params_json"]),
        messages=json.loads(row["run_messages_json"]),
        tools=json.loads(row["run_tools_json"]) if row["run_tools_json"] is not None else None,
        output_text=row["run_output_text"],
        output_json=json.loads(row["run_output_json"])
        if row["run_output_json"] is not None
        else None,
        input_tokens=row["run_input_tokens"],
        output_tokens=row["run_output_tokens"],
        cost_usd=row["run_cost_usd"],
        latency_ms=row["run_latency_ms"],
        error=row["run_error"],
    )
