"""Validation for the supported, versioned evaluation-case contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from switchcheck.task_types import EvaluatorType, TaskType

CASE_CONTRACT_VERSION = 1


@dataclass(frozen=True)
class Criterion:
    """One observable requirement used to evaluate a free-text response."""

    id: str
    requirement: str

    def as_dict(self) -> dict[str, str]:
        """Return the stable JSON representation."""
        return {"id": self.id, "requirement": self.requirement}


_VAGUE_CRITERIA = {
    "good answer",
    "high quality",
    "sounds intelligent",
    "is this a good answer",
    "is this response good",
}

_EXPECTED_TASKS = frozenset(
    {
        TaskType.CLASSIFICATION,
        TaskType.EXTRACTION,
        TaskType.STRUCTURED_TRANSFORMATION,
        TaskType.TOOL_SELECTION,
        TaskType.DECISION,
    }
)


def parse_messages(value: object) -> list[dict[str, Any]]:
    """Validate the initial single-turn message contract."""
    if not isinstance(value, list) or not value:
        raise ValueError("messages must be a non-empty list")

    messages: list[dict[str, Any]] = []
    user_count = 0
    for message in value:
        if not isinstance(message, dict):
            raise ValueError("each message must be an object")
        role = message.get("role")
        content = message.get("content")
        if role not in {"system", "developer", "user"}:
            raise ValueError(
                "single-turn cases only allow system, developer, and user message roles"
            )
        if not isinstance(content, str) or not content.strip():
            raise ValueError("each message must contain non-empty string content")
        if role == "user":
            user_count += 1
        messages.append(dict(message))

    if user_count != 1:
        raise ValueError("single-turn cases must contain exactly one user message")
    if messages[-1]["role"] != "user":
        raise ValueError("the user message must be the final message in a single-turn case")
    return messages


def parse_criteria(value: object) -> tuple[Criterion, ...]:
    """Parse concrete, uniquely identified criteria."""
    if value is None:
        return ()
    if not isinstance(value, list) or not value:
        raise ValueError("criteria must be a non-empty list when provided")

    criteria: list[Criterion] = []
    seen_ids: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("each criterion must be an object")
        criterion_id = item.get("id")
        requirement = item.get("requirement")
        if not isinstance(criterion_id, str) or not criterion_id.strip():
            raise ValueError("each criterion must have a non-empty string id")
        if not isinstance(requirement, str) or not requirement.strip():
            raise ValueError("each criterion must have a non-empty string requirement")
        criterion_id = criterion_id.strip()
        requirement = requirement.strip()
        if criterion_id in seen_ids:
            raise ValueError(f"duplicate criterion id {criterion_id!r}")
        normalized = requirement.lower().strip(" .?!")
        if normalized in _VAGUE_CRITERIA:
            raise ValueError(
                f"criterion {criterion_id!r} is vague; state a concrete observable requirement"
            )
        seen_ids.add(criterion_id)
        criteria.append(Criterion(id=criterion_id, requirement=requirement))
    return tuple(criteria)


def validate_case_contract(
    *,
    task_type: TaskType | None,
    messages: list[dict[str, Any]],
    has_expected: bool,
    expected: Any,
    has_reference: bool,
    reference: Any,
    has_context: bool,
    context: Any,
    criteria: tuple[Criterion, ...],
    evaluators: tuple[EvaluatorType, ...],
) -> None:
    """Apply task-specific eligibility rules without making provider calls."""
    if task_type is None:
        raise ValueError("task_type is required; legacy cases must be explicitly relabeled")
    parse_messages(messages)

    if task_type in _EXPECTED_TASKS and not has_expected:
        raise ValueError(f"expected is required for task_type {task_type.value!r}")
    if task_type is TaskType.FACTUAL_QA and not (has_expected or has_reference):
        raise ValueError("factual_qa requires expected facts or reference information")
    if task_type is TaskType.SUPPORT_RESPONSE:
        _require_context_and_criteria(task_type, has_context, criteria)
    if task_type is TaskType.SUMMARIZATION:
        _require_context_and_criteria(task_type, has_context, criteria)
    if task_type is TaskType.RAG_ANSWER:
        _require_context_and_criteria(task_type, has_context, criteria)
    if task_type is TaskType.RUBRIC_FREE_TEXT and not criteria:
        raise ValueError("rubric_free_text requires explicit observable criteria")

    if EvaluatorType.CRITERIA_JUDGE in evaluators and not criteria:
        raise ValueError("criteria_judge requires explicit observable criteria")
    if EvaluatorType.REQUIRED_FACTS in evaluators and not (has_expected or has_reference):
        raise ValueError("required_facts requires expected facts or reference information")
    if (
        task_type is TaskType.TOOL_SELECTION
        and has_expected
        and (not isinstance(expected, dict) or not isinstance(expected.get("tool"), str))
    ):
        raise ValueError("tool_selection expected must be an object with a string tool")

    if has_reference and reference is None:
        raise ValueError("reference must not be null when provided")
    if has_context and context is None:
        raise ValueError("context must not be null when provided")


def _require_context_and_criteria(
    task_type: TaskType, has_context: bool, criteria: tuple[Criterion, ...]
) -> None:
    if not has_context:
        raise ValueError(f"context is required for task_type {task_type.value!r}")
    if not criteria:
        raise ValueError(f"criteria are required for task_type {task_type.value!r}")
