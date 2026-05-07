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
from src.agents.human_review import make_brief_review_node, make_approach_review_node

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
):
    graph = StateGraph(ArchitectureState)

    # Human-in-the-loop nodes (no timing wrapper — they block on user input)
    graph.add_node("review_brief", make_brief_review_node(interactive, interaction_fn=brief_interaction_fn))
    graph.add_node("review_approaches", make_approach_review_node(interactive, interaction_fn=approach_interaction_fn))

    # Agent nodes with progress timing
    for i, (node_name, label, fn) in enumerate(_STEPS, start=1):
        graph.add_node(node_name, _timed_node(i, label, fn, node_name=node_name, progress_callback=progress_callback))

    # Linear pipeline with HITL checkpoints spliced in
    graph.add_edge(START, "business_analyst")
    graph.add_edge("business_analyst", "review_brief")
    graph.add_edge("review_brief", "solutioning")
    graph.add_edge("solutioning", "review_approaches")
    graph.add_edge("review_approaches", "architect")
    graph.add_edge("architect", "risk_reviewer")
    graph.add_edge("risk_reviewer", "doc_writer")
    graph.add_edge("doc_writer", "doc_reviewer")
    graph.add_edge("doc_reviewer", "editor")
    graph.add_edge("editor", END)

    return graph.compile()
