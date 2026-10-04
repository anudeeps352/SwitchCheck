"""Read-only eligibility checks for persisted evaluation datasets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from switchcheck.contracts import CASE_CONTRACT_VERSION, validate_case_contract
from switchcheck.store import Dataset, EvaluationCase, get_dataset, list_evaluation_cases


@dataclass(frozen=True)
class EligibilityIssue:
    """One reason a dataset or case cannot be evaluated automatically."""

    case_id: str | None
    reason: str


@dataclass(frozen=True)
class EligibilityReport:
    """Result of checking a dataset without invoking a model or evaluator."""

    dataset: Dataset
    case_count: int
    eligible_count: int
    issues: tuple[EligibilityIssue, ...]

    @property
    def eligible(self) -> bool:
        """Whether the complete dataset satisfies the current contract."""
        return not self.issues and self.eligible_count == self.case_count


def check_dataset_eligibility(project_directory: Path, *, identifier: str) -> EligibilityReport:
    """Validate every persisted case without making any provider call."""
    dataset = get_dataset(project_directory, identifier=identifier)
    if dataset is None:
        raise ValueError(f"Dataset {identifier!r} was not found in this project.")

    cases = list_evaluation_cases(project_directory, dataset_id=dataset.id)
    issues: list[EligibilityIssue] = []
    eligible_count = 0
    if dataset.contract_version != CASE_CONTRACT_VERSION:
        issues.append(
            EligibilityIssue(
                case_id=None,
                reason=(
                    f"dataset contract_version {dataset.contract_version} is legacy; "
                    f"re-import or migrate it to version {CASE_CONTRACT_VERSION}"
                ),
            )
        )

    for case in cases:
        reason = _case_issue(case)
        if reason is None:
            eligible_count += 1
        else:
            issues.append(EligibilityIssue(case_id=case.id, reason=reason))

    if not cases:
        issues.append(EligibilityIssue(case_id=None, reason="dataset contains no cases"))

    return EligibilityReport(
        dataset=dataset,
        case_count=len(cases),
        eligible_count=eligible_count,
        issues=tuple(issues),
    )


def _case_issue(case: EvaluationCase) -> str | None:
    if case.contract_version != CASE_CONTRACT_VERSION:
        return (
            f"contract_version {case.contract_version} is legacy; explicitly migrate this case "
            f"to version {CASE_CONTRACT_VERSION}"
        )
    try:
        validate_case_contract(
            task_type=case.task_type,
            messages=case.messages,
            has_expected=case.has_expected,
            expected=case.expected,
            has_reference=case.has_reference,
            reference=case.reference,
            has_context=case.has_context,
            context=case.context,
            criteria=case.criteria,
            evaluators=case.evaluators,
        )
    except ValueError as error:
        return str(error)
    return None
