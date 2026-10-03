"""Tests for deterministic evaluation and its replay integration."""

from __future__ import annotations

import json

import pytest

from switchcheck.checkers import JsonFieldChecker, JsonSchemaChecker, parse_checkers
from switchcheck.replay import replay
from switchcheck.store import create_run, list_replay_results


def _response(content: str) -> dict[str, object]:
    return {"choices": [{"message": {"content": content}}], "usage": {}}


def test_replay_persists_all_verdicts_and_uses_logical_and(tmp_path) -> None:
    """A result passes only when all configured checks pass."""
    create_run(
        tmp_path,
        model="source/model",
        messages=[{"role": "user", "content": "hello"}],
        params={},
        output_text="invoice 42",
    )

    summary = replay(
        tmp_path,
        target_model="candidate/model",
        checkers=parse_checkers(["contains:invoice", "regex:^invoice [0-9]+$", "exact"]),
        completion=lambda **_: _response("invoice 43"),
    )

    result = list_replay_results(tmp_path, replay_id=summary.replay_id)[0]
    assert result.passed is False
    assert result.score == pytest.approx(2 / 3)
    assert summary.pass_rate == 0.0
    assert summary.evaluation_failed_count == 1
    assert result.verdict is not None
    assert [item["checker"] for item in result.verdict] == ["contains", "regex", "exact"]


def test_provider_error_is_a_persisted_failed_verdict(tmp_path) -> None:
    """Errors are evaluation failures rather than omitted from the result set."""
    create_run(
        tmp_path,
        model="source/model",
        messages=[{"role": "user", "content": "hello"}],
        params={},
    )

    def fail(**_):
        raise ValueError("bad request")

    summary = replay(tmp_path, target_model="candidate/model", completion=fail)

    result = list_replay_results(tmp_path, replay_id=summary.replay_id)[0]
    assert result.passed is False
    assert result.score == 0.0
    assert summary.pass_rate == 0.0
    assert summary.evaluation_failed_count == 1
    assert result.verdict is not None
    assert result.verdict[0]["checker"] == "provider"


def test_json_schema_and_json_field_checkers(tmp_path) -> None:
    """JSON checks parse textual model outputs and give explainable failures."""
    schema_path = tmp_path / "invoice-schema.json"
    schema_path.write_text(json.dumps({"type": "object", "required": ["total"]}), encoding="utf-8")
    schema_checker = parse_checkers([f"json-schema:{schema_path.name}"], base_path=tmp_path)[0]

    schema_verdict = schema_checker.evaluate(
        reference_text=None,
        reference_json=None,
        candidate_text='{"total": 42}',
        candidate_json=None,
    )
    field_verdict = JsonFieldChecker("total").evaluate(
        reference_text='{"total": 42}',
        reference_json=None,
        candidate_text='{"total": 43}',
        candidate_json=None,
    )

    assert isinstance(schema_checker, JsonSchemaChecker)
    assert schema_verdict.passed is True
    assert field_verdict.passed is False


def test_invalid_checker_configuration_is_rejected_before_replay() -> None:
    """Malformed deterministic checkers fail fast without provider calls."""
    with pytest.raises(ValueError, match="Invalid regex"):
        parse_checkers(["regex:(["])
