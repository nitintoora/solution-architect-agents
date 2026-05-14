import time

from langgraph.graph import StateGraph, START, END

from src.state import ArchitectureState
from src.agents.business_analyst import business_analyst
from src.agents.solutioning import solutioning
from src.agents.architect import architect
from src.agents.risk_reviewer import risk_reviewer
from src.agents.doc_writer import doc_writer
from src.agents.doc_reviewer import doc_reviewer
from src.agents.editor import editor
from src.agents.human_review import (
    make_brief_review_node,
    make_approach_review_node,
    make_architect_review_node,
    make_risk_review_node,
    make_draft_review_node,
    make_feedback_review_node,
    make_final_review_node,
)

_STEPS = [
    ("business_analyst", "Business analyst", business_analyst),
    ("solutioning", "Solutioning", solutioning),
    ("architect", "Architect", architect),
    ("risk_reviewer", "Risk reviewer", risk_reviewer),
    ("doc_writer", "Doc writer", doc_writer),
    ("doc_reviewer", "Doc reviewer", doc_reviewer),
    ("editor", "Editor", editor),
]


def _timed_node(idx: int, label: str, fn, node_name: str = "", progress_callback=None):
    total = len(_STEPS)

    def node(state: ArchitectureState) -> dict:
        if progress_callback:
            progress_callback(node_name, "running", 0.0)
        else:
            print(f"[{idx}/{total}] {label}...", end=" ", flush=True)
        start = time.time()
        result = fn(state)
        elapsed = time.time() - start
        if progress_callback:
            progress_callback(node_name, "done", elapsed)
        else:
            print(f"done ({elapsed:.1f}s)")
        return result

    return node


def build_graph(
    interactive: bool = False,
    progress_callback=None,
    brief_interaction_fn=None,
    approach_interaction_fn=None,
    architect_interaction_fn=None,
    risk_interaction_fn=None,
    draft_interaction_fn=None,
    feedback_interaction_fn=None,
    final_interaction_fn=None,
):
    graph = StateGraph(ArchitectureState)

    # Human-in-the-loop nodes (no timing wrapper — they block on user input)
    graph.add_node("review_brief", make_brief_review_node(interactive, interaction_fn=brief_interaction_fn))
    graph.add_node("review_approaches", make_approach_review_node(interactive, interaction_fn=approach_interaction_fn))
    graph.add_node("review_architect", make_architect_review_node(interactive, interaction_fn=architect_interaction_fn))
    graph.add_node("review_risks", make_risk_review_node(interactive, interaction_fn=risk_interaction_fn))
    graph.add_node("review_draft", make_draft_review_node(interactive, interaction_fn=draft_interaction_fn))
    graph.add_node("review_feedback", make_feedback_review_node(interactive, interaction_fn=feedback_interaction_fn))
    graph.add_node("review_final", make_final_review_node(interactive, interaction_fn=final_interaction_fn))

    # Agent nodes with progress timing
    for i, (node_name, label, fn) in enumerate(_STEPS, start=1):
        graph.add_node(node_name, _timed_node(i, label, fn, node_name=node_name, progress_callback=progress_callback))

    # Linear pipeline with HITL checkpoints after every agent
    graph.add_edge(START, "business_analyst")
    graph.add_edge("business_analyst", "review_brief")
    graph.add_edge("review_brief", "solutioning")
    graph.add_edge("solutioning", "review_approaches")
    graph.add_edge("review_approaches", "architect")
    graph.add_edge("architect", "review_architect")
    graph.add_edge("review_architect", "risk_reviewer")
    graph.add_edge("risk_reviewer", "review_risks")
    graph.add_edge("review_risks", "doc_writer")
    graph.add_edge("doc_writer", "review_draft")
    graph.add_edge("review_draft", "doc_reviewer")
    graph.add_edge("doc_reviewer", "review_feedback")
    graph.add_edge("review_feedback", "editor")
    graph.add_edge("editor", "review_final")
    graph.add_edge("review_final", END)

    return graph.compile()
