"""Offline coverage for the support-ticket comparison example."""

import json

from examples.support_ticket_classifier.app import TAG, _fake_completion, record_tickets

from switchcheck.store import list_runs


def test_support_ticket_example_records_five_valid_json_calls(tmp_path) -> None:
    outputs = record_tickets(tmp_path, completion=_fake_completion)

    assert len(outputs) == 5
    assert all(isinstance(json.loads(output), dict) for output in outputs)
    runs = list_runs(tmp_path, tag=TAG, limit=10)
    assert len(runs) == 5
    assert all(run.output_json is not None for run in runs)
