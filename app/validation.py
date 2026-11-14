"""Lesson 3.3: three layers of checks on every reply.

  1. Syntax   - is it JSON at all?            (json / Pydantic)
  2. Schema   - right keys, types and values?  (Pydantic model)
  3. Rules    - does it make business sense?   (plain Python, below)

Native structured outputs make layers 1 and 2 almost always pass, but the
API cannot check length limits or rules like "urgent needs a human", so we
always run all three.
"""
import re

from pydantic import BaseModel, ValidationError

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")


class ReplyInvalid(Exception):
    """The reply failed a check. `problems` is a list of short, fixable messages."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def strip_fences(raw: str) -> str:
    return raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()


def check_rules(result: BaseModel) -> list[str]:
    """Business rules JSON Schema can't express. Return [] when all is well."""
    problems = []
    data = result.model_dump()
    if data.get("priority") == "urgent" and data.get("needs_human") is False:
        problems.append("priority is urgent, so needs_human must be true")
    summary = data.get("summary", "")
    if EMAIL.search(summary) or PHONE.search(summary):
        problems.append("summary must not contain an email address or phone number")
    return problems


def validate_reply(raw: str, schema: type[BaseModel]) -> BaseModel:
    """Run all three layers. Return the parsed model or raise ReplyInvalid."""
    try:
        result = schema.model_validate_json(strip_fences(raw))
    except ValidationError as exc:
        problems = []
        for err in exc.errors()[:5]:
            where = ".".join(str(p) for p in err["loc"]) or "reply"
            problems.append(f"{where}: {err['msg']}")
        raise ReplyInvalid(problems) from exc
    problems = check_rules(result)
    if problems:
        raise ReplyInvalid(problems)
    return result


def repair_message(problems: list[str]) -> str:
    """The follow-up we send when a reply fails: say exactly what to fix."""
    bullet_list = "\n".join(f"- {p}" for p in problems)
    return ("Your previous reply did not pass validation:\n"
            f"{bullet_list}\n"
            "Reply again with only the corrected JSON object.")
