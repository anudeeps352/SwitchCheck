# Privacy, price data, and provider limits

Switchcheck is local-first: it does not send data to Switchcheck-operated
services or collect telemetry. The local SQLite database and generated reports
contain the prompts, model outputs, and provider error messages needed to make
a replay explainable. Treat `.switchcheck/` and exported HTML reports as
sensitive artifacts; review them before sharing, committing, or attaching them
to a ticket.

v0.1 does not redact content automatically. Remove or replace sensitive values
in the application before calling `switchcheck.client.chat`, and use synthetic
or approved data for demonstrations. Never place API keys, authorization
headers, or secrets in prompts, tags, or command-line arguments.

The current wrapper supports non-streaming chat completions only. Streaming,
tool-call execution, multi-turn traces, and agent replay are outside the v0.1
scope. A replay makes a new call to the candidate provider, so it is subject to
that provider's authentication, rate, retention, regional-processing, and
pricing policies. Start with `switchcheck replay --dry-run`, small limits, and
low-cost candidate models.

Cost fields are shown only when the provider response supplies them. Switchcheck
does not currently maintain local model price data, so dry-run cost estimates
are deliberately reported as unavailable rather than guessed.
