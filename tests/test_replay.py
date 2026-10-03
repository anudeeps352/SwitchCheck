"""Offline tests for candidate-model replay behavior."""

from __future__ import annotations

from switchcheck.replay import replay, replay_dry_run
from switchcheck.store import create_run, list_replay_results


def _record_run(tmp_path, content: str, tag: str = "invoices") -> None:
    create_run(
        tmp_path,
        model="source/model",
        messages=[{"role": "user", "content": content}],
        params={"temperature": 0},
        tag=tag,
    )


def test_replay_dry_run_does_not_create_a_session(tmp_path) -> None:
    """Dry runs select exactly the calls a live replay would select."""
    _record_run(tmp_path, "one")
    _record_run(tmp_path, "two", tag="other")

    assert replay_dry_run(tmp_path, tag="invoices") == 1


def test_replay_persists_success_and_provider_failure(tmp_path) -> None:
    """One bad candidate call does not discard successful results."""
    _record_run(tmp_path, "good")
    _record_run(tmp_path, "bad")

    def fake_completion(**kwargs):
        content = kwargs["messages"][0]["content"]
        if content == "bad":
            raise ValueError("unsupported request")
        return {
            "choices": [{"message": {"content": f"candidate: {content}"}}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 3},
        }

    summary = replay(
        tmp_path,
        target_model="candidate/model",
        tag="invoices",
        concurrency=2,
        completion=fake_completion,
    )

    assert summary.selected_count == 2
    assert summary.completed_count == 1
    assert summary.failed_count == 1
    results = list_replay_results(tmp_path, replay_id=summary.replay_id)
    assert len(results) == 2
    assert {result.output_text for result in results} == {"candidate: good", None}
    assert any(result.error == "ValueError: unsupported request" for result in results)


def test_replay_retries_transient_error(tmp_path) -> None:
    """Timeouts are retried before a replay is marked failed."""
    _record_run(tmp_path, "retry")
    attempts = 0

    def fake_completion(**_):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TimeoutError("temporary")
        return {"choices": [{"message": {"content": "recovered"}}], "usage": {}}

    summary = replay(tmp_path, target_model="candidate/model", completion=fake_completion)

    assert attempts == 2
    assert summary.completed_count == 1
    assert list_replay_results(tmp_path, replay_id=summary.replay_id)[0].output_text == "recovered"
