"""Command-line interface for Switchcheck."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from switchcheck import __version__
from switchcheck.checkers import parse_checkers
from switchcheck.datasets import import_jsonl_dataset
from switchcheck.eligibility import check_dataset_eligibility
from switchcheck.experiments import evaluate_dataset
from switchcheck.replay import replay, replay_dry_run
from switchcheck.report import write_report
from switchcheck.store import initialize_database, list_runs
from switchcheck.task_types import TaskType, parse_task_type

app = typer.Typer(
    add_completion=False,
    help="Evaluate supported repeatable LLM tasks against predefined expectations.",
    no_args_is_help=True,
)
dataset_app = typer.Typer(help="Create and import labeled evaluation datasets.")
app.add_typer(dataset_app, name="dataset")


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
    """Evaluate supported repeatable LLM tasks; not arbitrary LLM quality."""


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


@dataset_app.command("import")
def import_dataset_command(
    name: Annotated[str, typer.Argument(help="Unique name for the dataset.")],
    source: Annotated[Path, typer.Argument(help="UTF-8 JSONL file containing labeled cases.")],
    description: Annotated[str | None, typer.Option(help="Optional dataset description.")] = None,
    task_type: Annotated[
        str | None,
        typer.Option(
            "--task-type",
            help="Default supported task type for every case in this import.",
        ),
    ] = None,
    path: Annotated[Path, typer.Option(help="Project directory to update.")] = Path("."),
) -> None:
    """Validate and import a labeled JSONL evaluation dataset."""
    try:
        parsed_task_type: TaskType | None = (
            parse_task_type(task_type) if task_type is not None else None
        )
        result = import_jsonl_dataset(
            path,
            name=name,
            source=source,
            description=description,
            task_type=parsed_task_type,
        )
    except ValueError as error:
        raise typer.BadParameter(str(error), param_hint="SOURCE") from error
    noun = "case" if result.case_count == 1 else "cases"
    typer.echo(
        f"Imported {result.case_count} {noun} into dataset {result.dataset.name} "
        f"({result.dataset.id})."
    )


@dataset_app.command("check")
def check_dataset_command(
    dataset: Annotated[str, typer.Argument(help="Dataset name or ID to validate.")],
    path: Annotated[Path, typer.Option(help="Project directory to inspect.")] = Path("."),
) -> None:
    """Check evaluation eligibility without making provider calls."""
    try:
        report = check_dataset_eligibility(path, identifier=dataset)
    except ValueError as error:
        raise typer.BadParameter(str(error), param_hint="DATASET") from error

    typer.echo(
        f"Dataset {report.dataset.name}: {report.eligible_count}/{report.case_count} "
        "cases eligible."
    )
    for issue in report.issues:
        location = f"case {issue.case_id}" if issue.case_id else "dataset"
        typer.echo(f"Unsupported evaluation task ({location}): {issue.reason}")
    if not report.eligible:
        raise typer.Exit(code=1)


@app.command("evaluate")
def evaluate_command(
    dataset: Annotated[str, typer.Option("--dataset", help="Dataset name or ID.")],
    model: Annotated[str, typer.Option("--model", help="Candidate LiteLLM model.")],
    schema: Annotated[
        Path | None,
        typer.Option(help="JSON Schema used by configured schema evaluators."),
    ] = None,
    numeric_tolerance: Annotated[
        float,
        typer.Option(min=0.0, help="Absolute tolerance for numeric evaluators."),
    ] = 0.0,
    path: Annotated[Path, typer.Option(help="Project directory to update.")] = Path("."),
) -> None:
    """Run an eligible labeled dataset against a candidate model."""
    try:
        schema_value = None
        if schema is not None:
            schema_value = json.loads(schema.read_text(encoding="utf-8"))
            if not isinstance(schema_value, dict):
                raise ValueError("JSON Schema root must be an object")
        summary = evaluate_dataset(
            path,
            dataset=dataset,
            target_model=model,
            schema=schema_value,
            numeric_tolerance=numeric_tolerance,
        )
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise typer.BadParameter(str(error), param_hint="--dataset") from error
    typer.echo(
        f"Experiment {summary.experiment_id}: {summary.passed_count}/{summary.case_count} "
        f"passed ({summary.pass_rate:.0%}), {summary.failed_count} failed, "
        f"{summary.review_count} review, {summary.error_count} errors."
    )


@app.command("replay")
def replay_command(
    model: Annotated[str, typer.Option("--model", help="Candidate LiteLLM model.")],
    tag: Annotated[str | None, typer.Option(help="Only replay this exact tag.")] = None,
    limit: Annotated[int, typer.Option(min=1, help="Maximum calls to select.")] = 20,
    concurrency: Annotated[int, typer.Option(min=1, help="Maximum provider calls in flight.")] = 1,
    dry_run: Annotated[
        bool, typer.Option(help="Show the selection without provider calls.")
    ] = False,
    checks: Annotated[
        list[str] | None,
        typer.Option(
            "--check",
            help="exact, contains:TEXT, regex:PATTERN, json-schema:FILE, or json-field:PATH.",
        ),
    ] = None,
    path: Annotated[Path, typer.Option(help="Project directory to inspect.")] = Path("."),
) -> None:
    """Replay recorded calls against a candidate model."""
    try:
        checkers = parse_checkers(checks or [], base_path=path)
    except ValueError as error:
        raise typer.BadParameter(str(error), param_hint="--check") from error
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
        checkers=checkers,
    )
    typer.echo(
        f"Replay {summary.replay_id}: {summary.completed_count} completed, "
        f"{summary.failed_count} provider failures, {summary.passed_count}/"
        f"{summary.selected_count} passed ({summary.pass_rate:.0%})."
    )


@app.command("report")
def report_command(
    replay_id: Annotated[str, typer.Option("--replay", help="Replay ID to render.")],
    output: Annotated[
        Path | None,
        typer.Option(help="Destination HTML file (defaults under .switchcheck/reports)."),
    ] = None,
    path: Annotated[Path, typer.Option(help="Project directory to inspect.")] = Path("."),
) -> None:
    """Create a self-contained HTML report for one replay."""
    try:
        destination = write_report(path, replay_id=replay_id, output=output)
    except ValueError as error:
        raise typer.BadParameter(str(error), param_hint="--replay") from error
    typer.echo(f"Wrote report to {destination}")
