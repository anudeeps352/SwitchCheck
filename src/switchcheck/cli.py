"""Command-line interface for Switchcheck."""

from __future__ import annotations

from pathlib import Path

import typer

from switchcheck import __version__
from switchcheck.store import initialize_database

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
def init(path: Path = typer.Argument(Path("."), help="Project directory to initialise.")) -> None:
    """Create or migrate the project-local Switchcheck database."""
    path = initialize_database(path)
    typer.echo(f"Initialised {path}")
