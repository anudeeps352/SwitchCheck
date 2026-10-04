"""Tests for labeled experiment metrics and self-contained reports."""

from __future__ import annotations

import json
from pathlib import Path

from switchcheck.datasets import import_jsonl_dataset
from switchcheck.experiment_report import write_experiment_report
from switchcheck.experiments import evaluate_dataset
from switchcheck.metrics import calculate_metrics
from switchcheck.store import list_evaluation_cases, list_evaluation_results
from switchcheck.task_types import TaskType


def test_experiment_metrics_and_report_include_classification_failures(tmp_path: Path) -> None:
    source = tmp_path / "cases.jsonl"
    source.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "messages": [{"role": "user", "content": "first"}],
                        "expected": "billing",
                        "evaluators": ["exact"],
                    }
                ),
                json.dumps(
                    {
                        "messages": [{"role": "user", "content": "second"}],
                        "expected": "technical",
                        "evaluators": ["exact"],
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    imported = import_jsonl_dataset(
        tmp_path,
        name="labels-v1",
        source=source,
        task_type=TaskType.CLASSIFICATION,
    )

    def completion(**kwargs: object) -> dict[str, object]:
        del kwargs
        return {"choices": [{"message": {"content": "billing"}}]}

    summary = evaluate_dataset(
        tmp_path,
        dataset="labels-v1",
        target_model="fake/candidate",
        completion=completion,
    )
    cases = list_evaluation_cases(tmp_path, dataset_id=imported.dataset.id)
    results = list_evaluation_results(tmp_path, experiment_id=summary.experiment_id)
    metrics = calculate_metrics(cases, results)
    report = write_experiment_report(tmp_path, experiment_id=summary.experiment_id)
    content = report.read_text(encoding="utf-8")

    assert metrics.case_count == 2
    assert metrics.pass_rate == 0.5
    assert metrics.classification["value"].accuracy == 0.5
    assert "Classification metrics" in content
    assert "50%" in content
    assert "technical" in content
