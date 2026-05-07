import json
import re

import src.llm as llm
from src.utils.prompt_loader import load_prompt
from src.state import ArchitectureState, Risk


def risk_reviewer(state: ArchitectureState) -> dict:
    system_prompt = load_prompt("risk_reviewer")
    user_message = (
        f"Business brief:\n\n{state.business_brief}\n\n"
        f"---\n\nArchitecture description:\n\n{state.architecture}"
    )
    response = llm.call_claude(
        system_prompt, user_message,
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
    )
    return {"risks": _parse_risks(response)}


def _parse_risks(response: str) -> list[Risk]:
    data = _extract_json(response)
    return [Risk(**item) for item in data]


def _extract_json(text: str) -> list:
    if not text or not text.strip():
        raise ValueError("Risk reviewer returned an empty response from the LLM.")
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        return json.loads(match.group(1).strip())
    return json.loads(text.strip())
