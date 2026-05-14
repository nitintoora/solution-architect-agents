import json
import re

import src.llm as llm
from src.utils.prompt_loader import load_prompt


def get_clarifying_questions(requirements: str) -> list[str]:
    """Return 3–5 clarifying questions for the given requirements.

    Uses Haiku for speed. Returns an empty list on any parse or API error
    so the caller can fall back to direct generation gracefully.
    """
    system_prompt = load_prompt("requirements_clarifier")
    try:
        response = llm.call_claude(
            system_prompt,
            f"Business requirements:\n\n{requirements}",
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
        )
        return _parse_questions(response)
    except Exception:
        return []


def _parse_questions(response: str) -> list[str]:
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", response)
    raw = match.group(1).strip() if match else response.strip()
    data = json.loads(raw)
    if isinstance(data, list):
        return [str(q) for q in data if q]
    return []
