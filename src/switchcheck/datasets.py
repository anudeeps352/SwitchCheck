"""Import and validate human-reviewed evaluation datasets."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from switchcheck.contracts import (
    CASE_CONTRACT_VERSION,
    Criterion,
    parse_criteria,
    parse_messages,
    validate_case_contract,
)
from switchcheck.store import Dataset, create_dataset, create_evaluation_case
from switchcheck.task_types import EvaluatorType, TaskType, parse_evaluators, parse_task_type


@dataclass(frozen=True)
class DatasetImport:
    """Summary of one completed dataset import."""

    dataset: Dataset
    case_count: int


@dataclass(frozen=True)
class _CaseInput:
    contract_version: int
    task_type: TaskType
    messages: list[dict[str, Any]]
    has_expected: bool
    expected: Any
    has_reference: bool
    reference: Any
    has_context: bool
    context: Any
    criteria: tuple[Criterion, ...]
    metadata: dict[str, Any]
    source_run_id: str | None
    evaluators: tuple[EvaluatorType, ...]


def import_jsonl_dataset(
    project_directory: Path,
    *,
    name: str,
    source: Path,
    description: str | None = None,
) -> DatasetImport:
    """Validate a JSONL file completely, then persist it as a named dataset."""
    cases = _read_cases(source)
    dataset = create_dataset(project_directory, name=name, description=description)
    for case in cases:
        create_evaluation_case(
            project_directory,
            dataset_id=dataset.id,
            contract_version=case.contract_version,
            task_type=case.task_type,
            messages=case.messages,
            has_expected=case.has_expected,
            expected=case.expected,
            has_reference=case.has_reference,
            reference=case.reference,
            has_context=case.has_context,
            context=case.context,
            criteria=case.criteria,
            metadata=case.metadata,
            source_run_id=case.source_run_id,
            evaluators=case.evaluators,
        )
    return DatasetImport(dataset=dataset, case_count=len(cases))


def _read_cases(source: Path) -> list[_CaseInput]:
    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ValueError(f"Cannot read dataset {source}: {error}") from error

    cases: list[_CaseInput] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSON on line {line_number}: {error.msg}") from error
        try:
            cases.append(_validate_case(value))
        except ValueError as error:
            raise ValueError(f"Invalid evaluation case on line {line_number}: {error}") from error

    if not cases:
        raise ValueError("Dataset must contain at least one evaluation case.")
    return cases


def _validate_case(value: Any) -> _CaseInput:
    if not isinstance(value, dict):
        raise ValueError("case must be a JSON object")
    contract_version = value.get("contract_version", CASE_CONTRACT_VERSION)
    if contract_version != CASE_CONTRACT_VERSION:
        raise ValueError(
            f"unsupported contract_version {contract_version!r}; expected {CASE_CONTRACT_VERSION}"
        )
    task_type = parse_task_type(value.get("task_type"))
    evaluators = parse_evaluators(task_type, value.get("evaluators"))
    messages = parse_messages(value.get("messages"))
    criteria = parse_criteria(value.get("criteria"))
    has_expected = "expected" in value
    expected = value.get("expected")
    has_reference = "reference" in value
    reference = value.get("reference")
    has_context = "context" in value
    context = value.get("context")
    metadata = value.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be an object")
    source_run_id = value.get("source_run_id")
    if source_run_id is not None and not isinstance(source_run_id, str):
        raise ValueError("source_run_id must be a string or null")

    validate_case_contract(
        task_type=task_type,
        messages=messages,
        has_expected=has_expected,
        expected=expected,
        has_reference=has_reference,
        reference=reference,
        has_context=has_context,
        context=context,
        criteria=criteria,
        evaluators=evaluators,
    )

    return _CaseInput(
        contract_version=contract_version,
        task_type=task_type,
        messages=messages,
        has_expected=has_expected,
        expected=expected,
        has_reference=has_reference,
        reference=reference,
        has_context=has_context,
        context=context,
        criteria=criteria,
        metadata=dict(metadata),
        source_run_id=source_run_id,
        evaluators=evaluators,
    )
