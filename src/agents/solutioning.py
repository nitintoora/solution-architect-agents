import json
import re

import src.llm as llm
from src.utils.prompt_loader import load_prompt
from src.state import ArchitectureState, CandidateApproach


def solutioning(state: ArchitectureState) -> dict:
    system_prompt = load_prompt("solutioning")
    user_message = f"Business brief:\n\n{state.business_brief}"
    response = llm.call_claude(
        system_prompt, user_message,
        model="claude-sonnet-4-6",
        max_tokens=3000,
    )
    return {"candidate_approaches": _parse_approaches(response)}


def _parse_approaches(response: str) -> list[CandidateApproach]:
    data = _extract_json(response)
    return [CandidateApproach(**item) for item in data]


def _extract_json(text: str) -> list:
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        return json.loads(match.group(1).strip())
    return json.loads(text.strip())
