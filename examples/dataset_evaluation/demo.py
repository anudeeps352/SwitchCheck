"""Run a complete labeled evaluation locally without credentials or network."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import uuid4

from switchcheck.datasets import import_jsonl_dataset
from switchcheck.experiment_report import write_experiment_report
from switchcheck.experiments import ExperimentSummary, evaluate_dataset
from switchcheck.task_types import TaskType


def run_demo(project_directory: Path) -> tuple[ExperimentSummary, Path]:
    """Import cases, run a fake candidate, and write an experiment report."""
    records = [
        {
            "messages": [
                {
                    "role": "user",
                    "content": "Invoice INV-1001 has a total of 5400 INR.",
                }
            ],
            "expected": {"invoice_number": "INV-1001", "total": 5400},
            "evaluators": ["fields", "numeric"],
        },
        {
            "messages": [
                {
                    "role": "user",
                    "content": "Invoice INV-1002 has a total of 7000 INR.",
                }
            ],
            "expected": {"invoice_number": "INV-1002", "total": 7000},
            "evaluators": ["fields", "numeric"],
        },
    ]
    with TemporaryDirectory() as temporary:
        source = Path(temporary) / "invoice-cases.jsonl"
        source.write_text(
            "\n".join(json.dumps(record) for record in records) + "\n",
            encoding="utf-8",
        )
        dataset_name = f"invoice-demo-{uuid4().hex[:8]}"
        import_jsonl_dataset(
            project_directory,
            name=dataset_name,
            source=source,
            task_type=TaskType.EXTRACTION,
        )

    summary = evaluate_dataset(
        project_directory,
        dataset=dataset_name,
        target_model="fake/invoice-candidate",
        completion=_fake_completion,
    )
    report = write_experiment_report(project_directory, experiment_id=summary.experiment_id)
    return summary, report


def _fake_completion(**kwargs: Any) -> dict[str, Any]:
    prompt = kwargs["messages"][-1]["content"]
    content = (
        '{"invoice_number":"INV-1001","total":5400}'
        if "INV-1001" in prompt
        else '{"invoice_number":"INV-1002","total":7100}'
    )
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 8},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, default=Path("."))
    args = parser.parse_args()
    summary, report = run_demo(args.project)
    print(
        f"Experiment {summary.experiment_id}: {summary.passed_count}/"
        f"{summary.case_count} passed; report {report}"
    )


if __name__ == "__main__":
    main()
