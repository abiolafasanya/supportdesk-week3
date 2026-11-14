# Prompt changelog

Released prompt files are never edited. To change a prompt, copy it to the next
version, edit the copy, run the eval, and record the result here.
`tests/test_prompts.py` fails if a released file changes without a new version.

| Version | Date | Schema | Change | Eval (golden set, 12 tickets) |
|---|---|---|---|---|
| triage/v1 | 2026-10-31 | triage.v1 | Week 2 prompt moved into a file unchanged | Fill in after `uv run python -m app.eval --prompt-version v1` |
| triage/v2 | 2026-11-13 | triage.v2 | New fields, priority rules, ticket in tags, two examples | Fill in after `uv run python -m app.eval --prompt-version v2` |
