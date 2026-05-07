import src.llm as llm
from src.utils.prompt_loader import load_prompt
from src.state import ArchitectureState


def doc_reviewer(state: ArchitectureState) -> dict:
    system_prompt = load_prompt("doc_reviewer")
    user_message = (
        f"Business brief:\n\n{state.business_brief}\n\n"
        f"---\n\nDraft solution design document:\n\n{state.draft_doc}"
    )
    response = llm.call_claude(
        system_prompt, user_message,
        model="claude-sonnet-4-6",
        max_tokens=2048,
    )
    return {"review_feedback": response}
