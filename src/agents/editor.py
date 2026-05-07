import src.llm as llm
from src.utils.prompt_loader import load_prompt
from src.state import ArchitectureState


def editor(state: ArchitectureState) -> dict:
    system_prompt = load_prompt("editor")
    user_message = (
        f"Draft document:\n\n{state.draft_doc}\n\n"
        f"---\n\nReviewer feedback:\n\n{state.review_feedback}"
    )
    response = llm.call_claude(
        system_prompt, user_message,
        model="claude-sonnet-4-6",
        max_tokens=8192,
    )
    return {"final_doc": response}
