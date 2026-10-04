# Support-ticket model comparison (legacy prototype)

> This example documents the older record/replay workflow. The planned public
> MVP replaces these steps with one `switchcheck.yaml` and one
> `switchcheck test` command. Keep this example for compatibility until the new
> classification example is implemented; do not use it as the primary
> onboarding path.

This dummy application classifies five synthetic customer-support tickets. It
uses Switchcheck's `client.chat()` wrapper, so each normal model call is also
recorded locally. You can then replay exactly the same calls against another
provider and generate an HTML comparison report.

## 1. Install the project

From the repository root, activate a supported Python 3.10-3.12 environment and
install the package:

```powershell
python -m pip install -e "."
python -m pip install --upgrade "litellm>=1.101,<2"
switchcheck init
```

To verify the application without using a key or making a network request:

```powershell
python examples/support_ticket_classifier/app.py --fake
```

## 2. Record real source-model calls

For Claude Haiku, set `ANTHROPIC_API_KEY` in the current PowerShell session and
select its LiteLLM model name. Do not put the key in a source file or commit it
to Git.

```powershell
$env:ANTHROPIC_API_KEY = "your-anthropic-api-key"
python examples/support_ticket_classifier/app.py --model anthropic/claude-haiku-4-5-20251001
```

Alternatively, set `OPENAI_API_KEY` and omit `--model` to use the default
`openai/gpt-6-luna` source model. Five calls are made and stored under the tag
`support-ticket-demo`.

Inspect the recorded calls:

```powershell
switchcheck runs --tag support-ticket-demo --limit 5
```

## 3. Get a free-tier Gemini API key

Create a key in [Google AI Studio](https://aistudio.google.com/apikey), then set
it in the same terminal:

```powershell
$env:GEMINI_API_KEY = "your-gemini-api-key"
```

The Gemini free tier has provider-defined model and rate limits. This example
uses `gemini/gemini-3.1-flash-lite`, whose stable provider model ID is
`gemini-3.1-flash-lite`.

Free-tier prompts and responses may be used by the provider to improve its
products. This example contains synthetic data only; do not substitute private
customer tickets without reviewing the provider's data-use terms.

## 4. Replay the source calls with Gemini

Preview the selection without making calls:

```powershell
switchcheck replay `
  --tag support-ticket-demo `
  --limit 5 `
  --model gemini/gemini-3.1-flash-lite `
  --dry-run
```

Run the comparison:

```powershell
switchcheck replay `
  --tag support-ticket-demo `
  --limit 5 `
  --model gemini/gemini-3.1-flash-lite `
  --check json-schema:examples/support_ticket_classifier/classification.schema.json `
  --check json-field:category `
  --check json-field:priority
```

Copy the replay ID printed by that command and generate the report:

```powershell
switchcheck report --replay YOUR_REPLAY_ID
```

Open `.switchcheck/reports/YOUR_REPLAY_ID.html`. It shows the source and Gemini
outputs side by side, whether each candidate returned valid JSON, and whether
its category and priority match the recorded source result.

If you run the recorder repeatedly, Switchcheck keeps all runs. `--limit 5`
selects the five newest calls for this walkthrough.
