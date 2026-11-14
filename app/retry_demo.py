"""Lesson 3.3 live demo: validation and repair, with no API key and no network.

A scripted fake model makes two classic mistakes, then fixes them when told
exactly what was wrong. Run it and watch each attempt.

  uv run python -m app.retry_demo            # breaks two business rules, then repairs
  uv run python -m app.retry_demo --stubborn # summary too long twice: schema failure
"""
import json
import sys
from types import SimpleNamespace

from app.config import Settings
from app.triage import SchemaFailure, triage_ticket

BAD = json.dumps({
    "reason": "Many agents are locked out.", "category": "technical", "product_area": "login",
    "priority": "urgent", "sentiment": "frustrated", "needs_human": False,
    "summary": "40 agents locked out since 9am; contact ops@acme-example.com",
})
TOO_LONG = json.dumps({
    "reason": "Many agents are locked out.", "category": "technical", "product_area": "login",
    "priority": "urgent", "sentiment": "frustrated", "needs_human": True,
    "summary": "None of the 40 agents at the customer's company have been able to log in to SupportDesk since"
               " 9am this morning, and they are very worried",
})
GOOD = json.dumps({
    "reason": "Many agents are locked out, which blocks work right now.", "category": "technical",
    "product_area": "login", "priority": "urgent", "sentiment": "frustrated", "needs_human": True,
    "summary": "None of the 40 agents can log in since 9am.",
})


class ScriptedModel:
    """Looks like anthropic.Anthropic() to our code, but replies from a script."""

    def __init__(self, *replies):
        self.replies, self.messages = list(replies), self

    def create(self, **kwargs):
        sent = kwargs["messages"]
        print(f"\n--- attempt {len(sent) // 2 + 1}: sending {len(sent)} message(s) ---")
        if len(sent) > 1:
            print("Repair message we sent:\n" + sent[-1]["content"])
        text = self.replies.pop(0)
        print("Model replied:\n" + text)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)],
                               usage=SimpleNamespace(input_tokens=900, output_tokens=90),
                               stop_reason="end_turn")


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    replies = (TOO_LONG, TOO_LONG) if "--stubborn" in argv else (BAD, GOOD)
    settings = Settings("anthropic", "claude-haiku-5-5", 1024, "v2", "native")
    import app.triage as triage
    triage.log_usage = lambda *a, **k: None   # demo only: don't write to usage.csv
    try:
        outcome = triage_ticket(ScriptedModel(*replies), settings,
                                "URGENT: none of our 40 agents can log in since 9am.", "T-1004")
    except SchemaFailure as exc:
        print(f"\nSCHEMA FAILURE (exit code 3): {exc}")
        return 3
    print(f"\nVALID after {outcome.attempts} attempts:")
    print(outcome.result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
