"""Lesson 3.3: the three layers, tested without any model."""
import pytest

from app.schemas import TriageV2
from app.validation import ReplyInvalid, check_rules, repair_message, validate_reply
from tests.fakes import triage_json


def test_layer1_not_json():
    with pytest.raises(ReplyInvalid):
        validate_reply("Sure! Here is the triage you asked for.", TriageV2)


def test_code_fences_are_tolerated():
    assert validate_reply(f"```json\n{triage_json()}\n```", TriageV2).category == "billing"


@pytest.mark.parametrize("override, field", [
    ({"category": "refunds"}, "category"),
    ({"summary": "x" * 121}, "summary"),
    ({"needs_human": "maybe"}, "needs_human"),
])
def test_layer2_schema(override, field):
    with pytest.raises(ReplyInvalid) as info:
        validate_reply(triage_json(**override), TriageV2)
    assert info.value.problems[0].startswith(field)


def test_layer2_extra_keys_are_rejected():
    with pytest.raises(ReplyInvalid):
        validate_reply(triage_json(confidence=0.9), TriageV2)


def test_layer3_urgent_needs_a_human():
    result = TriageV2.model_validate_json(triage_json(priority="urgent", needs_human=False))
    assert check_rules(result) == ["priority is urgent, so needs_human must be true"]


@pytest.mark.parametrize("summary", ["Email me at dana@example.com", "Call +44 7700 900123 today"])
def test_layer3_no_contact_details_in_summary(summary):
    result = TriageV2.model_validate_json(triage_json(summary=summary))
    assert check_rules(result)


def test_repair_message_lists_every_problem():
    msg = repair_message(["a is wrong", "b is wrong"])
    assert "- a is wrong" in msg and "- b is wrong" in msg and "only the corrected JSON" in msg
