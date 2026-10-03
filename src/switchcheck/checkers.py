"""Deterministic output checkers used by candidate replays."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from jsonschema import Draft202012Validator, SchemaError, ValidationError


@dataclass(frozen=True)
class Verdict:
    """A serializable, explainable result from one deterministic checker."""

    checker: str
    passed: bool
    score: float
    reason: str
    details: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation for SQLite storage."""
        return asdict(self)


class Checker(Protocol):
    """A deterministic comparison of a candidate response to a recorded run."""

    def evaluate(
        self,
        *,
        reference_text: str | None,
        reference_json: Any | None,
        candidate_text: str | None,
        candidate_json: Any | None,
    ) -> Verdict: ...

    def config(self) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ExactChecker:
    """Require the candidate text to exactly match the recorded text."""

    def evaluate(self, **values: Any) -> Verdict:
        reference = values["reference_text"]
        candidate = values["candidate_text"]
        passed = reference is not None and candidate == reference
        return Verdict(
            checker="exact",
            passed=passed,
            score=1.0 if passed else 0.0,
            reason="Output exactly matches the recorded output"
            if passed
            else "Output does not exactly match the recorded output",
            details={},
        )

    def config(self) -> dict[str, Any]:
        return {"type": "exact"}


@dataclass(frozen=True)
class ContainsChecker:
    """Require a configured literal string in the candidate text."""

    needle: str

    def evaluate(self, **values: Any) -> Verdict:
        candidate = values["candidate_text"]
        passed = candidate is not None and self.needle in candidate
        return Verdict(
            checker="contains",
            passed=passed,
            score=1.0 if passed else 0.0,
            reason="Output contains the required text"
            if passed
            else "Output is missing required text",
            details={"needle": self.needle},
        )

    def config(self) -> dict[str, Any]:
        return {"type": "contains", "needle": self.needle}


@dataclass(frozen=True)
class RegexChecker:
    """Require the candidate text to match a configured regular expression."""

    pattern: str

    def evaluate(self, **values: Any) -> Verdict:
        candidate = values["candidate_text"]
        passed = candidate is not None and re.search(self.pattern, candidate) is not None
        return Verdict(
            checker="regex",
            passed=passed,
            score=1.0 if passed else 0.0,
            reason="Output matches the required regular expression"
            if passed
            else "Output does not match the required regular expression",
            details={"pattern": self.pattern},
        )

    def config(self) -> dict[str, Any]:
        return {"type": "regex", "pattern": self.pattern}


@dataclass(frozen=True)
class JsonSchemaChecker:
    """Validate a JSON candidate output against a JSON Schema."""

    schema: dict[str, Any]

    def __post_init__(self) -> None:
        try:
            Draft202012Validator.check_schema(self.schema)
        except SchemaError as error:
            raise ValueError(f"Invalid JSON Schema: {error.message}") from error

    def evaluate(self, **values: Any) -> Verdict:
        try:
            candidate = _json_output(values["candidate_text"], values["candidate_json"])
        except ValueError as error:
            return Verdict("json-schema", False, 0.0, str(error), {})
        try:
            Draft202012Validator(self.schema).validate(candidate)
        except ValidationError as error:
            return Verdict(
                "json-schema", False, 0.0, f"JSON Schema validation failed: {error.message}", {}
            )
        return Verdict("json-schema", True, 1.0, "Output validates against the JSON Schema", {})

    def config(self) -> dict[str, Any]:
        return {"type": "json-schema", "schema": self.schema}


@dataclass(frozen=True)
class JsonFieldChecker:
    """Require a dotted JSON field to retain its recorded value."""

    path: str

    def evaluate(self, **values: Any) -> Verdict:
        try:
            reference = _field(
                _json_output(values["reference_text"], values["reference_json"]), self.path
            )
            candidate = _field(
                _json_output(values["candidate_text"], values["candidate_json"]), self.path
            )
        except ValueError as error:
            return Verdict("json-field", False, 0.0, str(error), {"path": self.path})
        passed = candidate == reference
        return Verdict(
            "json-field",
            passed,
            1.0 if passed else 0.0,
            "JSON field matches the recorded value"
            if passed
            else "JSON field differs from recorded value",
            {"path": self.path},
        )

    def config(self) -> dict[str, Any]:
        return {"type": "json-field", "path": self.path}


def parse_checkers(specifications: list[str], *, base_path: Path = Path(".")) -> list[Checker]:
    """Parse and validate repeatable CLI check specifications before replay starts."""
    checkers: list[Checker] = []
    for specification in specifications:
        kind, separator, value = specification.partition(":")
        if kind == "exact" and not separator:
            checkers.append(ExactChecker())
        elif kind == "contains" and separator and value:
            checkers.append(ContainsChecker(value))
        elif kind == "regex" and separator and value:
            try:
                re.compile(value)
            except re.error as error:
                raise ValueError(f"Invalid regex checker {specification!r}: {error}") from error
            checkers.append(RegexChecker(value))
        elif kind == "json-schema" and separator and value:
            schema_path = (base_path / value).resolve()
            try:
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
            except OSError as error:
                raise ValueError(f"Cannot read JSON Schema {schema_path}: {error}") from error
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON Schema file {schema_path}: {error.msg}") from error
            if not isinstance(schema, dict):
                raise ValueError("JSON Schema root must be an object")
            checkers.append(JsonSchemaChecker(schema))
        elif kind == "json-field" and separator and value:
            checkers.append(JsonFieldChecker(value))
        else:
            raise ValueError(
                "Invalid checker. Use exact, contains:TEXT, regex:PATTERN, "
                "json-schema:FILE, or json-field:PATH."
            )
    return checkers


def checker_config(checkers: list[Checker]) -> list[dict[str, Any]]:
    """Serialize checker configuration with the replay for reproducibility."""
    return [checker.config() for checker in checkers]


def _json_output(text: str | None, value: Any | None) -> Any:
    if value is not None:
        return value
    if text is None:
        raise ValueError("Output is missing JSON content")
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"Output is not valid JSON: {error.msg}") from error


def _field(value: Any, path: str) -> Any:
    current = value
    for segment in path.split("."):
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        elif isinstance(current, list) and segment.isdigit() and int(segment) < len(current):
            current = current[int(segment)]
        else:
            raise ValueError(f"JSON field {path!r} is missing")
    return current
