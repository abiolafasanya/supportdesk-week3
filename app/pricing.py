"""Lesson 2.5: turn token counts into money.

Prices are US dollars per 1 million tokens, standard tier, checked on
31 October 2026 from the official pricing pages. Prices change: check
platform.claude.com/docs/en/about-claude/pricing and
developers.openai.com/api/docs/pricing before you rely on them.
"""

PRICES_PER_MTOK = {
    # model:              (input, output)
    "claude-opus-5-5":    (4.00, 20.00),
    "claude-sonnet-5-5":  (2.00, 10.00),
    "claude-haiku-5-5":   (0.10, 0.50),   # prompts up to 100K tokens
    "gpt-6-astra":        (10.00, 50.00),
    "gpt-6.1-sol":        (2.00, 10.00),
    "gpt-6.1-terra":      (1.00, 5.00),
    "gpt-6-luna":         (0.10, 0.50),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return the cost in dollars for one call."""
    if model not in PRICES_PER_MTOK:
        raise KeyError(f"No price for '{model}'. Add it to PRICES_PER_MTOK.")
    input_price, output_price = PRICES_PER_MTOK[model]
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000


def format_cost(dollars: float) -> str:
    return f"${dollars:.6f}"
