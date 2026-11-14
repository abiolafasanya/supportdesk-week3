import pytest

from app.pricing import estimate_cost


def test_haiku_cost():
    # 1,000 input tokens at $0.10/M + 200 output tokens at $0.50/M
    assert estimate_cost("claude-haiku-5-5", 1_000, 200) == pytest.approx(0.0002)


def test_output_tokens_cost_more_than_input():
    assert estimate_cost("gpt-6-luna", 0, 1_000) > estimate_cost("gpt-6-luna", 1_000, 0)


def test_unknown_model_is_an_error():
    with pytest.raises(KeyError):
        estimate_cost("mystery-model", 1, 1)
