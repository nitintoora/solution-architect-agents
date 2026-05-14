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
        print("CHECKPOINT 1/7 — Business Brief")
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
        print("CHECKPOINT 2/7 — Candidate Approaches")
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


def make_architect_review_node(interactive: bool = False, interaction_fn=None):
    """Pause after architect agent for human review of architecture + decisions."""

    def review_architect(state: ArchitectureState) -> dict:
        if interaction_fn:
            return interaction_fn(state)

        if not interactive:
            return {}

        print(f"\n{_SEP}")
        print("CHECKPOINT 3/7 — Architecture & Decisions")
        print(_SEP)
        print(state.architecture)
        print(_SEP + "\n")

        feedback = input("Any feedback for the risk reviewer? (press Enter to skip): ").strip()

        if feedback:
            amended = state.architecture + f"\n\n---\n\n**User notes:**\n{feedback}"
            print("  → Notes recorded. Continuing...\n")
            return {"architecture": amended, "human_architect_feedback": feedback}

        print("  → Approved. Continuing...\n")
        return {}

    return review_architect


def make_risk_review_node(interactive: bool = False, interaction_fn=None):
    """Pause after risk_reviewer agent for human review of the risk register."""

    def review_risks(state: ArchitectureState) -> dict:
        if interaction_fn:
            return interaction_fn(state)

        if not interactive:
            return {}

        print(f"\n{_SEP}")
        print("CHECKPOINT 4/7 — Risk Register")
        print(_SEP)

        for i, r in enumerate(state.risks, 1):
            print(f"\n[{i}] {r.description}")
            print(f"    Likelihood: {r.likelihood}  Impact: {r.impact}")
            print(f"    Mitigation: {r.mitigation}")

        print(f"\n{_SEP}")

        feedback = input("Any additional risks or notes for the doc writer? (press Enter to skip): ").strip()

        if feedback:
            print("  → Notes recorded. Continuing...\n")
            return {"human_risk_feedback": feedback}

        print("  → Approved. Continuing...\n")
        return {}

    return review_risks


def make_draft_review_node(interactive: bool = False, interaction_fn=None):
    """Pause after doc_writer agent for human review/edit of the draft document."""

    def review_draft(state: ArchitectureState) -> dict:
        if interaction_fn:
            return interaction_fn(state)

        if not interactive:
            return {}

        print(f"\n{_SEP}")
        print("CHECKPOINT 5/7 — Draft Document")
        print("The draft is shown below. You can paste an edited version,")
        print("or press Enter to approve as-is.")
        print(_SEP)
        print(state.draft_doc)
        print(_SEP + "\n")

        print("Paste your edited draft (press Enter twice when done), or just Enter to approve:")
        lines = []
        while True:
            line = input()
            if line == "" and lines and lines[-1] == "":
                break
            lines.append(line)

        edited = "\n".join(lines).strip()
        if edited:
            print("  → Edited draft saved. Continuing...\n")
            return {"draft_doc": edited}

        print("  → Approved as-is. Continuing...\n")
        return {}

    return review_draft


def make_feedback_review_node(interactive: bool = False, interaction_fn=None):
    """Pause after doc_reviewer agent for human review of the critique."""

    def review_feedback(state: ArchitectureState) -> dict:
        if interaction_fn:
            return interaction_fn(state)

        if not interactive:
            return {}

        print(f"\n{_SEP}")
        print("CHECKPOINT 6/7 — Doc Reviewer Critique")
        print(_SEP)
        print(state.review_feedback)
        print(_SEP + "\n")

        feedback = input("Any additional notes for the editor? (press Enter to skip): ").strip()

        if feedback:
            amended = state.review_feedback + f"\n\n---\n\n**User notes:**\n{feedback}"
            print("  → Notes recorded. Continuing...\n")
            return {"review_feedback": amended, "human_review_note": feedback}

        print("  → Approved. Continuing...\n")
        return {}

    return review_feedback


def make_final_review_node(interactive: bool = False, interaction_fn=None):
    """Pause after editor agent for human review/edit of the final document."""

    def review_final(state: ArchitectureState) -> dict:
        if interaction_fn:
            return interaction_fn(state)

        if not interactive:
            return {}

        print(f"\n{_SEP}")
        print("CHECKPOINT 7/7 — Final Document")
        print("The final document is shown below. You can paste an edited version,")
        print("or press Enter to accept.")
        print(_SEP)
        print(state.final_doc)
        print(_SEP + "\n")

        print("Paste your edited final doc (press Enter twice when done), or just Enter to accept:")
        lines = []
        while True:
            line = input()
            if line == "" and lines and lines[-1] == "":
                break
            lines.append(line)

        edited = "\n".join(lines).strip()
        if edited:
            print("  → Edited final doc saved. Continuing...\n")
            return {"final_doc": edited}

        print("  → Accepted. Continuing...\n")
        return {}

    return review_final
