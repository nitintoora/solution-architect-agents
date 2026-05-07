import src.llm as llm
from src.utils.prompt_loader import load_prompt
from src.state import ArchitectureState


def doc_writer(state: ArchitectureState) -> dict:
    system_prompt = load_prompt("doc_writer")

    decisions_text = "\n\n".join(
        f"**{d.title}**\n"
        f"- Context: {d.context}\n"
        f"- Decision: {d.decision}\n"
        f"- Reasoning: {d.reasoning}\n"
        f"- Alternatives considered: {', '.join(d.alternatives_considered) or 'None'}"
        for d in state.decisions
    )

    risks_text = "\n".join(
        f"- {r.description} "
        f"(likelihood: {r.likelihood}, impact: {r.impact}) — Mitigation: {r.mitigation}"
        for r in state.risks
    )

    # Compact options table — full tradeoff reasoning is already in chosen_approach_reasoning
    approaches_table = "\n".join(
        f"- **{a.name}** (score: {a.suitability_score}/10): {a.summary}"
        for a in state.candidate_approaches
    )

    user_message = (
        f"## Business brief\n\n{state.business_brief}\n\n"
        f"---\n\n"
        f"## Chosen approach\n\n{state.chosen_approach}\n\n"
        f"## Reasoning\n\n{state.chosen_approach_reasoning}\n\n"
        f"---\n\n"
        f"## Architecture description\n\n{state.architecture}\n\n"
        f"---\n\n"
        f"## Mermaid diagram\n\n```mermaid\n{state.mermaid_diagram}\n```\n\n"
        f"---\n\n"
        f"## Options considered\n\n{approaches_table}\n\n"
        f"---\n\n"
        f"## Key decisions\n\n{decisions_text}\n\n"
        f"---\n\n"
        f"## Risks\n\n{risks_text}"
    )

    response = llm.call_claude(
        system_prompt, user_message,
        model="claude-sonnet-4-6",
        max_tokens=8192,
    )
    return {"draft_doc": response}
