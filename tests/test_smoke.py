"""End-to-end acceptance test using the synthetic invoice example."""

from examples.invoice_extractor.demo import run_demo


def test_invoice_example_runs_offline_and_generates_a_report(tmp_path) -> None:
    """The release workflow works without provider credentials or a network."""
    report = run_demo(tmp_path)
    page = report.read_text(encoding="utf-8")

    assert report.is_file()
    assert "Switchcheck replay report" in page
    assert "2 (100%)" in page
    assert "invoice-extractor" in page
