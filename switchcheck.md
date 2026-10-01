# Switchcheck

> **Will switching to a cheaper or newer model break my app?** Switchcheck answers that in one command, using your own real LLM traffic.

---

## 1. The problem

Teams with an LLM feature in production (invoice extraction, support replies, classification, summaries) face the same situation every few weeks:

- A cheaper or faster model is released, or a provider deprecates the one they use.
- They tweak a prompt to fix one bug and have no idea what else it broke.
- Nobody dares switch without testing, so they either overpay or ship on a guess.

Existing eval tools are mostly heavy hosted platforms: sign-ups, dashboards, SDK lock-in, team pricing. There is room for a **tiny, local, zero-signup tool** that does one thing well: record what your app really did, replay it somewhere else, and show the difference.

## 2. Target users and use cases

| Who | Scenario | What they get |
|---|---|---|
| Indie dev with an LLM feature | "Can I move from Model A to the cheaper Model B?" | Pass rate, cost and latency deltas, list of regressed cases |
| Small team iterating on prompts | "Did prompt v2 break anything v1 handled?" | Side-by-side diff on real past inputs |
| Developer on a provider deprecation notice | "What happens when the old model is retired?" | A safe, evidence-based migration |
| Student/learner building LLM apps | "Is my change actually better?" | A habit of testing prompts like code |

**Headline demo:** take a real feature, replay 200 saved runs on a cheaper model, and show: *"Same pass rate on 96% of cases, 60% lower cost, these 8 cases regressed, here is the diff."*

## 3. Concept

Switchcheck treats LLM calls like recorded HTTP traffic:

1. **Record**: wrap your LLM client so every call is saved (inputs, outputs, tokens, cost, latency).
2. **Replay**: rerun the saved inputs against a different model, prompt, or parameters.
3. **Check**: score each new output against the original (or against rules you define).
4. **Report**: show what regressed, what improved, and what it costs.

It is **not** an agent itself in v1. It is tooling around LLM workflows. Version 2 adds agent traces and an agent that analyses failures and proposes prompt fixes (see section 11).

## 4. Scope

### MVP (a few days)

- Python package with a drop-in client wrapper that logs calls to SQLite
- CLI: `init`, `runs`, `replay`, `report`
- Replay across models/providers via LiteLLM (one interface for many providers)
- Checkers: exact match, contains/regex, JSON-schema validity, field equality for JSON, LLM-as-judge
- Static HTML report (single file, shareable, no server)
- README with a 30-second demo GIF and a sample app

### Not in MVP (deliberately)

- Hosted dashboard, auth, multi-user, teams
- Fancy statistical scoring
- Fine-tuning, dataset management UI
- Streaming-response replay

## 5. Architecture

```
 ┌──────────────┐     wraps      ┌──────────────────────┐
 │  Your app    │ ─────────────► │  Switchcheck client  │
 │ (LLM calls)  │ ◄───────────── │  (logging wrapper)   │
 └──────────────┘    response    └──────────┬───────────┘
                                            │ write
                                            ▼
                                   ┌─────────────────┐
                                   │ SQLite store    │
                                   │ runs / replays  │
                                   └───────┬─────────┘
                                           │ read
        ┌──────────────────────────────────┼─────────────────────────────┐
        │                                  │                             │
        ▼                                  ▼                             ▼
 ┌──────────────┐   calls model   ┌────────────────┐             ┌──────────────┐
 │ Replay engine│ ───────────────►│ LiteLLM        │             │ Report       │
 │ (concurrent, │ ◄───────────────│ (any provider) │             │ generator    │
 │  rate-limited)│                └────────────────┘             │ (HTML)       │
 └──────┬───────┘                                                └──────▲───────┘
        │ outputs                                                       │
        ▼                                                               │
 ┌──────────────┐   verdicts + scores                                   │
 │ Checkers     │ ──────────────────────────────────────────────────────┘
 │ exact/regex/ │
 │ schema/judge │
 └──────────────┘

 CLI (Typer) orchestrates: init → runs → replay → report
```

### Components

| Component | Responsibility | Notes |
|---|---|---|
| **Client wrapper** | Intercept calls, time them, count tokens, save a run | Keep it a thin wrapper so users change one import line |
| **Store** | SQLite file in the project folder (`.switchcheck/db.sqlite`) | No server, easy to inspect, easy to commit or share |
| **Replay engine** | Load N runs, call target model with same inputs, save results | Async with a concurrency limit; retry with backoff |
| **Checkers** | Turn (original, replayed) into pass/fail plus a score | Pluggable; each is a small function |
| **Cost calculator** | Tokens x price per model | Prices in a local JSON file that users can update |
| **Report generator** | Render a single HTML file from a replay | Jinja2 template, inline CSS, no JS framework |
| **CLI** | User entry point | Typer for clean commands and help text |

## 6. Data model (SQLite)

```sql
-- One row per original LLM call recorded from the app
CREATE TABLE runs (
  id            TEXT PRIMARY KEY,          -- uuid
  created_at    TEXT NOT NULL,             -- ISO timestamp
  tag           TEXT,                      -- e.g. "invoice-extractor" (group runs by feature)
  model         TEXT NOT NULL,
  params_json   TEXT NOT NULL,             -- temperature, max_tokens, etc.
  messages_json TEXT NOT NULL,             -- full input messages
  tools_json    TEXT,                      -- tool definitions, if any
  output_text   TEXT,
  output_json   TEXT,                      -- raw response (tool calls etc.)
  input_tokens  INTEGER,
  output_tokens INTEGER,
  cost_usd      REAL,
  latency_ms    INTEGER,
  error         TEXT
);

-- One row per replay session (a "what if" experiment)
CREATE TABLE replays (
  id            TEXT PRIMARY KEY,
  created_at    TEXT NOT NULL,
  name          TEXT,                      -- e.g. "cheaper-model-test"
  tag           TEXT,                      -- which runs were replayed
  target_model  TEXT NOT NULL,
  prompt_override TEXT,                    -- optional new system prompt
  params_json   TEXT,
  checker_json  TEXT NOT NULL              -- which checkers were used
);

-- One row per (run, replay) pair
CREATE TABLE replay_results (
  id            TEXT PRIMARY KEY,
  replay_id     TEXT NOT NULL REFERENCES replays(id),
  run_id        TEXT NOT NULL REFERENCES runs(id),
  output_text   TEXT,
  input_tokens  INTEGER,
  output_tokens INTEGER,
  cost_usd      REAL,
  latency_ms    INTEGER,
  passed        INTEGER,                   -- 1/0
  score         REAL,                      -- 0..1 where applicable
  verdict_json  TEXT,                      -- per-checker details and reasons
  error         TEXT
);

CREATE INDEX idx_runs_tag ON runs(tag);
CREATE INDEX idx_results_replay ON replay_results(replay_id);
```

## 7. CLI design

```bash
# 1. Set up in your project
switchcheck init

# 2. In your app (Python): change one import
#    from switchcheck import client      # instead of the raw provider client
#    resp = client.chat(model="model-a", messages=[...], tag="invoice-extractor")

# 3. See what was recorded
switchcheck runs --tag invoice-extractor --limit 20

# 4. Replay on a different model
switchcheck replay \
  --tag invoice-extractor \
  --model model-b \
  --check json-schema:schema.json \
  --check judge:"Does the answer contain the same facts as the reference?" \
  --sample 200 \
  --name cheaper-model-test

# 5. Open the report
switchcheck report cheaper-model-test --open
```

Other useful commands:

- `switchcheck replay --prompt prompts/v2.txt` to test a prompt change on the same model
- `switchcheck export --tag X --format jsonl` to export runs
- `switchcheck prices` to view or edit the price table

## 8. Checkers

| Checker | Use for | How it works |
|---|---|---|
| `exact` | Classification labels, short answers | Normalised string equality with the original |
| `contains` / `regex` | Required phrases or formats | Pattern match on the new output |
| `json-schema` | Structured extraction | Validates output against a JSON Schema |
| `json-fields` | Extraction where some fields must match | Compare chosen fields to the original |
| `judge` | Free-text quality | A model grades new vs original using a rubric; returns pass/fail plus a reason |

**Judge caveats (document these in the README):**

- Use a fixed, strong judge model and a fixed rubric so results are comparable.
- Ask for a short reason with every verdict so humans can audit.
- Spot-check a sample by hand; judges can be wrong or biased toward longer answers.

## 9. Replay semantics (things that trip people up)

- **Non-determinism:** the same model can give different answers on repeated runs. Offer `--repeat N` and report agreement rate so users know the noise floor.
- **Tool calls:** in v1, replay only the first model turn and record the proposed tool calls. Full multi-step replay arrives with agent traces (v2).
- **Parameter differences:** some models ignore or reject certain parameters. Log a warning and record what was actually sent.
- **Rate limits and cost:** show an estimated cost before running (`--dry-run`) and require confirmation above a configurable threshold.
- **Privacy:** recorded runs may contain sensitive data. Keep everything local by default, add a `redact` hook for scrubbing before storage, and warn before sharing the DB or a report.

## 10. Report contents

A single static HTML file with:

1. **Summary card:** pass rate (original vs new), total cost (original vs new), p50/p95 latency, number of regressions and improvements
2. **Regression list:** cases that passed before and fail now, sorted by severity
3. **Diff view:** original output next to new output with changes highlighted
4. **Cost and latency breakdown:** per-case and aggregated
5. **Failure reasons:** judge explanations or schema errors, grouped by type
6. **Reproducibility footer:** models, params, checker config, date, Switchcheck version

## 11. Roadmap

### v1 (MVP): see section 4

### v2: agent support

- **Trace recording:** capture multi-step agent runs (each model turn, tool call, tool result)
- **Step-level replay:** replay with recorded tool results (deterministic) or live tools
- **Failure-analysis agent:** reads regressed runs, clusters failures ("fails when the tool returns empty", "ignores system prompt after step 4"), writes a diagnosis
- **Prompt-fix loop:** the agent proposes a prompt edit, Switchcheck replays it on the failing cases, and the edit is kept only if the pass rate improves
- **Sample agent** in the repo to try everything out of the box

### v3: ecosystem

- GitHub Action: run a replay on every PR that touches a prompt, and comment the result
- Adapters for common frameworks and for TypeScript
- MCP tool-call logging
- Export to common eval formats

## 12. Suggested repo structure

```
switchcheck/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/switchcheck/
│   ├── __init__.py
│   ├── client.py          # logging wrapper
│   ├── store.py           # SQLite access, migrations
│   ├── replay.py          # replay engine (async)
│   ├── checkers/
│   │   ├── __init__.py
│   │   ├── exact.py
│   │   ├── regex.py
│   │   ├── schema.py
│   │   └── judge.py
│   ├── pricing.py         # token prices, cost calculation
│   ├── report.py          # HTML generation
│   ├── templates/report.html.j2
│   └── cli.py             # Typer commands
├── examples/
│   ├── invoice_extractor/ # sample app + sample data
│   └── README.md
└── tests/
    ├── test_store.py
    ├── test_checkers.py
    ├── test_replay.py     # uses a mocked model
    └── test_report.py
```

## 13. Tech choices

| Need | Choice | Why |
|---|---|---|
| Language | Python 3.10+ | Most LLM users are already there |
| Multi-provider calls | LiteLLM | One interface for many providers |
| CLI | Typer | Clean UX, built-in help |
| Storage | SQLite | Zero setup, portable |
| Async | asyncio + a semaphore | Fast replays without hammering rate limits |
| Templates | Jinja2 | Simple static report |
| Validation | pydantic, jsonschema | Config and schema checks |
| Tests | pytest, with a fake model | No API cost in CI |
| Packaging | PyPI via pyproject | `pip install switchcheck` |

## 14. Build plan

**Day 1: Recording**
- Project skeleton, SQLite schema, `init` command
- Client wrapper that logs calls (start with one provider through LiteLLM)
- `runs` command to list recorded calls

**Day 2: Replay**
- Async replay engine with concurrency limit, retries, cost tracking
- Price table and `--dry-run` cost estimate

**Day 3: Checkers**
- exact, regex, json-schema, json-fields
- LLM judge with a rubric and reason output

**Day 4: Report**
- Jinja2 HTML report with summary, regression list and diffs
- `report --open`

**Day 5: Example app and polish**
- Invoice-extractor sample with ~50 realistic synthetic runs
- Tests with a fake model
- README, demo GIF, `pip install` flow verified in a clean environment

**Day 6 (optional): Launch**
- Publish to PyPI, tag a release
- Post: a write-up of the demo result ("same accuracy, 60% cheaper") with the GIF

## 15. Testing strategy

- **Unit tests** for each checker, the cost calculator and the store
- **Replay tests** using a fake model that returns scripted outputs (including failures and timeouts)
- **Golden-file test** for the HTML report on a fixed dataset
- **Smoke test** in CI: install the package fresh, run init, record from the sample app, replay, and report

## 16. README and demo plan

The README should open with the one-line promise, a GIF of the 5-command flow, and the headline result table:

| | Original model | Cheaper model |
|---|---|---|
| Pass rate | 97% | 95% |
| Cost per 1k runs | $X | $Y |
| p95 latency | A ms | B ms |
| Regressions | (n/a) | 8 cases, listed in the report |

Then: install, 3-minute quickstart, how checkers work, privacy notes, limits and roadmap.

## 17. Risks and how to handle them

| Risk | Mitigation |
|---|---|
| Judge model is unreliable | Fixed rubric, short reasons, hand-check samples, recommend deterministic checkers when possible |
| Replay is noisy | `--repeat N` and an agreement rate to show the noise floor |
| Sensitive data in the DB | Local by default, redaction hook, clear warnings |
| Provider differences break replay | Log what was actually sent; surface unsupported params as warnings |
| Scope creep | Hold the MVP line in section 4; everything else goes in the roadmap |
| "Another eval tool" fatigue | Lead with the concrete migration use case and the five-command flow, not the feature list |

## 18. Why this is worth building

- **Real pain, specific audience:** anyone paying for LLM calls wants to cut cost safely.
- **Small enough to finish**, useful from the first release, easy to extend.
- **Strong portfolio signal:** it shows reliability thinking, backend design (storage, async, CLI) and awareness of how LLM apps fail in practice.
- **Natural path to agents:** v2 turns it into an agent-harness project without throwing anything away.
