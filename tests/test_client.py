"""Tests for recording application calls without a network provider."""

from __future__ import annotations

import pytest

from switchcheck.client import chat
from switchcheck.store import list_runs


def test_chat_records_response(tmp_path) -> None:
    """A successful provider response is returned and made replayable."""
    response = {
        "choices": [{"message": {"content": "Invoice total: 42"}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 4},
        "_hidden_params": {"response_cost": 0.001},
    }

    actual = chat(
        model="fake/model",
        messages=[{"role": "user", "content": "Extract the total."}],
        tag="invoices",
        temperature=0,
        completion=lambda **_: response,
        project_directory=tmp_path,
    )

    assert actual is response
    runs = list_runs(tmp_path)
    assert len(runs) == 1
    run = runs[0]
    assert run.model == "fake/model"
    assert run.tag == "invoices"
    assert run.params == {"temperature": 0}
    assert run.output_text == "Invoice total: 42"
    assert run.input_tokens == 12
    assert run.output_tokens == 4
    assert run.cost_usd == 0.001
    assert run.error is None


def test_chat_records_provider_error(tmp_path) -> None:
    """Provider failures remain visible in the recorded history."""

    def fail(**_: object) -> None:
        raise TimeoutError("provider timed out")

    with pytest.raises(TimeoutError, match="provider timed out"):
        chat(
            model="fake/model",
            messages=[{"role": "user", "content": "Hello"}],
            completion=fail,
            project_directory=tmp_path,
        )

    run = list_runs(tmp_path)[0]
    assert run.error == "TimeoutError: provider timed out"
    assert run.output_text is None


def test_chat_records_json_message_content_as_json(tmp_path) -> None:
    """JSON checkers receive the assistant output, not the provider response envelope."""
    chat(
        model="fake/model",
        messages=[{"role": "user", "content": "Extract the invoice."}],
        completion=lambda **_: {
            "choices": [{"message": {"content": '{"invoice_id":"INV-1001"}'}}]
        },
        project_directory=tmp_path,
    )

    run = list_runs(tmp_path)[0]
    assert run.output_json == {"invoice_id": "INV-1001"}


def test_chat_rejects_empty_messages(tmp_path) -> None:
    """Invalid requests are rejected before they reach a provider or the store."""
    with pytest.raises(ValueError, match="at least one"):
        chat(model="fake/model", messages=[], completion=lambda **_: {}, project_directory=tmp_path)

    assert list_runs(tmp_path) == []
