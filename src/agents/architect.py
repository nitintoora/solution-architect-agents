import json
import re

import src.llm as llm
from src.utils.prompt_loader import load_prompt
from src.state import ArchitectureState, Decision


def architect(state: ArchitectureState) -> dict:
    system_prompt = load_prompt("architect")

    approaches_text = "\n\n".join(
        f"### {a.name}\n{a.summary}\n\n"
        f"Key components: {', '.join(a.key_components)}\n\n"
        f"Tradeoffs: {a.tradeoffs}\n\n"
        f"Suitability score: {a.suitability_score}/10"
        for a in state.candidate_approaches
    )

    hint = ""
    if state.human_selected_approach:
        hint = (
            f"\n\n---\n\n**User preference:** The user has indicated a preference for "
            f"'{state.human_selected_approach}'. Select this approach unless there is a "
            f"strong technical reason not to — if so, name the objection explicitly in "
            f"your <CHOSEN_APPROACH_REASONING>."
        )

    user_message = (
        f"Business brief:\n\n{state.business_brief}\n\n"
        f"---\n\nCandidate approaches:\n\n{approaches_text}"
        f"{hint}"
    )

    response = llm.call_claude(
        system_prompt, user_message,
        model="claude-opus-4-6",
        max_tokens=8192,
    )

    return {
        "chosen_approach": _extract_tag(response, "CHOSEN_APPROACH"),
        "chosen_approach_reasoning": _extract_tag(response, "CHOSEN_APPROACH_REASONING"),
        "architecture": _extract_tag(response, "ARCHITECTURE"),
        "mermaid_diagram": _extract_tag(response, "MERMAID"),
        "decisions": _parse_decisions(response),
    }


def _extract_tag(text: str, tag: str) -> str:
    pattern = rf"<{tag}>([\s\S]*?)</{tag}>"
    match = re.search(pattern, text)
    if not match:
        raise ValueError(
            f"Could not find <{tag}> in architect response.\n"
            f"Response snippet: {text[:300]}"
        )
    return match.group(1).strip()


def _parse_decisions(response: str) -> list[Decision]:
    content = _extract_tag(response, "DECISIONS")
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
    if json_match:
        data = json.loads(json_match.group(1).strip())
    else:
        data = json.loads(content)
    return [Decision(**item) for item in data]
