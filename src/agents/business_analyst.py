import src.llm as llm
from src.utils.prompt_loader import load_prompt
from src.state import ArchitectureState


def business_analyst(state: ArchitectureState) -> dict:
    system_prompt = load_prompt("business_analyst")
    user_message = f"Business requirements:\n\n{state.requirements_input}"
    response = llm.call_claude(
        system_prompt, user_message,
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
    )
    return {"business_brief": response}
