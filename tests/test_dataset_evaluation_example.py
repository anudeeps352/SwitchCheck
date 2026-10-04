"""Offline acceptance test for the labeled evaluation example."""

from pathlib import Path

from examples.dataset_evaluation.demo import run_demo


def test_dataset_evaluation_demo_runs_end_to_end(tmp_path: Path) -> None:
    summary, report = run_demo(tmp_path)

    assert summary.case_count == 2
    assert summary.passed_count == 1
    assert summary.failed_count == 1
    assert report.is_file()
    assert "Switchcheck experiment" in report.read_text(encoding="utf-8")
