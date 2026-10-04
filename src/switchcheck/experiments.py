"""Run eligible labeled datasets against a candidate model."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

import jsonschema

from switchcheck.client import Completion, _load_litellm_completion, _response_fields
from switchcheck.eligibility import check_dataset_eligibility
from switchcheck.evaluators import (
    CaseEvaluator,
    CaseState,
    ExactEvaluator,
    FieldEvaluator,
    NumericEvaluator,
    RequiredFactsEvaluator,
    SchemaEvaluator,
    ToolCallEvaluator,
    combine_verdicts,
)
from switchcheck.store import (
    EvaluationCase,
    EvaluationResult,
    create_evaluation_result,
    create_experiment,
    list_evaluation_cases,
    update_evaluation_result,
)
from switchcheck.task_types import EvaluatorType


@dataclass(frozen=True)
class ExperimentSummary:
    """Aggregate terminal states for one persisted dataset experiment."""

    experiment_id: str
    case_count: int
    passed_count: int
    failed_count: int
    review_count: int
    error_count: int

    @property
    def pass_rate(self) -> float:
        return self.passed_count / self.case_count if self.case_count else 0.0


def evaluate_dataset(
    project_directory: Path,
    *,
    dataset: str,
    target_model: str,
    schema: dict[str, Any] | None = None,
    numeric_tolerance: float = 0.0,
    params: dict[str, Any] | None = None,
    completion: Completion | None = None,
) -> ExperimentSummary:
    """Evaluate every eligible case and retain every terminal result."""
    eligibility = check_dataset_eligibility(project_directory, identifier=dataset)
    if not eligibility.eligible:
        reasons = "; ".join(issue.reason for issue in eligibility.issues)
        raise ValueError(f"Dataset is not eligible: {reasons}")
    cases = list_evaluation_cases(project_directory, dataset_id=eligibility.dataset.id)
    if schema is not None:
        jsonschema.Draft202012Validator.check_schema(schema)
    evaluators = {
        case.id: _case_evaluators(case, schema=schema, numeric_tolerance=numeric_tolerance)
        for case in cases
    }
    active_params = params or {}
    experiment_id = create_experiment(
        project_directory,
        dataset_id=eligibility.dataset.id,
        target_model=target_model,
        params=active_params,
        evaluator_config={
            "schema": schema,
            "numeric_tolerance": numeric_tolerance,
        },
    )
    pending = [
        (
            case,
            create_evaluation_result(
                project_directory, experiment_id=experiment_id, case_id=case.id
            ),
        )
        for case in cases
    ]
    provider_completion = completion or _load_litellm_completion()
    results = [
        _evaluate_one(
            project_directory,
            case=case,
            result=result,
            target_model=target_model,
            params=active_params,
            completion=provider_completion,
            evaluators=evaluators[case.id],
        )
        for case, result in pending
    ]
    return _summary(experiment_id, results)


def _case_evaluators(
    case: EvaluationCase,
    *,
    schema: dict[str, Any] | None,
    numeric_tolerance: float,
) -> list[CaseEvaluator]:
    if not case.evaluators:
        raise ValueError(f"Case {case.id} has no configured evaluators")
    evaluators: list[CaseEvaluator] = []
    for evaluator_type in case.evaluators:
        if evaluator_type is EvaluatorType.EXACT:
            evaluators.append(ExactEvaluator())
        elif evaluator_type is EvaluatorType.FIELDS:
            evaluators.append(FieldEvaluator())
        elif evaluator_type is EvaluatorType.SCHEMA:
            if schema is None:
                raise ValueError("SchemaEvaluator requires --schema")
            evaluators.append(SchemaEvaluator(schema))
        elif evaluator_type is EvaluatorType.NUMERIC:
            fields = _numeric_fields(case.expected)
            if isinstance(case.expected, dict) and not fields:
                raise ValueError(f"Case {case.id} has no top-level numeric expected fields")
            evaluators.append(NumericEvaluator(fields=fields, absolute_tolerance=numeric_tolerance))
        elif evaluator_type is EvaluatorType.TOOL_CALL:
            evaluators.append(ToolCallEvaluator())
        elif evaluator_type is EvaluatorType.REQUIRED_FACTS:
            evaluators.append(RequiredFactsEvaluator())
        elif evaluator_type is EvaluatorType.CLASSIFICATION_METRICS:
            raise ValueError("ClassificationMetricsEvaluator aggregation is not implemented yet")
        elif evaluator_type is EvaluatorType.CRITERIA_JUDGE:
            raise ValueError("CriteriaJudgeEvaluator is not implemented yet")
        else:
            raise ValueError(f"Evaluator {evaluator_type.value!r} is not executable yet")
    return evaluators


def _evaluate_one(
    project_directory: Path,
    *,
    case: EvaluationCase,
    result: EvaluationResult,
    target_model: str,
    params: dict[str, Any],
    completion: Completion,
    evaluators: list[CaseEvaluator],
) -> EvaluationResult:
    started = perf_counter()
    try:
        response = completion(model=target_model, messages=case.messages, **params)
    except Exception as error:
        reason = f"Candidate provider error: {type(error).__name__}: {error}"
        return update_evaluation_result(
            project_directory,
            result_id=result.id,
            latency_ms=_elapsed_ms(started),
            state=CaseState.ERROR.value,
            score=0.0,
            verdict=[{"evaluator": "provider", "state": "ERROR", "reason": reason}],
            error=reason,
        )

    output_text, output_json, input_tokens, output_tokens, cost_usd = _response_fields(response)
    candidate = output_json if output_json is not None else output_text
    verdicts = [
        evaluator.evaluate(expected=case.expected, candidate=candidate) for evaluator in evaluators
    ]
    state = combine_verdicts(verdicts)
    score = sum(verdict.score for verdict in verdicts) / len(verdicts)
    return update_evaluation_result(
        project_directory,
        result_id=result.id,
        output_text=output_text,
        output_json=output_json,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        latency_ms=_elapsed_ms(started),
        state=state.value,
        score=score,
        verdict=[verdict.as_dict() for verdict in verdicts],
    )


def _numeric_fields(expected: Any) -> tuple[str, ...]:
    if not isinstance(expected, dict):
        return ()
    return tuple(
        key
        for key, value in expected.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    )


def _summary(experiment_id: str, results: list[EvaluationResult]) -> ExperimentSummary:
    states = [result.state for result in results]
    return ExperimentSummary(
        experiment_id=experiment_id,
        case_count=len(results),
        passed_count=states.count(CaseState.PASS.value),
        failed_count=states.count(CaseState.FAIL.value),
        review_count=states.count(CaseState.REVIEW.value),
        error_count=states.count(CaseState.ERROR.value),
    )


def _elapsed_ms(started: float) -> int:
    return round((perf_counter() - started) * 1000)
