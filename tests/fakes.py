"""Fake SDK clients: free, fast, no key, no network."""
import json
from types import SimpleNamespace


def triage_json(**overrides) -> str:
    data = {"reason": "Customer was billed twice.", "category": "billing", "product_area": "billing",
            "priority": "normal", "sentiment": "neutral", "needs_human": True,
            "summary": "Customer was charged twice in March."}
    data.update(overrides)
    return json.dumps(data)


class FakeAnthropic:
    """Returns the given replies in order, like client.messages.create would. Records every call."""

    def __init__(self, *replies, stop_reason="end_turn"):
        self.replies = list(replies)
        self.calls = []
        self.stop_reason = stop_reason
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self.replies.pop(0))],
            usage=SimpleNamespace(input_tokens=900, output_tokens=80),
            stop_reason=self.stop_reason,
        )


class FakeOpenAI:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []
        self.responses = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            output_text=self.replies.pop(0), output=[], status="completed",
            usage=SimpleNamespace(input_tokens=900, output_tokens=80),
        )


class ByTicket(FakeAnthropic):
    """Answers each golden ticket from a lookup table keyed by ticket id."""

    def __init__(self, answers: dict[str, str]):
        super().__init__()
        self.answers = answers

    def create(self, **kwargs):
        self.calls.append(kwargs)
        first = kwargs["messages"][0]["content"]
        ticket_id = first.split('id="')[1].split('"')[0]
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self.answers[ticket_id])],
            usage=SimpleNamespace(input_tokens=900, output_tokens=80),
            stop_reason="end_turn",
        )
