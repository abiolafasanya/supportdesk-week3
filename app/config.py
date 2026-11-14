"""Settings loaded from .env. Never print the key itself."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

OUTPUT_MODES = ("native", "prompt")


@dataclass(frozen=True)
class Settings:
    provider: str
    model: str
    max_output_tokens: int
    prompt_version: str = "v2"
    output_mode: str = "native"


def get_settings(provider: str | None = None, prompt_version: str | None = None,
                 output_mode: str | None = None) -> Settings:
    provider = (provider or os.getenv("LLM_PROVIDER", "anthropic")).lower()
    if provider == "anthropic":
        model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5")
    elif provider == "openai":
        model = os.getenv("OPENAI_MODEL", "gpt-6-luna")
    else:
        raise ValueError(f"Unknown LLM_PROVIDER '{provider}'. Use anthropic or openai.")
    mode = (output_mode or os.getenv("OUTPUT_MODE", "native")).lower()
    if mode not in OUTPUT_MODES:
        raise ValueError(f"Unknown OUTPUT_MODE '{mode}'. Use native or prompt.")
    return Settings(
        provider=provider,
        model=model,
        max_output_tokens=int(os.getenv("MAX_OUTPUT_TOKENS", "1024")),
        prompt_version=prompt_version or os.getenv("PROMPT_VERSION", "v2"),
        output_mode=mode,
    )


def has_api_key(provider: str) -> bool:
    name = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
    return bool(os.getenv(name))


def health() -> dict:
    return {"status": "ok"}
