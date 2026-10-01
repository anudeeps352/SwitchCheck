# Switchcheck architecture

## Purpose

Switchcheck is a local-first Python tool for answering one question with real
application traffic: **can we change an LLM model, prompt, or parameters without
breaking the feature?**

It records calls made by an application, replays selected calls against a
candidate configuration, evaluates the outputs, and produces a portable HTML
report. It does not require a hosted service or a Switchcheck account.

## Build decision: v0.1

Build the smallest end-to-end vertical slice first:

1. Record non-streaming chat-completion calls through a Python wrapper.
2. Store those calls in a project-local SQLite database.
3. Replay calls against a chosen LiteLLM model.
4. Run deterministic checks (`exact`, `contains`, `regex`, and JSON Schema).
5. Generate a single static HTML report.

The first supported use case is structured extraction or classification, where
deterministic checks make a migration decision credible. LLM-as-a-judge,
streaming, multi-turn agents, hosted UI, and TypeScript support are deliberately
outside v0.1.

## System context

```text
Application
    │ calls a thin Switchcheck client
    ▼
Client wrapper ── calls ──> LiteLLM ──> provider/model
    │                              │
    │ records input, response, usage, latency and error
    ▼                              ▼
SQLite store <── replay engine ── candidate provider/model
    │                 │
    │                 ▼
    │             checkers
    ▼                 │
CLI ───────────────> static HTML report
```

The CLI is the composition layer; application code only depends on the client
wrapper. Provider-specific behavior remains behind LiteLLM.

## Components

| Component | Responsibility | v0.1 boundary |
|---|---|---|
| `client` | Call LiteLLM, measure the call, and persist a run. | Non-streaming chat completions only. |
| `store` | Own schema migrations and all SQLite queries. | A `.switchcheck/switchcheck.sqlite3` file; no network service. |
| `replay` | Load eligible runs, apply an override, invoke target model with bounded concurrency, and persist results. | One turn per recorded call. |
| `checkers` | Compare original and candidate outputs and return structured verdicts. | Deterministic checks first. |
| `pricing` | Estimate and calculate token cost using versioned local price data. | Unknown prices are displayed as unavailable, never invented. |
| `report` | Render replay results into a self-contained HTML file. | Summary, regressions, case detail, reproducibility metadata. |
| `cli` | Expose user workflows and validate input. | `init`, `runs`, `replay`, `report`; `export` is later. |

## Public interfaces

### Python API

Keep the first API intentionally small and stable:

```python
from switchcheck import client

response = client.chat(
    model="provider/model",
    messages=[{"role": "user", "content": "Extract invoice fields..."}],
    tag="invoice-extractor",
    temperature=0,
)
```

`tag` groups calls into a feature-level evaluation set. The wrapper returns the
underlying provider response (or a documented compatible response object) so
adding Switchcheck does not force an application rewrite.

### CLI

```text
switchcheck init
switchcheck runs --tag invoice-extractor --limit 20
switchcheck replay --tag invoice-extractor --model provider/candidate --check json-schema:schema.json
switchcheck report <replay-id-or-name>
```

`replay --dry-run` must show selected-run count and known estimated cost before
network calls. A configurable spend limit requires explicit confirmation.

## Data ownership and model

All persisted data is local. JSON fields preserve provider payloads without
locking the relational schema to one provider.

```text
runs (original application calls)
  1 ──── * replay_results (candidate outputs and verdicts)
replays (one experiment)
  1 ──── * replay_results
```

Minimum fields:

- `runs`: ID, timestamp, tag, model, normalized request parameters, messages,
  optional tools, output, raw response, token usage, cost, latency, error.
- `replays`: ID, timestamp, display name, source selection/tag, target model,
  prompt/parameter overrides, checker configuration, package version.
- `replay_results`: replay/run IDs, candidate output and usage, cost, latency,
  per-check verdict JSON, aggregate pass/score, error.

Use UUIDs, UTC ISO-8601 timestamps, foreign keys enabled, and migrations tracked
with `PRAGMA user_version`. Add indexes on `runs.tag`, `runs.created_at`, and
`replay_results.replay_id`.

## Replay lifecycle

```text
validate selection → create replay row → estimate cost → invoke candidate calls
→ persist each result (including errors) → run checks → render report
```

Each replay result is persisted independently. An interrupted replay can be
reported as partial and later resumed; it must never discard completed work.

Concurrency defaults conservatively and is configurable. Retry only transient
provider failures, using exponential backoff with jitter. Store the normalized
request actually sent and warnings for dropped/unsupported parameters.

## Evaluation contract

Every checker returns a serializable result:

```json
{
  "checker": "json-schema",
  "passed": true,
  "score": 1.0,
  "reason": "Output validates against the configured schema",
  "details": {}
}
```

Multiple checkers use logical AND for the overall `passed` value. The report
shows individual results so a failure remains explainable. A replay error is a
failed case with its error retained; it is not silently excluded from the rate.

## Privacy and safety

- Database and reports are local by default; no telemetry in v0.1.
- Treat prompts and outputs as potentially sensitive. Document that reports and
  database files must not be shared without review.
- Provide a redaction callback before persistence, then add built-in patterns
  only after the core flow works.
- Never log API keys or authorization headers.
- Make external model calls only during application calls or an explicit replay.

## Repository layout

```text
src/switchcheck/
  client.py        # recording wrapper
  store.py         # migrations and queries
  replay.py        # orchestration and retry/concurrency
  pricing.py
  report.py
  cli.py
  checkers/
  templates/
tests/
examples/invoice_extractor/
docs/
```

## Key decisions to revisit after v0.1

- Whether the wrapper should expose LiteLLM responses directly or define its own
  protocol.
- A configuration file format and its precedence relative to CLI arguments.
- Adding an LLM judge only once deterministic reporting is solid.
- Trace and tool-call semantics for multi-turn agent support.
