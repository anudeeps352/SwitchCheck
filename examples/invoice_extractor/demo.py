"""Record, replay, evaluate, and report a synthetic invoice extractor.

Run offline with ``python examples/invoice_extractor/demo.py --fake``. Omit
``--fake`` to call the LiteLLM models supplied with ``--model`` and
``--candidate-model``; that requires the relevant provider credentials.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from switchcheck.checkers import JsonFieldChecker, JsonSchemaChecker
from switchcheck.client import Completion, chat
from switchcheck.replay import replay
from switchcheck.report import write_report

INVOICES = (
    "Invoice INV-1001: Acme Supplies billed USD 42.50.",
    "Invoice INV-1002: Northwind Traders billed USD 18.00.",
)
SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["invoice_id", "vendor", "total_usd"],
    "properties": {
        "invoice_id": {"type": "string"},
        "vendor": {"type": "string"},
        "total_usd": {"type": "number"},
    },
    "additionalProperties": False,
}


def _fake_completion(**kwargs: Any) -> dict[str, Any]:
    """Return deterministic responses, allowing the full workflow to stay offline."""
    prompt = kwargs["messages"][-1]["content"]
    records = {
        INVOICES[0]: {"invoice_id": "INV-1001", "vendor": "Acme Supplies", "total_usd": 42.5},
        INVOICES[1]: {"invoice_id": "INV-1002", "vendor": "Northwind Traders", "total_usd": 18.0},
    }
    return {
        "choices": [{"message": {"content": json.dumps(records[prompt])}}],
        "usage": {"prompt_tokens": 20, "completion_tokens": 12},
    }


def run_demo(
    project_directory: Path,
    *,
    model: str = "fake/source",
    candidate_model: str = "fake/candidate",
    completion: Completion | None = _fake_completion,
) -> Path:
    """Execute the complete invoice workflow and return its generated report path."""
    for invoice in INVOICES:
        chat(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract the invoice as JSON with invoice_id, vendor, and total_usd."
                    ),
                },
                {"role": "user", "content": invoice},
            ],
            tag="invoice-extractor",
            temperature=0,
            project_directory=project_directory,
            completion=completion,
        )
    summary = replay(
        project_directory,
        target_model=candidate_model,
        tag="invoice-extractor",
        checkers=[JsonSchemaChecker(SCHEMA), JsonFieldChecker("invoice_id")],
        completion=completion,
    )
    return write_report(project_directory, replay_id=summary.replay_id)


def main() -> None:
    """Run the demo with an offline fake provider or caller-configured LiteLLM provider."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path("."))
    parser.add_argument("--model", default="openai/gpt-4o-mini")
    parser.add_argument("--candidate-model", default="openai/gpt-4o-mini")
    parser.add_argument(
        "--fake", action="store_true", help="Use the deterministic offline provider."
    )
    arguments = parser.parse_args()
    completion = _fake_completion if arguments.fake else None
    report = run_demo(
        arguments.project,
        model="fake/source" if arguments.fake else arguments.model,
        candidate_model="fake/candidate" if arguments.fake else arguments.candidate_model,
        completion=completion,
    )
    print(f"Wrote report to {report}")


if __name__ == "__main__":
    main()
