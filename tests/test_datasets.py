"""Tests for importing human-reviewed evaluation datasets."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from switchcheck.datasets import import_jsonl_dataset
from switchcheck.store import database_path, list_evaluation_cases
from switchcheck.task_types import TaskType


def test_import_jsonl_dataset_persists_labeled_cases(tmp_path: Path) -> None:
    """A valid JSONL file becomes a named dataset with ordered cases."""
    source = tmp_path / "invoices.jsonl"
    records = [
        {
            "task_type": "extraction",
            "messages": [{"role": "user", "content": "Invoice 1"}],
            "expected": {"invoice_id": "1", "total": 12.5},
            "evaluators": ["schema", "fields", "numeric"],
            "criteria": [{"id": "all_fields", "requirement": "Must extract every expected field."}],
            "metadata": {"difficulty": "easy"},
        },
        {
            "task_type": "extraction",
            "messages": [{"role": "user", "content": "Invoice 2"}],
            "expected": {"invoice_id": "2", "total": 20},
        },
    ]
    source.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    result = import_jsonl_dataset(
        tmp_path,
        name="invoice-v1",
        source=source,
        description="Reviewed invoice cases",
    )

    assert result.case_count == 2
    assert result.dataset.name == "invoice-v1"
    cases = list_evaluation_cases(tmp_path, dataset_id=result.dataset.id)
    assert [case.expected for case in cases] == [record["expected"] for record in records]
    assert cases[0].criteria[0].id == "all_fields"
    assert cases[0].criteria[0].requirement == "Must extract every expected field."
    assert cases[1].metadata == {}
    assert cases[0].task_type is not None
    assert cases[0].task_type.value == "extraction"
    assert [evaluator.value for evaluator in cases[0].evaluators] == [
        "schema",
        "fields",
        "numeric",
    ]


def test_import_jsonl_dataset_validates_every_line_before_writing(tmp_path: Path) -> None:
    """One invalid case rejects the file without creating a project database."""
    source = tmp_path / "invalid.jsonl"
    source.write_text(
        '{"task_type":"classification","messages":[{"role":"user","content":"valid"}],"expected":"ok"}\n'
        '{"task_type":"classification","messages":[],"expected":"invalid"}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="line 2"):
        import_jsonl_dataset(tmp_path, name="invalid", source=source)

    assert not database_path(tmp_path).exists()


def test_import_jsonl_dataset_reports_invalid_json_line(tmp_path: Path) -> None:
    """Syntax errors identify the offending JSONL line."""
    source = tmp_path / "invalid.jsonl"
    source.write_text('{"messages": ', encoding="utf-8")

    with pytest.raises(ValueError, match="line 1"):
        import_jsonl_dataset(tmp_path, name="invalid", source=source)


def test_import_rejects_unsupported_task_type(tmp_path: Path) -> None:
    source = tmp_path / "unsupported.jsonl"
    source.write_text(
        '{"task_type":"creative_writing","messages":[{"role":"user","content":"Poem"}],"expected":"nice"}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported task_type"):
        import_jsonl_dataset(tmp_path, name="unsupported", source=source)


def test_import_rejects_evaluator_not_permitted_for_task(tmp_path: Path) -> None:
    source = tmp_path / "invalid-evaluator.jsonl"
    source.write_text(
        '{"task_type":"classification","messages":[{"role":"user","content":"Classify"}],'
        '"expected":"billing","evaluators":["criteria_judge"]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="not permitted"):
        import_jsonl_dataset(tmp_path, name="invalid-evaluator", source=source)


def test_import_applies_dataset_task_type_default(tmp_path: Path) -> None:
    source = tmp_path / "labels.jsonl"
    source.write_text(
        '{"messages":[{"role":"user","content":"Classify this"}],"expected":"billing"}\n',
        encoding="utf-8",
    )

    result = import_jsonl_dataset(
        tmp_path,
        name="labels-v1",
        source=source,
        task_type=TaskType.CLASSIFICATION,
    )
    case = list_evaluation_cases(tmp_path, dataset_id=result.dataset.id)[0]

    assert case.task_type is TaskType.CLASSIFICATION


def test_import_rejects_case_that_conflicts_with_dataset_task_type(tmp_path: Path) -> None:
    source = tmp_path / "mixed.jsonl"
    source.write_text(
        '{"task_type":"decision","messages":[{"role":"user","content":"Route this"}],'
        '"expected":"fraud_team"}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="conflicts with import default"):
        import_jsonl_dataset(
            tmp_path,
            name="mixed-v1",
            source=source,
            task_type=TaskType.CLASSIFICATION,
        )


def test_import_support_response_with_context_and_structured_criteria(tmp_path: Path) -> None:
    source = tmp_path / "support.jsonl"
    source.write_text(
        json.dumps(
            {
                "task_type": "support_response",
                "messages": [{"role": "user", "content": "Can I return this after 20 days?"}],
                "context": "Returns are allowed within 30 days.",
                "criteria": [
                    {"id": "eligibility", "requirement": "Must state that the return is allowed."}
                ],
                "evaluators": ["criteria_judge"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = import_jsonl_dataset(tmp_path, name="support-v1", source=source)
    case = list_evaluation_cases(tmp_path, dataset_id=result.dataset.id)[0]

    assert case.has_expected is False
    assert case.has_context is True
    assert case.context == "Returns are allowed within 30 days."
    assert case.contract_version == 1


@pytest.mark.parametrize(
    ("record", "message"),
    [
        (
            {
                "task_type": "summarization",
                "messages": [{"role": "user", "content": "Summarize this."}],
                "criteria": [{"id": "fact", "requirement": "Must preserve fact X."}],
            },
            "context is required",
        ),
        (
            {
                "task_type": "rubric_free_text",
                "messages": [{"role": "user", "content": "Explain tokens."}],
                "criteria": [{"id": "quality", "requirement": "Good answer."}],
            },
            "is vague",
        ),
        (
            {
                "task_type": "tool_selection",
                "messages": [{"role": "user", "content": "Weather tomorrow?"}],
                "expected": {"name": "get_weather"},
            },
            "string tool",
        ),
        (
            {
                "task_type": "classification",
                "messages": [
                    {"role": "user", "content": "Classify this."},
                    {"role": "assistant", "content": "billing"},
                ],
                "expected": "billing",
            },
            "single-turn cases only allow",
        ),
    ],
)
def test_import_rejects_ineligible_case_contracts(
    tmp_path: Path, record: dict[str, object], message: str
) -> None:
    source = tmp_path / "ineligible.jsonl"
    source.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        import_jsonl_dataset(tmp_path, name="ineligible", source=source)
