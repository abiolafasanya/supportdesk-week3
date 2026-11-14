# SupportDesk (Week 3 demo)

The Week 2 ticket-triage CLI, upgraded with prompt files, a richer JSON schema,
native structured outputs, validation with one repair attempt, prompt tests and
an evaluation script. Fictional data only.

## Setup (Windows PowerShell)

```powershell
Copy-Item .env.example .env
notepad .env                 # add your own key, choose LLM_PROVIDER
uv sync
uv run python -m pytest      # 51 offline tests, no key needed
```

## Run

```powershell
# Look inside (offline)
uv run python -m app.prompts                 # list prompt versions and hashes
uv run python -m app.prompts show v2         # the rendered system prompt + user message
uv run python -m app.schemas                 # the JSON Schema sent to the API
uv run python -m app.retry_demo              # validation + repair with a scripted fake model
uv run python -m app.retry_demo --stubborn   # ends in a schema failure (exit code 3)

# Real calls (need a key)
uv run python -m app.triage "I was charged twice for March"
uv run python -m app.triage "I was charged twice for March" --json
uv run python -m app.triage --file data\tickets.json --json --out logs\results.jsonl
uv run python -m app.triage --prompt-version v1 --mode prompt "App crashes on Reports"
uv run python -m app.eval --prompt-version v1
uv run python -m app.eval --prompt-version v2
uv run python -m app.eval --compare evals\results\<v1 file>.json evals\results\<v2 file>.json
```

Read one result in PowerShell:

```powershell
$r = uv run python -m app.triage "Nobody can log in" --json | ConvertFrom-Json
$r.result.priority
```

Exit codes: 0 ok, 1 invalid input or missing key, 2 provider error, 3 schema failure.
Every call is logged to `logs/usage.csv` with the prompt version, mode and attempt number.

## Where things live

| Path | Lesson | What it does |
|---|---|---|
| `prompts/triage/v1.md`, `v2.md` | 3.1, 3.4 | System prompts as versioned files with front matter |
| `prompts/prompts.lock.json`, `prompts/CHANGELOG.md` | 3.4 | Hashes of released prompts; what changed and why |
| `app/prompts.py` | 3.1 | Loads a prompt, fills `$placeholders` from the schema, wraps the ticket in tags |
| `app/schemas.py` | 3.2 | `TriageV1`, `TriageV2` and `api_schema()` |
| `app/llm.py` | 3.2 | `complete(..., schema=)` turns on native structured outputs for both SDKs |
| `app/validation.py` | 3.3 | Syntax, schema and business-rule checks; the repair message |
| `app/triage.py` | 3.3, 3.5 | The CLI: bounded repair loop, `--json`, `--out`, `--prompt-version`, `--mode` |
| `evals/golden.jsonl`, `app/eval.py` | 3.4 | 12 labelled tickets and the scoring script |
| `tests/` | 3.3–3.5 | Offline tests with fake clients |
