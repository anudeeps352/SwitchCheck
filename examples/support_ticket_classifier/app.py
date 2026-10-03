"""Dummy support-ticket application instrumented with Switchcheck.

Run with ``python examples/support_ticket_classifier/app.py`` to classify five
synthetic tickets with a configured model and record the calls. Use ``--fake``
for an offline run that consumes no API credits.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from switchcheck.client import Completion, chat

TAG = "support-ticket-demo"
DEFAULT_MODEL = "openai/gpt-6-luna"

TICKETS = (
    {
        "id": "TICKET-001",
        "text": "I was charged twice for order 1842. Please refund the duplicate charge.",
    },
    {
        "id": "TICKET-002",
        "text": "The password-reset email never arrives, so I cannot access my account.",
    },
    {
        "id": "TICKET-003",
        "text": "Please add a dark mode. The current interface works, but it is bright at night.",
    },
    {
        "id": "TICKET-004",
        "text": "The mobile app crashes every time I press Pay, so I cannot complete checkout.",
    },
    {
        "id": "TICKET-005",
        "text": "The dashboard total is displayed as $0 even though this month has seven orders.",
    },
)

SYSTEM_PROMPT = """
You classify customer-support tickets.

Return only a JSON object with exactly these fields:
- category: one of "billing", "account_access", "bug", or "feature_request"
- priority: one of "high", "medium", or "low"
- summary: one short sentence

Priority rules:
- high: payment problem, security risk, or the service is unusable
- medium: the customer is blocked from an account or an important task
- low: feature request or non-blocking inconvenience

Do not use Markdown or add fields.
""".strip()

_FAKE_RESULTS = {
    "TICKET-001": {
        "category": "billing",
        "priority": "high",
        "summary": "Customer requests a refund for a duplicate order charge.",
    },
    "TICKET-002": {
        "category": "account_access",
        "priority": "medium",
        "summary": "Customer cannot receive the password-reset email.",
    },
    "TICKET-003": {
        "category": "feature_request",
        "priority": "low",
        "summary": "Customer requests a dark mode for nighttime use.",
    },
    "TICKET-004": {
        "category": "bug",
        "priority": "high",
        "summary": "Mobile checkout crashes when the customer tries to pay.",
    },
    "TICKET-005": {
        "category": "bug",
        "priority": "medium",
        "summary": "Dashboard incorrectly shows zero orders for the month.",
    },
}


def _fake_completion(**kwargs: Any) -> dict[str, Any]:
    """Return deterministic classifications for tests and offline exploration."""
    ticket_id = kwargs["messages"][-1]["content"].split(":", 1)[0]
    return {
        "choices": [{"message": {"content": json.dumps(_FAKE_RESULTS[ticket_id])}}],
        "usage": {"prompt_tokens": 80, "completion_tokens": 25},
    }


def _response_text(response: Any) -> str:
    data = response if isinstance(response, dict) else response.model_dump()
    return str(data["choices"][0]["message"]["content"])


def record_tickets(
    project_directory: Path,
    *,
    model: str = DEFAULT_MODEL,
    tag: str = TAG,
    completion: Completion | None = None,
) -> list[str]:
    """Classify all sample tickets and record each provider call."""
    outputs: list[str] = []
    for ticket in TICKETS:
        response = chat(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"{ticket['id']}: {ticket['text']}",
                },
            ],
            tag=tag,
            max_tokens=800,
            project_directory=project_directory,
            completion=completion,
        )
        output = _response_text(response)
        outputs.append(output)
        print(f"{ticket['id']}: {output}")
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path("."))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--tag", default=TAG)
    parser.add_argument(
        "--fake",
        action="store_true",
        help="Use deterministic local responses instead of an API.",
    )
    arguments = parser.parse_args()
    record_tickets(
        arguments.project,
        model="fake/support-classifier" if arguments.fake else arguments.model,
        tag=arguments.tag,
        completion=_fake_completion if arguments.fake else None,
    )
    print()
    print(f"Recorded {len(TICKETS)} calls with tag {arguments.tag!r}.")
    print(f"Next: switchcheck runs --tag {arguments.tag}")


if __name__ == "__main__":
    main()
