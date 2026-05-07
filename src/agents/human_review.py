from src.state import ArchitectureState

_SEP = "=" * 60


def make_brief_review_node(interactive: bool = False, interaction_fn=None):
    """Return a LangGraph node that pauses for human review of the business brief.

    When interaction_fn is provided (web mode), it is called with state and must
    return a state-update dict. When interactive=True (CLI mode), blocks on stdin.
    When neither, the node is a no-op.
    """

    def review_brief(state: ArchitectureState) -> dict:
        if interaction_fn:
            return interaction_fn(state)

        if not interactive:
            return {}

        print(f"\n{_SEP}")
        print("CHECKPOINT 1/2 — Business Brief")
        print("Review the brief below. Press Enter to approve, or type")
        print("corrections / additions then press Enter.")
        print(_SEP)
        print(state.business_brief)
        print(_SEP + "\n")

        feedback = input("Your input: ").strip()

        if feedback:
            amended = (
                state.business_brief
                + f"\n\n---\n\n**User clarifications:**\n{feedback}"
            )
            print("  → Clarifications noted. Continuing...\n")
            return {"business_brief": amended, "human_brief_feedback": feedback}

        print("  → Approved. Continuing...\n")
        return {}

    return review_brief


def make_approach_review_node(interactive: bool = False, interaction_fn=None):
    """Return a LangGraph node that pauses for human review of candidate approaches.

    When interaction_fn is provided (web mode), it is called with state and must
    return a state-update dict. When interactive=True (CLI mode), blocks on stdin.
    When neither, the node is a no-op.
    """

    def review_approaches(state: ArchitectureState) -> dict:
        if interaction_fn:
            return interaction_fn(state)

        if not interactive:
            return {}

        print(f"\n{_SEP}")
        print("CHECKPOINT 2/2 — Candidate Approaches")
        print(_SEP)

        for i, a in enumerate(state.candidate_approaches, 1):
            print(f"\n[{i}] {a.name}  (suitability: {a.suitability_score}/10)")
            print(f"    {a.summary}")
            print(f"    Tradeoffs: {a.tradeoffs}")

        print(f"\n{_SEP}")
        print("Enter a number to indicate a preferred approach,")
        print("or press Enter to let the architect decide.\n")

        choice = input("Your choice: ").strip()

        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(state.candidate_approaches):
                name = state.candidate_approaches[idx].name
                print(f"  → Preference noted: {name}. Continuing...\n")
                return {"human_selected_approach": name}

        print("  → No preference set. Architect will decide. Continuing...\n")
        return {}

    return review_approaches
