# Week 3 preflight checks (Windows PowerShell)
# Run from the supportdesk folder:  .\scripts\preflight.ps1
# If PowerShell blocks scripts:  powershell -ExecutionPolicy Bypass -File .\scripts\preflight.ps1

$ok = $true
function Pass($msg) { Write-Host "[ OK ] $msg" -ForegroundColor Green }
function Fail($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red; $script:ok = $false }

if (Get-Command uv -ErrorAction SilentlyContinue) { Pass "uv found: $(uv --version)" }
else { Fail "uv not found. Install: powershell -ExecutionPolicy ByPass -c `"irm https://astral.sh/uv/install.ps1 | iex`" then reopen the terminal" }

if (Test-Path .\pyproject.toml) { Pass "pyproject.toml found (you are in the project folder)" }
else { Fail "Run this from the supportdesk folder" }

if (Test-Path .\.env) { Pass ".env exists" }
else { Fail ".env missing. Run: Copy-Item .env.example .env ; notepad .env" }

if ((git check-ignore .env 2>$null) -eq ".env") { Pass ".env is git-ignored" }
elseif (Test-Path .\.git) { Fail ".env is NOT ignored by git. Check .gitignore" }
else { Write-Host "[INFO] Not a git repo yet; skipping the .gitignore check" }

uv sync --quiet
if ($LASTEXITCODE -eq 0) { Pass "dependencies installed (uv sync)" } else { Fail "uv sync failed" }

# Checks whether a key is present WITHOUT printing it
$check = uv run python -c "from app.config import get_settings, has_api_key; s = get_settings(); print(s.provider, s.model, has_api_key(s.provider), s.prompt_version, s.output_mode)"
if ($LASTEXITCODE -eq 0) {
    $parts = $check.Trim().Split(" ")
    if ($parts[2] -eq "True") { Pass "provider $($parts[0]), model $($parts[1]), API key present, prompt $($parts[3]), mode $($parts[4])" }
    else { Fail "provider $($parts[0]) selected but its API key is empty in .env" }
} else { Fail "could not read settings from .env" }

uv run python -m app.prompts
if ($LASTEXITCODE -eq 0) { Pass "prompt files load (see the list above)" } else { Fail "a prompt file is broken" }

uv run python -m pytest -q
if ($LASTEXITCODE -eq 0) { Pass "offline tests pass" } else { Fail "tests failed" }

if ($ok) { Write-Host "`nAll checks passed. Next: uv run python -m app.retry_demo (offline), then uv run python -m app.triage --file data\tickets.json" -ForegroundColor Green }
else { Write-Host "`nFix the FAIL lines above, then run this again." -ForegroundColor Yellow }
