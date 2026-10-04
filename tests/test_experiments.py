"""Tests for running labeled datasets against a candidate model."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from switchcheck.datasets import import_jsonl_dataset
from switchcheck.experiments import evaluate_dataset
from switchcheck.store import list_evaluation_results
from switchcheck.task_types import TaskType


def _response(content: str) -> dict[str, object]:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 4, "completion_tokens": 2},
    }


def test_evaluate_dataset_persists_pass_fail_and_error_states(tmp_path: Path) -> None:
    source = tmp_path / "cases.jsonl"
    records = [
        {
            "messages": [{"role": "user", "content": "pass"}],
            "expected": {"label": "billing"},
            "evaluators": ["exact"],
        },
        {
            "messages": [{"role": "user", "content": "fail"}],
            "expected": {"label": "billing"},
            "evaluators": ["fields"],
        },
        {
            "messages": [{"role": "user", "content": "error"}],
            "expected": {"label": "billing"},
            "evaluators": ["exact"],
        },
    ]
    source.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )
    imported = import_jsonl_dataset(
        tmp_path,
        name="labels-v1",
        source=source,
        task_type=TaskType.CLASSIFICATION,
    )

    def completion(**kwargs: object) -> dict[str, object]:
        content = kwargs["messages"][0]["content"]  # type: ignore[index]
        if content == "error":
            raise ConnectionError("offline failure")
        if content == "pass":
            return _response('{"label":"billing"}')
        return _response('{"label":"technical"}')

    summary = evaluate_dataset(
        tmp_path,
        dataset=imported.dataset.name,
        target_model="fake/candidate",
        completion=completion,
    )
    results = list_evaluation_results(tmp_path, experiment_id=summary.experiment_id)

    assert summary.case_count == 3
    assert summary.passed_count == 1
    assert summary.failed_count == 1
    assert summary.error_count == 1
    assert {result.state for result in results} == {"ERROR", "FAIL", "PASS"}


def test_evaluate_rejects_incomplete_evaluator_setup_before_provider_call(
    tmp_path: Path,
) -> None:
    source = tmp_path / "cases.jsonl"
    source.write_text(
        '{"messages":[{"role":"user","content":"Extract"}],'
        '"expected":{"total":10},"evaluators":["schema"]}\n',
        encoding="utf-8",
    )
    import_jsonl_dataset(
        tmp_path,
        name="extract-v1",
        source=source,
        task_type=TaskType.EXTRACTION,
    )
    called = False

    def completion(**_: object) -> dict[str, object]:
        nonlocal called
        called = True
        return _response('{"total":10}')

    with pytest.raises(ValueError, match="requires --schema"):
        evaluate_dataset(
            tmp_path,
            dataset="extract-v1",
            target_model="fake/candidate",
            completion=completion,
        )

    assert called is False
