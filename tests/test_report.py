"""Offline tests for static replay reports."""

from __future__ import annotations

from switchcheck.checkers import ContainsChecker
from switchcheck.replay import replay
from switchcheck.report import write_report
from switchcheck.store import create_run


def test_report_is_self_contained_and_lists_failures_first(tmp_path) -> None:
    """A report compares outputs safely and makes regressions immediately visible."""
    create_run(
        tmp_path,
        model="source/model",
        messages=[{"role": "user", "content": "one"}],
        params={},
        output_text="reference <script>alert(1)</script>",
    )
    create_run(
        tmp_path,
        model="source/model",
        messages=[{"role": "user", "content": "two"}],
        params={},
        output_text="reference two",
    )

    def fake_completion(**kwargs):
        content = kwargs["messages"][0]["content"]
        return {
            "choices": [{"message": {"content": "candidate one" if content == "one" else "two"}}]
        }

    summary = replay(
        tmp_path,
        target_model="candidate/model",
        checkers=[ContainsChecker("two")],
        completion=fake_completion,
    )
    destination = write_report(tmp_path, replay_id=summary.replay_id)
    page = destination.read_text(encoding="utf-8")

    assert destination == tmp_path / ".switchcheck" / "reports" / f"{summary.replay_id}.html"
    assert "Switchcheck replay report" in page
    assert "Evaluation failures" in page
    assert "Output is missing required text" in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "<script>alert(1)</script>" not in page
    assert page.index("Case 1") < page.index("Case 2")
    assert "Reproducibility" in page
    assert "<footer>" in page
    assert 'aria-label="Replay summary"' in page


def test_report_rejects_unknown_replay(tmp_path) -> None:
    """Reports cannot accidentally be created for unrelated identifiers."""
    try:
        write_report(tmp_path, replay_id="missing")
    except ValueError as error:
        assert "was not found" in str(error)
    else:
        raise AssertionError("Expected an unknown replay to fail")
