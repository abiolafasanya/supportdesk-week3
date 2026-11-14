#!/usr/bin/env bash
# Week 3 preflight checks (macOS / Linux). Run from the supportdesk folder: bash scripts/preflight.sh
ok=1
pass() { echo "[ OK ] $1"; }
fail() { echo "[FAIL] $1"; ok=0; }

command -v uv >/dev/null && pass "uv found: $(uv --version)" || fail "uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
[ -f pyproject.toml ] && pass "pyproject.toml found" || fail "Run this from the supportdesk folder"
[ -f .env ] && pass ".env exists" || fail ".env missing. Run: cp .env.example .env and add your key"
if [ -d .git ]; then
  [ "$(git check-ignore .env)" = ".env" ] && pass ".env is git-ignored" || fail ".env is NOT ignored by git"
fi
uv sync --quiet && pass "dependencies installed" || fail "uv sync failed"
check=$(uv run python -c "from app.config import get_settings, has_api_key; s = get_settings(); print(s.provider, s.model, has_api_key(s.provider), s.prompt_version, s.output_mode)") || fail "could not read settings"
set -- $check
[ "$3" = "True" ] && pass "provider $1, model $2, API key present, prompt $4, mode $5" || fail "provider $1 selected but its API key is empty in .env"
uv run python -m app.prompts && pass "prompt files load" || fail "a prompt file is broken"
uv run python -m pytest -q && pass "offline tests pass" || fail "tests failed"
[ $ok = 1 ] && echo "All checks passed." || echo "Fix the FAIL lines above, then run again."
