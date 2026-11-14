"""Lesson 3.3: validation and the one-repair rule, with a fake client."""

import pytest

from app import triage
from app.config import Settings
from tests.fakes import FakeAnthropic, FakeOpenAI, triage_json

V2 = Settings("anthropic", "claude-haiku-5-5", 1024, "v2", "native")
V1_PROMPT_MODE = Settings("anthropic", "claude-haiku-5-5", 1024, "v1", "prompt")


def test_valid_result_first_time():
    client = FakeAnthropic(triage_json())
    outcome = triage.triage_ticket(client, V2, "charged twice")
    assert outcome.result.category == "billing"
    assert outcome.attempts == 1 and outcome.cost > 0
    assert len(client.calls) == 1


def test_native_mode_sends_json_schema():
    client = FakeAnthropic(triage_json())
    triage.triage_ticket(client, V2, "charged twice")
    fmt = client.calls[0]["output_config"]["format"]
    assert fmt["type"] == "json_schema"
    assert fmt["schema"]["additionalProperties"] is False
    summary = fmt["schema"]["properties"]["summary"]
    assert "maxLength" not in summary and "maxLength: 120" in summary["description"]


def test_prompt_mode_sends_no_schema_and_v1_has_three_fields():
    client = FakeAnthropic('{"category": "billing", "priority": "low", "summary": "Invoice question."}')
    outcome = triage.triage_ticket(client, V1_PROMPT_MODE, "invoice?")
    assert "output_config" not in client.calls[0]
    assert set(outcome.result.model_dump()) == {"category", "priority", "summary"}


def test_openai_native_mode_uses_strict_text_format():
    client = FakeOpenAI(triage_json())
    settings = Settings("openai", "gpt-6-luna", 1024, "v2", "native")
    triage.triage_ticket(client, settings, "charged twice")
    fmt = client.calls[0]["text"]["format"]
    assert fmt["type"] == "json_schema" and fmt["strict"] is True


def test_ticket_is_wrapped_in_tags():
    client = FakeAnthropic(triage_json())
    triage.triage_ticket(client, V2, "charged twice", "T-9")
    assert client.calls[0]["messages"][0]["content"].startswith('<ticket id="T-9">')


def test_repair_sends_the_problems_back():
    bad = triage_json(priority="urgent", needs_human=False)
    client = FakeAnthropic(bad, triage_json())
    outcome = triage.triage_ticket(client, V2, "everyone is locked out")
    assert outcome.attempts == 2
    second = client.calls[1]["messages"]
    assert [m["role"] for m in second] == ["user", "assistant", "user"]
    assert second[1]["content"] == bad
    assert "needs_human must be true" in second[2]["content"]


def test_schema_failure_after_two_attempts():
    client = FakeAnthropic(triage_json(category="refunds"), triage_json(category="refunds"))
    with pytest.raises(triage.SchemaFailure):
        triage.triage_ticket(client, V2, "x")
    assert len(client.calls) == triage.MAX_ATTEMPTS == 2


def test_refusal_is_not_retried():
    client = FakeAnthropic("", stop_reason="refusal")
    with pytest.raises(triage.SchemaFailure, match="declined"):
        triage.triage_ticket(client, V2, "x")
    assert len(client.calls) == 1


def test_truncated_reply_is_not_retried():
    client = FakeAnthropic('{"reason": "Cut o', stop_reason="max_tokens")
    with pytest.raises(triage.SchemaFailure, match="MAX_OUTPUT_TOKENS"):
        triage.triage_ticket(client, V2, "x")
    assert len(client.calls) == 1


@pytest.mark.parametrize("bad", ["", "   ", "x" * 2001])
def test_invalid_input_is_rejected_before_any_call(bad):
    with pytest.raises(ValueError):
        triage.validate_ticket(bad)
