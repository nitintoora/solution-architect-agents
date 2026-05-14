import json
import re

import src.llm as llm
from src.utils.prompt_loader import load_prompt


def _call(user_message: str) -> str:
    return llm.call_claude(
        load_prompt("refiner"),
        user_message,
        model="claude-sonnet-4-6",
        max_tokens=4096,
    )


def refine_text(current_output: str, message: str) -> str:
    """Revise any text/markdown output according to the user's instruction."""
    user_message = (
        f"Current content:\n\n{current_output}\n\n"
        f"---\n\nUser's revision instruction: {message}"
    )
    return _call(user_message)


def refine_risks(current_risks: list[dict], message: str) -> list[dict]:
    """Revise a risks list (JSON array) according to the user's instruction.

    Returns the updated list of risk dicts. Falls back to the original list
    on any parse failure.
    """
    risks_json = json.dumps(current_risks, indent=2)
    user_message = (
        f"Current risks (JSON array):\n\n{risks_json}\n\n"
        f"---\n\nUser's revision instruction: {message}\n\n"
        f"Return the complete updated JSON array only. Each object must have: "
        f"description, likelihood (low/medium/high), impact (low/medium/high), mitigation."
    )
    raw = _call(user_message)
    try:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        data = json.loads(match.group(1).strip() if match else raw.strip())
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return current_risks


def refine_architect_output(architecture: str, decisions: list[dict], message: str) -> dict:
    """Revise the architect output (architecture text + decisions JSON).

    Returns {architecture: str, decisions: list[dict]}.
    """
    decisions_json = json.dumps(decisions, indent=2)
    user_message = (
        f"Current architecture description:\n\n{architecture}\n\n"
        f"---\n\nCurrent decisions (JSON array):\n\n{decisions_json}\n\n"
        f"---\n\nUser's revision instruction: {message}\n\n"
        f"Return your response in exactly this format:\n"
        f"<ARCHITECTURE>\n[updated architecture text]\n</ARCHITECTURE>\n"
        f"<DECISIONS>\n[updated decisions JSON array]\n</DECISIONS>"
    )
    raw = _call(user_message)

    arch = _extract_tag(raw, "ARCHITECTURE") or architecture
    dec_raw = _extract_tag(raw, "DECISIONS") or decisions_json
    try:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", dec_raw)
        decisions_out = json.loads(match.group(1).strip() if match else dec_raw.strip())
    except Exception:
        decisions_out = decisions

    return {"architecture": arch, "decisions": decisions_out}


def _extract_tag(text: str, tag: str) -> str | None:
    match = re.search(rf"<{tag}>([\s\S]*?)</{tag}>", text)
    return match.group(1).strip() if match else None
