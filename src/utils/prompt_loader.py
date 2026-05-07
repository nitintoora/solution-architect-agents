from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(agent_name: str) -> str:
    """Load a prompt from src/prompts/<agent_name>.md.

    Raises FileNotFoundError if the prompt file does not exist.
    """
    path = _PROMPTS_DIR / f"{agent_name}.md"
    if not path.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {path}\n"
            f"Expected a file at src/prompts/{agent_name}.md"
        )
    return path.read_text(encoding="utf-8").strip()
