"""Deterministic evaluators for supported Switchcheck task contracts."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

import jsonschema

from switchcheck.task_types import EvaluatorType


class CaseState(str, Enum):
    """The only terminal states for an evaluated case."""

    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"
    ERROR = "ERROR"


@dataclass(frozen=True)
class EvaluationVerdict:
    """Serializable evidence produced by one evaluator."""

    evaluator: EvaluatorType
    state: CaseState
    score: float
    reason: str
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Return the stable persistence/report representation."""
        return {
            "evaluator": self.evaluator.value,
            "state": self.state.value,
            "score": self.score,
            "reason": self.reason,
            "details": self.details,
        }


class CaseEvaluator(Protocol):
    """Protocol shared by deterministic per-case evaluators."""

    evaluator_type: EvaluatorType

    def evaluate(self, *, expected: Any, candidate: Any) -> EvaluationVerdict:
        """Evaluate one candidate against predefined expected evidence."""
        ...


@dataclass(frozen=True)
class ExactEvaluator:
    """Compare complete expected and candidate values without coercion."""

    evaluator_type = EvaluatorType.EXACT

    def evaluate(self, *, expected: Any, candidate: Any) -> EvaluationVerdict:
        passed = candidate == expected
        return _binary_verdict(
            self.evaluator_type,
            passed,
            "Candidate exactly matches the expected value."
            if passed
            else "Candidate does not exactly match the expected value.",
            {"expected": expected, "candidate": candidate},
        )


@dataclass(frozen=True)
class FieldEvaluator:
    """Compare configured dotted fields, with optional string normalization."""

    fields: tuple[str, ...] = ()
    normalize_strings: bool = False
    set_fields: frozenset[str] = frozenset()
    evaluator_type = EvaluatorType.FIELDS

    def evaluate(self, *, expected: Any, candidate: Any) -> EvaluationVerdict:
        try:
            expected_value = _json_value(expected)
            candidate_value = _json_value(candidate)
            fields = self.fields or _top_level_fields(expected_value)
            comparisons: list[dict[str, Any]] = []
            for path in fields:
                expected_field = _field(expected_value, path)
                candidate_field = _field(candidate_value, path)
                passed = self._equal(path, expected_field, candidate_field)
                comparisons.append(
                    {
                        "field": path,
                        "passed": passed,
                        "expected": expected_field,
                        "candidate": candidate_field,
                    }
                )
        except (TypeError, ValueError) as error:
            return _error_verdict(self.evaluator_type, str(error))

        passed_count = sum(item["passed"] is True for item in comparisons)
        passed = passed_count == len(comparisons)
        return EvaluationVerdict(
            evaluator=self.evaluator_type,
            state=CaseState.PASS if passed else CaseState.FAIL,
            score=passed_count / len(comparisons),
            reason=(
                "All configured fields match."
                if passed
                else f"{len(comparisons) - passed_count} configured field(s) differ."
            ),
            details={"fields": comparisons},
        )

    def _equal(self, path: str, expected: Any, candidate: Any) -> bool:
        if path in self.set_fields:
            if not isinstance(expected, list) or not isinstance(candidate, list):
                return False
            return {_stable_value(item) for item in expected} == {
                _stable_value(item) for item in candidate
            }
        if self.normalize_strings and isinstance(expected, str) and isinstance(candidate, str):
            return _normalize_string(expected) == _normalize_string(candidate)
        return expected == candidate


@dataclass(frozen=True)
class SchemaEvaluator:
    """Validate a candidate JSON value against a supplied JSON Schema."""

    schema: dict[str, Any]
    evaluator_type = EvaluatorType.SCHEMA

    def evaluate(self, *, expected: Any, candidate: Any) -> EvaluationVerdict:
        del expected
        try:
            value = _json_value(candidate)
            jsonschema.Draft202012Validator.check_schema(self.schema)
            jsonschema.validate(instance=value, schema=self.schema)
        except (TypeError, ValueError, jsonschema.SchemaError) as error:
            return _error_verdict(self.evaluator_type, str(error))
        except jsonschema.ValidationError as error:
            return _binary_verdict(
                self.evaluator_type,
                False,
                f"Candidate does not satisfy the JSON Schema: {error.message}",
                {"path": list(error.absolute_path)},
            )
        return _binary_verdict(
            self.evaluator_type,
            True,
            "Candidate satisfies the configured JSON Schema.",
        )


@dataclass(frozen=True)
class NumericEvaluator:
    """Compare a complete number or configured numeric fields with tolerance."""

    fields: tuple[str, ...] = ()
    absolute_tolerance: float = 0.0
    evaluator_type = EvaluatorType.NUMERIC

    def __post_init__(self) -> None:
        if self.absolute_tolerance < 0:
            raise ValueError("absolute_tolerance must be non-negative")

    def evaluate(self, *, expected: Any, candidate: Any) -> EvaluationVerdict:
        try:
            expected_value = _json_value(expected) if self.fields else expected
            candidate_value = _json_value(candidate) if self.fields else candidate
            paths = self.fields or ("$",)
            comparisons: list[dict[str, Any]] = []
            for path in paths:
                expected_number = expected_value if path == "$" else _field(expected_value, path)
                candidate_number = candidate_value if path == "$" else _field(candidate_value, path)
                if isinstance(expected_number, bool) or not isinstance(
                    expected_number, (int, float)
                ):
                    raise TypeError(f"expected numeric field {path!r} is not a number")
                if isinstance(candidate_number, bool) or not isinstance(
                    candidate_number, (int, float)
                ):
                    raise TypeError(f"candidate numeric field {path!r} is not a number")
                passed = math.isclose(
                    float(expected_number),
                    float(candidate_number),
                    rel_tol=0.0,
                    abs_tol=self.absolute_tolerance,
                )
                comparisons.append(
                    {
                        "field": path,
                        "passed": passed,
                        "expected": expected_number,
                        "candidate": candidate_number,
                        "absolute_tolerance": self.absolute_tolerance,
                    }
                )
        except (TypeError, ValueError) as error:
            return _error_verdict(self.evaluator_type, str(error))

        passed_count = sum(item["passed"] is True for item in comparisons)
        return EvaluationVerdict(
            evaluator=self.evaluator_type,
            state=CaseState.PASS if passed_count == len(comparisons) else CaseState.FAIL,
            score=passed_count / len(comparisons),
            reason=f"{passed_count}/{len(comparisons)} numeric value(s) are within tolerance.",
            details={"fields": comparisons},
        )


@dataclass(frozen=True)
class PatternEvaluator:
    """Check explicit required and prohibited regular-expression constraints."""

    required: tuple[str, ...] = ()
    prohibited: tuple[str, ...] = ()
    flags: int = re.IGNORECASE
    evaluator_type = EvaluatorType.PATTERN

    def evaluate(self, *, expected: Any, candidate: Any) -> EvaluationVerdict:
        del expected
        if not isinstance(candidate, str):
            return _error_verdict(self.evaluator_type, "candidate must be text")
        try:
            missing = [
                pattern
                for pattern in self.required
                if re.search(pattern, candidate, self.flags) is None
            ]
            present = [
                pattern for pattern in self.prohibited if re.search(pattern, candidate, self.flags)
            ]
        except re.error as error:
            return _error_verdict(self.evaluator_type, f"invalid pattern: {error}")
        passed = not missing and not present
        return _binary_verdict(
            self.evaluator_type,
            passed,
            "All pattern constraints are satisfied."
            if passed
            else "One or more pattern constraints failed.",
            {"missing_required": missing, "present_prohibited": present},
        )


@dataclass(frozen=True)
class ToolCallEvaluator:
    """Compare one proposed tool call and optionally validate its arguments."""

    argument_schema: dict[str, Any] | None = None
    evaluator_type = EvaluatorType.TOOL_CALL

    def evaluate(self, *, expected: Any, candidate: Any) -> EvaluationVerdict:
        try:
            expected_call = _tool_call(expected, "expected")
            candidate_call = _tool_call(candidate, "candidate")
            if self.argument_schema is not None:
                jsonschema.validate(candidate_call["arguments"], self.argument_schema)
        except jsonschema.ValidationError as error:
            return _binary_verdict(
                self.evaluator_type,
                False,
                f"Tool arguments do not satisfy the configured schema: {error.message}",
            )
        except (TypeError, ValueError, jsonschema.SchemaError) as error:
            return _error_verdict(self.evaluator_type, str(error))

        tool_matches = expected_call["tool"] == candidate_call["tool"]
        arguments_match = expected_call["arguments"] == candidate_call["arguments"]
        passed = tool_matches and arguments_match
        return _binary_verdict(
            self.evaluator_type,
            passed,
            "Tool name and arguments match." if passed else "Tool name or arguments do not match.",
            {"tool_matches": tool_matches, "arguments_match": arguments_match},
        )


@dataclass(frozen=True)
class RequiredFactsEvaluator:
    """Check explicitly supplied required and prohibited facts in text."""

    required_fields: tuple[str, ...] = ()
    prohibited: tuple[str | int | float | bool, ...] = ()
    evaluator_type = EvaluatorType.REQUIRED_FACTS

    def evaluate(self, *, expected: Any, candidate: Any) -> EvaluationVerdict:
        if not isinstance(candidate, str):
            return _error_verdict(self.evaluator_type, "candidate must be text")
        try:
            if self.required_fields:
                required = [(_field(expected, path), path) for path in self.required_fields]
            elif isinstance(expected, dict) and expected:
                required = [(value, key) for key, value in expected.items()]
            else:
                raise TypeError(
                    "required facts need a non-empty expected object or configured fields"
                )
            missing = [path for value, path in required if not _contains_fact(candidate, value)]
            prohibited_present = [
                value for value in self.prohibited if _contains_fact(candidate, value)
            ]
        except (TypeError, ValueError) as error:
            return _error_verdict(self.evaluator_type, str(error))

        passed = not missing and not prohibited_present
        return _binary_verdict(
            self.evaluator_type,
            passed,
            "All required facts are present and prohibited facts are absent."
            if passed
            else "Required or prohibited fact checks failed.",
            {"missing_required": missing, "present_prohibited": prohibited_present},
        )


@dataclass(frozen=True)
class ClassificationMetrics:
    """Aggregate metrics for labeled classification or decision outputs."""

    accuracy: float
    per_label: dict[str, dict[str, float]]
    confusion_matrix: dict[str, dict[str, int]]
    case_count: int


class ClassificationMetricsEvaluator:
    """Calculate accuracy, precision, recall, F1, and a confusion matrix."""

    evaluator_type = EvaluatorType.CLASSIFICATION_METRICS

    def evaluate(
        self, *, expected: Sequence[str], candidate: Sequence[str]
    ) -> ClassificationMetrics:
        if len(expected) != len(candidate):
            raise ValueError("expected and candidate label sequences must have equal length")
        if not expected:
            raise ValueError("classification metrics require at least one case")
        labels = sorted(set(expected) | set(candidate))
        confusion = {label: {predicted: 0 for predicted in labels} for label in labels}
        for truth, predicted in zip(expected, candidate, strict=True):
            confusion[truth][predicted] += 1

        per_label: dict[str, dict[str, float]] = {}
        for label in labels:
            true_positive = confusion[label][label]
            false_positive = sum(confusion[truth][label] for truth in labels if truth != label)
            false_negative = sum(
                confusion[label][predicted] for predicted in labels if predicted != label
            )
            precision = _safe_ratio(true_positive, true_positive + false_positive)
            recall = _safe_ratio(true_positive, true_positive + false_negative)
            f1 = _safe_ratio(2 * precision * recall, precision + recall)
            per_label[label] = {"precision": precision, "recall": recall, "f1": f1}

        correct = sum(
            truth == predicted for truth, predicted in zip(expected, candidate, strict=True)
        )
        return ClassificationMetrics(
            accuracy=correct / len(expected),
            per_label=per_label,
            confusion_matrix=confusion,
            case_count=len(expected),
        )


CASE_EVALUATOR_REGISTRY: dict[EvaluatorType, type[CaseEvaluator]] = {
    EvaluatorType.EXACT: ExactEvaluator,
    EvaluatorType.FIELDS: FieldEvaluator,
    EvaluatorType.SCHEMA: SchemaEvaluator,
    EvaluatorType.NUMERIC: NumericEvaluator,
    EvaluatorType.PATTERN: PatternEvaluator,
    EvaluatorType.TOOL_CALL: ToolCallEvaluator,
    EvaluatorType.REQUIRED_FACTS: RequiredFactsEvaluator,
}


def combine_verdicts(verdicts: Sequence[EvaluationVerdict]) -> CaseState:
    """Combine required evaluator evidence without hiding reviews or errors."""
    if not verdicts:
        raise ValueError("at least one evaluator verdict is required")
    states = {verdict.state for verdict in verdicts}
    if CaseState.ERROR in states:
        return CaseState.ERROR
    if CaseState.FAIL in states:
        return CaseState.FAIL
    if CaseState.REVIEW in states:
        return CaseState.REVIEW
    return CaseState.PASS


def _binary_verdict(
    evaluator: EvaluatorType,
    passed: bool,
    reason: str,
    details: dict[str, Any] | None = None,
) -> EvaluationVerdict:
    return EvaluationVerdict(
        evaluator=evaluator,
        state=CaseState.PASS if passed else CaseState.FAIL,
        score=1.0 if passed else 0.0,
        reason=reason,
        details=details or {},
    )


def _error_verdict(evaluator: EvaluatorType, reason: str) -> EvaluationVerdict:
    return EvaluationVerdict(
        evaluator=evaluator,
        state=CaseState.ERROR,
        score=0.0,
        reason=reason,
    )


def _json_value(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError as error:
            raise ValueError(f"value is not valid JSON: {error.msg}") from error
    return value


def _top_level_fields(value: Any) -> tuple[str, ...]:
    if not isinstance(value, dict) or not value:
        raise TypeError(
            "field evaluation requires a non-empty expected object or configured fields"
        )
    return tuple(value)


def _field(value: Any, path: str) -> Any:
    current = value
    for segment in path.split("."):
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        elif isinstance(current, list) and segment.isdigit() and int(segment) < len(current):
            current = current[int(segment)]
        else:
            raise ValueError(f"field {path!r} is missing")
    return current


def _normalize_string(value: str) -> str:
    return " ".join(value.casefold().split())


def _stable_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _tool_call(value: Any, label: str) -> dict[str, Any]:
    parsed = _json_value(value)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("tool"), str):
        raise TypeError(f"{label} tool call must be an object with a string tool")
    arguments = parsed.get("arguments", {})
    if not isinstance(arguments, dict):
        raise TypeError(f"{label} tool arguments must be an object")
    return {"tool": parsed["tool"], "arguments": arguments}


def _safe_ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _contains_fact(text: str, value: Any) -> bool:
    if isinstance(value, bool):
        return re.search(rf"\b{str(value).lower()}\b", text, re.IGNORECASE) is not None
    if isinstance(value, (int, float)):
        return re.search(rf"(?<![\d.]){re.escape(str(value))}(?![\d.])", text) is not None
    if isinstance(value, str):
        return _normalize_string(value) in _normalize_string(text)
    raise TypeError(f"fact value {value!r} is not a supported scalar")
