"""Append one row per API call to logs/usage.csv so you can see spend over time.

Week 3 adds prompt_version, mode and attempt, so you can compare prompts by cost.
If an older usage.csv has a different header, it is renamed, not mixed.
"""
import csv
from datetime import datetime, timezone
from pathlib import Path

LOG_FILE = Path("logs/usage.csv")
FIELDS = ["time", "provider", "model", "prompt_version", "mode", "attempt",
          "input_tokens", "output_tokens", "cost_usd", "outcome"]


def _rotate_if_old(path: Path) -> None:
    if not path.exists():
        return
    with path.open(newline="") as f:
        header = next(csv.reader(f), [])
    if header != FIELDS:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path.rename(path.with_name(f"{path.stem}-old-{stamp}{path.suffix}"))


def log_usage(provider, model, input_tokens, output_tokens, cost_usd, outcome="ok",
              prompt_version="", mode="", attempt=1, path=LOG_FILE):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _rotate_if_old(path)
    is_new = not path.exists()
    with path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow({
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "provider": provider,
            "model": model,
            "prompt_version": prompt_version,
            "mode": mode,
            "attempt": attempt,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": f"{cost_usd:.6f}",
            "outcome": outcome,
        })


def total_spend(path=LOG_FILE) -> float:
    path = Path(path)
    if not path.exists():
        return 0.0
    with path.open() as f:
        return sum(float(row["cost_usd"]) for row in csv.DictReader(f))
