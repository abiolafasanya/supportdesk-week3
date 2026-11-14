"""Week 3 reference: SupportDesk ticket-triage CLI with structured output.

  uv run python -m app.triage "I was charged twice for March"
  uv run python -m app.triage "I was charged twice for March" --json
  uv run python -m app.triage --file data/tickets.json --json --out logs/results.jsonl
  uv run python -m app.triage --prompt-version v1 --mode prompt "App crashes on Reports"

--json prints one JSON object per ticket on stdout (JSON Lines) and sends
everything else (progress, totals, errors) to stderr, so the output can be
piped into another program.

Exit codes: 0 ok, 1 invalid input, 2 provider error, 3 schema failure.
In a batch, invalid input and schema failures are recorded and the run
continues; the exit code is the highest one seen. A provider error stops the run.
"""
import argparse
import json
import sys
from dataclasses import dataclass, field

from pydantic import BaseModel

from app.config import Settings, get_settings, has_api_key
from app.errors import friendly_error
from app.llm import complete, make_client
from app.pricing import estimate_cost, format_cost
from app.prompts import load_prompt, ticket_message
from app.schemas import get_schema
from app.usage_log import log_usage
from app.validation import ReplyInvalid, repair_message, validate_reply

MAX_TICKET_CHARS = 2000
MAX_ATTEMPTS = 2  # bounded: the first try plus ONE repair attempt


class SchemaFailure(Exception):
    pass


@dataclass
class Outcome:
    result: BaseModel
    attempts: int
    cost: float
    prompt_version: str
    schema: str
    history: list = field(default_factory=list)  # every reply, for debugging


def validate_ticket(text: str) -> str:
    text = (text or "").strip()
    if not text:
        raise ValueError("Ticket text is empty.")
    if len(text) > MAX_TICKET_CHARS:
        raise ValueError(f"Ticket is longer than {MAX_TICKET_CHARS} characters.")
    return text


def triage_ticket(client, settings: Settings, text: str, ticket_id: str = "cli") -> Outcome:
    """Call the model, validate, and repair once if needed."""
    prompt = load_prompt(settings.prompt_version)
    schema = get_schema(prompt.schema)
    system = prompt.render()
    native = schema if settings.output_mode == "native" else None
    messages = [{"role": "user", "content": ticket_message(ticket_id, text)}]

    total_cost, history, problems = 0.0, [], []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        reply = complete(client, settings, system, messages, schema=native)
        cost = estimate_cost(settings.model, reply.usage.input_tokens, reply.usage.output_tokens)
        total_cost += cost
        history.append(reply.text)

        def log(outcome):
            log_usage(settings.provider, settings.model, reply.usage.input_tokens,
                      reply.usage.output_tokens, cost, outcome,
                      prompt.version, settings.output_mode, attempt)

        if reply.stop_reason == "refusal":       # retrying a refusal won't help
            log("refusal")
            raise SchemaFailure("The model declined to answer this ticket.")
        if reply.stop_reason == "max_tokens":    # same cap, same result: don't retry
            log("truncated")
            raise SchemaFailure("Reply was cut off at MAX_OUTPUT_TOKENS. Raise it in .env.")
        try:
            result = validate_reply(reply.text, schema)
        except ReplyInvalid as exc:
            problems = exc.problems
            log(f"invalid_attempt_{attempt}")
            # Repair: show the model its own reply and exactly what was wrong.
            messages = messages + [
                {"role": "assistant", "content": reply.text},
                {"role": "user", "content": repair_message(problems)},
            ]
            continue
        log("ok")
        return Outcome(result, attempt, total_cost, prompt.version, prompt.schema, history)

    raise SchemaFailure(f"Reply failed validation {MAX_ATTEMPTS} times: {'; '.join(problems)}")


def envelope(ticket_id: str, settings: Settings, status: str, outcome: Outcome | None = None,
             error: str | None = None) -> dict:
    """The machine-readable record printed by --json. Stable keys: other tools rely on them."""
    record = {"ticket_id": ticket_id, "status": status}
    if outcome:
        record["result"] = outcome.result.model_dump()
    if error:
        record["error"] = error
    record["meta"] = {
        "prompt_version": outcome.prompt_version if outcome else settings.prompt_version,
        "schema": outcome.schema if outcome else None,
        "mode": settings.output_mode,
        "provider": settings.provider,
        "model": settings.model,
        "attempts": outcome.attempts if outcome else None,
        "cost_usd": round(outcome.cost, 6) if outcome else None,
    }
    return record


def human_line(ticket_id: str, outcome: Outcome) -> str:
    r = outcome.result.model_dump()
    tags = f"{r['category']}/{r['priority']}"
    if "needs_human" in r:
        tags += "  needs_human" if r["needs_human"] else ""
    tries = "1 attempt" if outcome.attempts == 1 else f"{outcome.attempts} attempts"
    return (f"[{ticket_id}] {tags}  \"{r['summary']}\"  "
            f"({format_cost(outcome.cost)}, {tries}, prompt {outcome.prompt_version})")


def main(argv=None, client=None) -> int:
    parser = argparse.ArgumentParser(description="Triage SupportDesk tickets with an LLM.")
    parser.add_argument("ticket", nargs="?", help="ticket text")
    parser.add_argument("--file", help="JSON file with a list of {id, text} tickets")
    parser.add_argument("--provider", choices=["anthropic", "openai"])
    parser.add_argument("--prompt-version", help="prompt file to use, e.g. v1 or v2 (default: .env)")
    parser.add_argument("--mode", choices=["native", "prompt"], help="structured output mode (default: .env)")
    parser.add_argument("--json", action="store_true", help="print JSON Lines on stdout")
    parser.add_argument("--out", help="also append JSON Lines to this file")
    args = parser.parse_args(argv)

    settings = get_settings(args.provider, args.prompt_version, args.mode)
    say = (lambda msg: print(msg, file=sys.stderr)) if args.json else print

    try:
        load_prompt(settings.prompt_version)
    except (FileNotFoundError, ValueError) as exc:
        say(f"Prompt problem: {exc}")
        return 1
    if client is None and not has_api_key(settings.provider):
        say(f"No API key for {settings.provider}. Copy .env.example to .env and add yours.")
        return 1

    if args.file:
        with open(args.file, encoding="utf-8") as f:
            tickets = json.load(f)
    else:
        tickets = [{"id": "cli", "text": args.ticket}]

    client = client or make_client(settings)
    out_file = open(args.out, "a", encoding="utf-8") if args.out else None
    grand_total, worst = 0.0, 0

    def emit(record: dict):
        line = json.dumps(record)  # ASCII-safe: Windows pipes are not always UTF-8
        if args.json:
            print(line)
        if out_file:
            out_file.write(line + "\n")

    try:
        for ticket in tickets:
            tid = ticket.get("id", "?")
            try:
                text = validate_ticket(ticket.get("text"))
                outcome = triage_ticket(client, settings, text, tid)
            except ValueError as exc:
                say(f"[{tid}] invalid input: {exc}")
                emit(envelope(tid, settings, "invalid_input", error=str(exc)))
                worst = max(worst, 1)
                continue
            except SchemaFailure as exc:
                say(f"[{tid}] schema failure: {exc}")
                emit(envelope(tid, settings, "schema_failure", error=str(exc)))
                worst = max(worst, 3)
                continue
            except Exception as exc:
                message, _ = friendly_error(exc)
                say(f"[{tid}] provider error: {message}")
                emit(envelope(tid, settings, "provider_error", error=message))
                return 2
            grand_total += outcome.cost
            emit(envelope(tid, settings, "ok", outcome))
            if not args.json:
                print(human_line(tid, outcome))
    finally:
        if out_file:
            out_file.close()

    say(f"Total: {format_cost(grand_total)} on {settings.provider}/{settings.model}, "
        f"prompt {settings.prompt_version}, mode {settings.output_mode}")
    return worst


if __name__ == "__main__":
    sys.exit(main())
