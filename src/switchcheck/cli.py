"""Command-line interface for Switchcheck."""

from __future__ import annotations

from pathlib import Path

import typer

from switchcheck import __version__

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
    """Create the local Switchcheck directory.

    Stage 1 will add the SQLite schema migration to this command.
    """
    data_directory = path.resolve() / ".switchcheck"
    data_directory.mkdir(parents=True, exist_ok=True)
    typer.echo(f"Initialised {data_directory}")
