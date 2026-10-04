"""Supported evaluation task types and their allowed evaluator families."""

from __future__ import annotations

from enum import Enum


class TaskType(str, Enum):
    """The complete set of task families supported by the initial product."""

    CLASSIFICATION = "classification"
    EXTRACTION = "extraction"
    STRUCTURED_TRANSFORMATION = "structured_transformation"
    TOOL_SELECTION = "tool_selection"
    DECISION = "decision"
    FACTUAL_QA = "factual_qa"
    SUPPORT_RESPONSE = "support_response"
    SUMMARIZATION = "summarization"
    RAG_ANSWER = "rag_answer"
    RUBRIC_FREE_TEXT = "rubric_free_text"


class EvaluatorType(str, Enum):
    """Public evaluator identifiers used in dataset and experiment configuration."""

    EXACT = "exact"
    FIELDS = "fields"
    SCHEMA = "schema"
    NUMERIC = "numeric"
    PATTERN = "pattern"
    CLASSIFICATION_METRICS = "classification_metrics"
    TOOL_CALL = "tool_call"
    CRITERIA_JUDGE = "criteria_judge"
    REQUIRED_FACTS = "required_facts"


PERMITTED_EVALUATORS: dict[TaskType, frozenset[EvaluatorType]] = {
    TaskType.CLASSIFICATION: frozenset(
        {EvaluatorType.EXACT, EvaluatorType.FIELDS, EvaluatorType.CLASSIFICATION_METRICS}
    ),
    TaskType.EXTRACTION: frozenset(
        {EvaluatorType.SCHEMA, EvaluatorType.FIELDS, EvaluatorType.NUMERIC, EvaluatorType.EXACT}
    ),
    TaskType.STRUCTURED_TRANSFORMATION: frozenset(
        {EvaluatorType.SCHEMA, EvaluatorType.FIELDS, EvaluatorType.NUMERIC, EvaluatorType.EXACT}
    ),
    TaskType.TOOL_SELECTION: frozenset(
        {EvaluatorType.TOOL_CALL, EvaluatorType.SCHEMA, EvaluatorType.FIELDS}
    ),
    TaskType.DECISION: frozenset(
        {EvaluatorType.EXACT, EvaluatorType.FIELDS, EvaluatorType.CLASSIFICATION_METRICS}
    ),
    TaskType.FACTUAL_QA: frozenset(
        {
            EvaluatorType.REQUIRED_FACTS,
            EvaluatorType.EXACT,
            EvaluatorType.FIELDS,
            EvaluatorType.CRITERIA_JUDGE,
        }
    ),
    TaskType.SUPPORT_RESPONSE: frozenset(
        {EvaluatorType.REQUIRED_FACTS, EvaluatorType.CRITERIA_JUDGE}
    ),
    TaskType.SUMMARIZATION: frozenset({EvaluatorType.REQUIRED_FACTS, EvaluatorType.CRITERIA_JUDGE}),
    TaskType.RAG_ANSWER: frozenset({EvaluatorType.REQUIRED_FACTS, EvaluatorType.CRITERIA_JUDGE}),
    TaskType.RUBRIC_FREE_TEXT: frozenset({EvaluatorType.CRITERIA_JUDGE}),
}

JUDGE_TASK_TYPES = frozenset(
    {
        TaskType.FACTUAL_QA,
        TaskType.SUPPORT_RESPONSE,
        TaskType.SUMMARIZATION,
        TaskType.RAG_ANSWER,
        TaskType.RUBRIC_FREE_TEXT,
    }
)


def parse_task_type(value: object) -> TaskType:
    """Parse a task type while returning a useful validation error."""
    if not isinstance(value, str):
        raise ValueError("task_type must be a string")
    try:
        return TaskType(value)
    except ValueError as error:
        supported = ", ".join(task_type.value for task_type in TaskType)
        raise ValueError(f"unsupported task_type {value!r}; use one of: {supported}") from error


def parse_evaluators(task_type: TaskType, value: object) -> tuple[EvaluatorType, ...]:
    """Parse evaluator IDs and reject task/evaluator combinations outside the contract."""
    if value is None:
        return ()
    if not isinstance(value, list) or not value:
        raise ValueError("evaluators must be a non-empty list when provided")

    evaluators: list[EvaluatorType] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("each evaluator must be a string")
        try:
            evaluator = EvaluatorType(item)
        except ValueError as error:
            supported = ", ".join(evaluator_type.value for evaluator_type in EvaluatorType)
            raise ValueError(f"unsupported evaluator {item!r}; use one of: {supported}") from error
        if evaluator not in PERMITTED_EVALUATORS[task_type]:
            raise ValueError(
                f"evaluator {evaluator.value!r} is not permitted for task_type {task_type.value!r}"
            )
        evaluators.append(evaluator)
    return tuple(evaluators)
