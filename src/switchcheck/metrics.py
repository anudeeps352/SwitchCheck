"""Aggregate task-aware metrics from persisted labeled evaluation results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from switchcheck.evaluators import ClassificationMetrics, ClassificationMetricsEvaluator
from switchcheck.store import EvaluationCase, EvaluationResult
from switchcheck.task_types import TaskType


@dataclass(frozen=True)
class ExperimentMetrics:
    """Metrics that retain all cases, including review and technical errors."""

    case_count: int
    state_counts: dict[str, int]
    pass_rate: float
    field_accuracy: float | None
    tool_name_accuracy: float | None
    argument_accuracy: float | None
    classification: dict[str, ClassificationMetrics]


def calculate_metrics(
    cases: list[EvaluationCase], results: list[EvaluationResult]
) -> ExperimentMetrics:
    """Calculate applicable metrics without removing review or error cases."""
    case_by_id = {case.id: case for case in cases}
    state_counts = {state: 0 for state in ("PASS", "FAIL", "REVIEW", "ERROR")}
    field_passed = 0
    field_total = 0
    tool_passed = 0
    tool_total = 0
    argument_passed = 0
    argument_total = 0
    labels: dict[str, tuple[list[str], list[str]]] = {}

    for result in results:
        if result.state in state_counts:
            state_counts[result.state] += 1
        for verdict in result.verdict or []:
            details = verdict.get("details", {})
            for field in details.get("fields", []):
                field_total += 1
                field_passed += field.get("passed") is True
            if "tool_matches" in details:
                tool_total += 1
                tool_passed += details["tool_matches"] is True
            if "arguments_match" in details:
                argument_total += 1
                argument_passed += details["arguments_match"] is True

        case = case_by_id.get(result.case_id)
        if case is not None and case.task_type in {TaskType.CLASSIFICATION, TaskType.DECISION}:
            _collect_labels(labels, case.expected, _candidate_value(result))

    classification = {
        field: ClassificationMetricsEvaluator().evaluate(expected=expected, candidate=candidate)
        for field, (expected, candidate) in labels.items()
        if expected
    }
    case_count = len(results)
    return ExperimentMetrics(
        case_count=case_count,
        state_counts=state_counts,
        pass_rate=state_counts["PASS"] / case_count if case_count else 0.0,
        field_accuracy=field_passed / field_total if field_total else None,
        tool_name_accuracy=tool_passed / tool_total if tool_total else None,
        argument_accuracy=argument_passed / argument_total if argument_total else None,
        classification=classification,
    )


def _collect_labels(
    labels: dict[str, tuple[list[str], list[str]]], expected: Any, candidate: Any
) -> None:
    if isinstance(expected, dict) and isinstance(candidate, dict):
        for field, expected_value in expected.items():
            if field in candidate and _is_label(expected_value) and _is_label(candidate[field]):
                expected_labels, candidate_labels = labels.setdefault(field, ([], []))
                expected_labels.append(str(expected_value))
                candidate_labels.append(str(candidate[field]))
    elif _is_label(expected) and _is_label(candidate):
        expected_labels, candidate_labels = labels.setdefault("value", ([], []))
        expected_labels.append(str(expected))
        candidate_labels.append(str(candidate))


def _candidate_value(result: EvaluationResult) -> Any:
    return result.output_json if result.output_json is not None else result.output_text


def _is_label(value: Any) -> bool:
    return isinstance(value, (str, bool, int)) and not isinstance(value, float)
