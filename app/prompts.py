"""Lesson 3.1 and 3.4: system prompts live in files, not in string literals.

prompts/triage/v2.md has a small header (front matter) and a body:

    ---
    id: triage
    version: v2
    schema: triage.v2
    ...
    ---
    # Role
    You are ... Allowed categories: $categories

$names are filled in from the schema, so the prompt and the schema can
never disagree. We use string.Template ($name) instead of str.format ({name})
because prompts often contain JSON examples full of { }.

  uv run python -m app.prompts                  # list versions and hashes
  uv run python -m app.prompts show v2          # print the rendered prompt
  uv run python -m app.prompts lock             # record hashes of released prompts
"""
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from string import Template

from app import schemas

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"
LOCK_FILE = PROMPT_DIR / "prompts.lock.json"
REQUIRED_KEYS = ("id", "version", "schema", "date", "owner", "changes")


@dataclass(frozen=True)
class Prompt:
    id: str
    version: str
    schema: str
    meta: dict
    template: str
    path: Path

    @property
    def sha256(self) -> str:
        # Normalise line endings so Windows (CRLF) and macOS/Linux (LF) agree.
        text = self.path.read_text(encoding="utf-8").replace("\r\n", "\n")
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]

    def render(self) -> str:
        """Fill $placeholders from the schema. Fails loudly on any unknown $name."""
        return Template(self.template).substitute(
            categories=schemas.allowed(schemas.Category),
            priorities=schemas.allowed(schemas.Priority),
            sentiments=schemas.allowed(schemas.Sentiment),
            product_areas=schemas.allowed(schemas.ProductArea),
            keys=", ".join(schemas.get_schema(self.schema).model_fields),
        )


def _parse(path: Path) -> Prompt:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path.name}: missing front matter")
    _, header, body = text.split("---", 2)
    meta = {}
    for line in header.strip().splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    missing = [k for k in REQUIRED_KEYS if not meta.get(k)]
    if missing:
        raise ValueError(f"{path.name}: front matter is missing {', '.join(missing)}")
    return Prompt(meta["id"], meta["version"], meta["schema"], meta, body.strip(), path)


def load_prompt(version: str, prompt_id: str = "triage") -> Prompt:
    path = PROMPT_DIR / prompt_id / f"{version}.md"
    if not path.exists():
        known = ", ".join(p.stem for p in sorted((PROMPT_DIR / prompt_id).glob("v*.md")))
        raise FileNotFoundError(f"No prompt '{prompt_id}/{version}'. Known versions: {known}")
    prompt = _parse(path)
    if prompt.version != version:
        raise ValueError(f"{path.name} says version {prompt.version}; file name says {version}")
    return prompt


def all_prompts(prompt_id: str = "triage") -> list[Prompt]:
    return [_parse(p) for p in sorted((PROMPT_DIR / prompt_id).glob("v*.md"))]


def ticket_message(ticket_id: str, text: str) -> str:
    """Wrap untrusted ticket text in tags. A ticket can't close the tag early."""
    safe = text.replace("</ticket>", "[/ticket]")
    return f'<ticket id="{ticket_id}">\n{safe}\n</ticket>'


def write_lock() -> dict:
    lock = {f"{p.id}/{p.version}": p.sha256 for p in all_prompts()}
    LOCK_FILE.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    return lock


def main(argv: list[str]) -> int:
    if argv[:1] == ["show"]:
        prompt = load_prompt(argv[1] if len(argv) > 1 else "v2")
        print(prompt.render())
        print("\n--- user message ---")
        print(ticket_message("T-1001", "I was charged twice for my March subscription."))
        return 0
    if argv[:1] == ["lock"]:
        for key, digest in write_lock().items():
            print(f"locked {key}  {digest}")
        return 0
    for p in all_prompts():
        print(f"{p.id}/{p.version}  schema={p.schema}  date={p.meta['date']}  sha={p.sha256}  {p.meta['changes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
