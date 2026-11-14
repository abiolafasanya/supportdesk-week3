"""Lesson 3.4: measure a prompt version against a labelled golden set.

  uv run python -m app.eval --prompt-version v1
  uv run python -m app.eval --prompt-version v2
  uv run python -m app.eval --compare evals/results/v1-....json evals/results/v2-....json

This makes real API calls (12 tickets, about a cent on a small model).
Each run is saved to evals/results/ so you can compare versions later.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from app.config import Settings, get_settings, has_api_key
from app.llm import make_client
from app.triage import SchemaFailure, triage_ticket

GOLDEN = Path("evals/golden.jsonl")
RESULTS_DIR = Path("evals/results")
FIELDS = ("category", "priority", "needs_human")


def load_golden(path: Path = GOLDEN) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def run_eval(client, settings: Settings, cases: list[dict]) -> dict:
    rows, cost = [], 0.0
    for case in cases:
        row = {"id": case["id"], "expect": case["expect"], "got": None, "attempts": 0, "error": None}
        try:
            outcome = triage_ticket(client, settings, case["text"], case["id"])
            got = outcome.result.model_dump()
            row.update(got={k: got.get(k) for k in FIELDS}, attempts=outcome.attempts,
                       summary=got.get("summary"))
            cost += outcome.cost
        except SchemaFailure as exc:
            row["error"] = str(exc)
        rows.append(row)
    return {"prompt_version": settings.prompt_version, "mode": settings.output_mode,
            "model": settings.model, "cost_usd": round(cost, 6), "rows": rows,
            "scores": score(rows)}


def score(rows: list[dict]) -> dict:
    n = len(rows)
    valid = [r for r in rows if r["got"]]
    scores = {"cases": n, "schema_pass_rate": round(len(valid) / n, 3) if n else 0.0}
    for f in FIELDS:
        # A field only counts if the schema says it exists for this version.
        scored = [r for r in valid if r["got"].get(f) is not None]
        if scored:
            hits = sum(r["got"][f] == r["expect"][f] for r in scored)
            scores[f"{f}_accuracy"] = round(hits / n, 3)  # failures count as wrong
    retried = sum(1 for r in rows if r["attempts"] > 1)
    scores["needed_repair"] = retried
    return scores


def print_report(report: dict) -> None:
    print(f"Prompt {report['prompt_version']} | mode {report['mode']} | {report['model']}")
    for r in report["rows"]:
        if r["error"]:
            print(f"  {r['id']}  FAIL  {r['error']}")
            continue
        misses = [f for f in FIELDS if r["got"].get(f) is not None and r["got"][f] != r["expect"][f]]
        mark = "ok  " if not misses else "MISS"
        detail = ", ".join(f"{f}={r['got'][f]} (want {r['expect'][f]})" for f in misses)
        print(f"  {r['id']}  {mark}  {detail}")
    print("Scores:", json.dumps(report["scores"]))
    print(f"Cost: ${report['cost_usd']:.6f}")


def compare(a: dict, b: dict) -> int:
    print(f"{'metric':22} {a['prompt_version']:>8} {b['prompt_version']:>8}")
    regressions = 0
    for key in sorted(set(a["scores"]) | set(b["scores"])):
        va, vb = a["scores"].get(key, "-"), b["scores"].get(key, "-")
        flag = ""
        if isinstance(va, float) and isinstance(vb, float) and vb < va:
            flag, regressions = "  <-- worse", regressions + 1
        print(f"{key:22} {str(va):>8} {str(vb):>8}{flag}")
    print(f"{'cost_usd':22} {a['cost_usd']:>8} {b['cost_usd']:>8}")
    return 1 if regressions else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate a prompt version on the golden set.")
    parser.add_argument("--prompt-version")
    parser.add_argument("--mode", choices=["native", "prompt"])
    parser.add_argument("--provider", choices=["anthropic", "openai"])
    parser.add_argument("--compare", nargs=2, metavar=("OLD.json", "NEW.json"))
    args = parser.parse_args(argv)

    if args.compare:
        old, new = (json.loads(Path(p).read_text(encoding="utf-8")) for p in args.compare)
        return compare(old, new)

    settings = get_settings(args.provider, args.prompt_version, args.mode)
    if not has_api_key(settings.provider):
        print(f"No API key for {settings.provider}. Copy .env.example to .env and add yours.")
        return 1
    report = run_eval(make_client(settings), settings, load_golden())
    print_report(report)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = RESULTS_DIR / f"{settings.prompt_version}-{settings.output_mode}-{stamp}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
