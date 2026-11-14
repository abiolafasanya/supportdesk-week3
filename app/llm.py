"""One small wrapper so the rest of SupportDesk does not care which provider it uses.

complete()  returns the whole answer at once. Pass `schema` to switch on the
            provider's native structured outputs (Week 3).
stream()    yields text as it arrives, then the final Usage (Week 2).

Every Reply carries a normalised stop_reason: "end", "max_tokens" or "refusal".
"""
from collections.abc import Iterator
from dataclasses import dataclass

from pydantic import BaseModel

from app.config import Settings
from app.schemas import api_schema


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int


@dataclass
class Reply:
    text: str
    usage: Usage
    stop_reason: str


def make_client(settings: Settings, max_retries: int = 2, timeout: float = 30.0):
    """The SDKs retry 408/409/429/5xx and connection errors for you (default 2 retries)."""
    if settings.provider == "anthropic":
        import anthropic
        return anthropic.Anthropic(max_retries=max_retries, timeout=timeout)
    from openai import OpenAI
    return OpenAI(max_retries=max_retries, timeout=timeout)


def complete(client, settings: Settings, system: str, messages: list[dict],
             schema: type[BaseModel] | None = None) -> Reply:
    """messages: [{"role": "user"|"assistant", "content": "..."}, ...]"""
    if settings.provider == "anthropic":
        extra = {}
        if schema is not None:
            # Native structured outputs: the API only produces JSON matching this schema.
            extra["output_config"] = {"format": {"type": "json_schema", "schema": api_schema(schema)}}
        r = client.messages.create(
            model=settings.model,
            max_tokens=settings.max_output_tokens,
            system=system,
            messages=messages,
            **extra,
        )
        text = "".join(b.text for b in r.content if b.type == "text")
        stop = {"end_turn": "end", "max_tokens": "max_tokens", "refusal": "refusal"}.get(r.stop_reason, "end")
        return Reply(text, Usage(r.usage.input_tokens, r.usage.output_tokens), stop)

    extra = {}
    if schema is not None:
        extra["text"] = {"format": {"type": "json_schema", "name": schema.__name__.lower(),
                                    "strict": True, "schema": api_schema(schema)}}
    r = client.responses.create(
        model=settings.model,
        max_output_tokens=settings.max_output_tokens,
        instructions=system,
        input=messages,
        **extra,
    )
    stop = "end"
    if r.status == "incomplete":
        stop = "max_tokens"
    for item in getattr(r, "output", None) or []:
        for part in getattr(item, "content", None) or []:
            if getattr(part, "type", "") == "refusal":
                stop = "refusal"
    return Reply(r.output_text, Usage(r.usage.input_tokens, r.usage.output_tokens), stop)


def stream(client, settings: Settings, system: str, user: str) -> Iterator[str | Usage]:
    """Yield text chunks as they arrive; the last item yielded is a Usage."""
    if settings.provider == "anthropic":
        with client.messages.stream(
            model=settings.model,
            max_tokens=settings.max_output_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        ) as s:
            for text in s.text_stream:
                yield text
            final = s.get_final_message()
        yield Usage(final.usage.input_tokens, final.usage.output_tokens)
        return

    events = client.responses.create(
        model=settings.model,
        max_output_tokens=settings.max_output_tokens,
        instructions=system,
        input=user,
        stream=True,
    )
    for event in events:
        if event.type == "response.output_text.delta":
            yield event.delta
        elif event.type == "response.completed":
            u = event.response.usage
            yield Usage(u.input_tokens, u.output_tokens)
