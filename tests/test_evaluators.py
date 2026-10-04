"""Tests for deterministic evaluator behavior and aggregate metrics."""

from __future__ import annotations

import pytest

from switchcheck.evaluators import (
    CaseState,
    ClassificationMetricsEvaluator,
    EvaluationVerdict,
    ExactEvaluator,
    FieldEvaluator,
    NumericEvaluator,
    PatternEvaluator,
    RequiredFactsEvaluator,
    SchemaEvaluator,
    ToolCallEvaluator,
    combine_verdicts,
)
from switchcheck.task_types import EvaluatorType


def test_exact_and_field_evaluators_return_explainable_verdicts() -> None:
    exact = ExactEvaluator().evaluate(expected="billing", candidate="billing")
    fields = FieldEvaluator(
        fields=("customer.name", "skills"),
        normalize_strings=True,
        set_fields=frozenset({"skills"}),
    ).evaluate(
        expected={"customer": {"name": "Anudeep"}, "skills": ["Java", "Spring"]},
        candidate='{"customer":{"name":"  ANUDEEP "},"skills":["Spring","Java"]}',
    )

    assert exact.state is CaseState.PASS
    assert fields.state is CaseState.PASS
    assert fields.score == 1.0
    assert len(fields.details["fields"]) == 2


def test_schema_and_numeric_evaluators_cover_failure_and_tolerance() -> None:
    schema = SchemaEvaluator(
        {"type": "object", "required": ["total"], "properties": {"total": {"type": "number"}}}
    )
    invalid = schema.evaluate(expected=None, candidate={"total": "ten"})
    numeric = NumericEvaluator(fields=("total",), absolute_tolerance=0.1).evaluate(
        expected={"total": 10.0}, candidate={"total": 10.05}
    )

    assert invalid.state is CaseState.FAIL
    assert "JSON Schema" in invalid.reason
    assert numeric.state is CaseState.PASS


def test_pattern_and_tool_call_evaluators_apply_explicit_constraints() -> None:
    pattern = PatternEvaluator(required=(r"30\s+days",), prohibited=(r"restocking fee",)).evaluate(
        expected=None,
        candidate="You can return the product within 30 days.",
    )
    tool = ToolCallEvaluator(
        argument_schema={
            "type": "object",
            "required": ["order_id"],
            "properties": {"order_id": {"type": "string"}},
        }
    ).evaluate(
        expected={"tool": "cancel_order", "arguments": {"order_id": "123"}},
        candidate='{"tool":"cancel_order","arguments":{"order_id":"123"}}',
    )

    assert pattern.state is CaseState.PASS
    assert tool.state is CaseState.PASS


def test_required_facts_checks_supplied_values_not_world_knowledge() -> None:
    evaluator = RequiredFactsEvaluator(
        required_fields=("return_window_days",),
        prohibited=("60 days",),
    )

    verdict = evaluator.evaluate(
        expected={"return_window_days": 30},
        candidate="Products may be returned within 30 days of purchase.",
    )

    assert verdict.state is CaseState.PASS


def test_classification_metrics_include_each_label_and_confusion_counts() -> None:
    metrics = ClassificationMetricsEvaluator().evaluate(
        expected=["billing", "billing", "technical"],
        candidate=["billing", "technical", "technical"],
    )

    assert metrics.accuracy == pytest.approx(2 / 3)
    assert metrics.per_label["billing"]["precision"] == 1.0
    assert metrics.per_label["billing"]["recall"] == 0.5
    assert metrics.confusion_matrix["billing"]["technical"] == 1


def test_combine_verdicts_never_counts_review_or_error_as_pass() -> None:
    def verdict(state: CaseState) -> EvaluationVerdict:
        return EvaluationVerdict(
            evaluator=EvaluatorType.EXACT,
            state=state,
            score=0.0,
            reason=state.value,
        )

    assert combine_verdicts([verdict(CaseState.PASS)]) is CaseState.PASS
    assert (
        combine_verdicts([verdict(CaseState.PASS), verdict(CaseState.REVIEW)]) is CaseState.REVIEW
    )
    assert combine_verdicts([verdict(CaseState.REVIEW), verdict(CaseState.FAIL)]) is CaseState.FAIL
    assert combine_verdicts([verdict(CaseState.FAIL), verdict(CaseState.ERROR)]) is CaseState.ERROR


def test_malformed_candidate_is_an_error_not_silently_removed() -> None:
    verdict = SchemaEvaluator({"type": "object"}).evaluate(expected=None, candidate="not-json")

    assert verdict.state is CaseState.ERROR
    assert verdict.score == 0.0
