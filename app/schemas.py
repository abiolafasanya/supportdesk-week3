"""Lesson 3.2: the shapes we ask the model to return.

One Pydantic class per schema version. The class is the single source of
truth: the prompt lists its allowed values, the API receives its JSON
Schema, and our code validates every reply against it.

  uv run python -m app.schemas            # show the JSON Schema for triage.v2
  uv run python -m app.schemas triage.v1
"""
import copy
import json
import sys
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

Category = Literal["billing", "technical", "account", "other"]
Priority = Literal["low", "normal", "urgent"]
Sentiment = Literal["positive", "neutral", "frustrated", "angry"]
ProductArea = Literal["billing", "login", "mobile_app", "web_app", "reports", "integrations", "unknown"]


# Week 2 shape: three fields. (No docstrings on these classes: Pydantic would
# send them to the model as the schema's description.)
class TriageV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Category
    priority: Priority
    summary: str = Field(min_length=1, max_length=120)


# Week 3 shape. Field order matters: the model writes `reason` first,
# so it explains before it decides.
class TriageV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=200,
                        description="One short sentence: why this category and priority.")
    category: Category = Field(description="Which team owns the ticket.")
    product_area: ProductArea = Field(description="Part of the product affected. Use unknown if unclear.")
    priority: Priority = Field(description="urgent = many users blocked, money lost now, or a security risk.")
    sentiment: Sentiment = Field(description="The customer's tone.")
    needs_human: bool = Field(description="True if a person must handle it: refunds, legal, security, "
                                          "outages, angry customers, or anything unclear.")
    summary: str = Field(min_length=1, max_length=120,
                         description="One neutral sentence. No names, emails or phone numbers.")


SCHEMAS: dict[str, type[BaseModel]] = {
    "triage.v1": TriageV1,
    "triage.v2": TriageV2,
}


def get_schema(name: str) -> type[BaseModel]:
    if name not in SCHEMAS:
        raise KeyError(f"Unknown schema '{name}'. Known: {', '.join(SCHEMAS)}")
    return SCHEMAS[name]


def allowed(literal) -> str:
    """'billing, technical, account, other' from a Literal type, for prompts."""
    return ", ".join(get_args(literal))


# What the APIs accept ----------------------------------------------------
# Structured outputs support enum, required and additionalProperties: false,
# but NOT minLength / maxLength / minimum / maximum. The Anthropic SDK's
# transform_schema() moves those into the description for you; this helper
# does the same so both providers get a schema they accept. We still enforce
# the real limits ourselves with Pydantic after the reply arrives.
UNSUPPORTED = ("minLength", "maxLength", "minimum", "maximum", "exclusiveMinimum",
               "exclusiveMaximum", "multipleOf", "minItems", "maxItems", "pattern")


def api_schema(model: type[BaseModel]) -> dict:
    schema = copy.deepcopy(model.model_json_schema())

    def clean(node):
        if isinstance(node, dict):
            moved = {k: node.pop(k) for k in UNSUPPORTED if k in node}
            node.pop("title", None)
            if moved:
                note = ", ".join(f"{k}: {v}" for k, v in moved.items())
                node["description"] = (node.get("description", "") + f" ({note})").strip()
            for value in node.values():
                clean(value)
        elif isinstance(node, list):
            for item in node:
                clean(item)

    clean(schema)
    return schema


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "triage.v2"
    print(json.dumps(api_schema(get_schema(name)), indent=2))
