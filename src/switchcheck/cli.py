"""Command-line interface for Switchcheck."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from switchcheck import __version__
from switchcheck.replay import replay, replay_dry_run
from switchcheck.store import initialize_database, list_runs

app = typer.Typer(
    add_completion=False,
    help="Record and replay LLM calls to assess model or prompt changes.",
    no_args_is_help=True,
)


def version_callback(value: bool) -> None:
    """Print the installed version when requested."""
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show the installed Switchcheck version and exit.",
    ),
) -> None:
    """Record and replay LLM calls to assess model or prompt changes."""


@app.command()
def init(
    path: Annotated[Path, typer.Argument(help="Project directory to initialise.")] = Path("."),
) -> None:
    """Create or migrate the project-local Switchcheck database."""
    path = initialize_database(path)
    typer.echo(f"Initialised {path}")


@app.command()
def runs(
    tag: Annotated[str | None, typer.Option(help="Only include this exact tag.")] = None,
    limit: Annotated[int, typer.Option(min=1, help="Maximum runs to show.")] = 20,
    path: Annotated[Path, typer.Option(help="Project directory to inspect.")] = Path("."),
) -> None:
    """List most recently recorded application calls."""
    recorded_runs = list_runs(path, tag=tag, limit=limit)
    if not recorded_runs:
        typer.echo("No recorded runs found.")
        return
    for run in recorded_runs:
        status = "error" if run.error else "ok"
        typer.echo(f"{run.id}\t{run.created_at}\t{run.model}\t{run.tag or '-'}\t{status}")


@app.command("replay")
def replay_command(
    model: Annotated[str, typer.Option("--model", help="Candidate LiteLLM model.")],
    tag: Annotated[str | None, typer.Option(help="Only replay this exact tag.")] = None,
    limit: Annotated[int, typer.Option(min=1, help="Maximum calls to select.")] = 20,
    concurrency: Annotated[int, typer.Option(min=1, help="Maximum provider calls in flight.")] = 1,
    dry_run: Annotated[
        bool, typer.Option(help="Show the selection without provider calls.")
    ] = False,
    path: Annotated[Path, typer.Option(help="Project directory to inspect.")] = Path("."),
) -> None:
    """Replay recorded calls against a candidate model."""
    if dry_run:
        count = replay_dry_run(path, tag=tag, limit=limit)
        typer.echo(f"Selected {count} runs. Cost estimate: unavailable.")
        return
    summary = replay(
        path,
        target_model=model,
        tag=tag,
        limit=limit,
        concurrency=concurrency,
    )
    typer.echo(
        f"Replay {summary.replay_id}: {summary.completed_count} completed, "
        f"{summary.failed_count} failed (of {summary.selected_count})."
    )
