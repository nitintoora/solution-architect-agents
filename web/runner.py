"""
Background run orchestration for the web UI.

Each run gets a RunContext holding a thread-safe queue for SSE events and a
threading.Event used as the HITL pause/resume handshake.
"""

import queue
import threading
import uuid
from dataclasses import dataclass, field
from typing import Optional

from src.graph import build_graph
from src.state import ArchitectureState
from src.utils.output_writer import _render_options, _render_decisions, _render_risks

_STEP_LABELS: dict[str, str] = {
    "business_analyst": "Business Analyst",
    "solutioning": "Solutioning",
    "architect": "Architect",
    "risk_reviewer": "Risk Reviewer",
    "doc_writer": "Doc Writer",
    "doc_reviewer": "Doc Reviewer",
    "editor": "Editor",
}

# Checkpoint timeout: 10 minutes
_CHECKPOINT_TIMEOUT = 600


@dataclass
class RunContext:
    run_id: str
    queue: queue.Queue = field(default_factory=queue.Queue)
    checkpoint_event: threading.Event = field(default_factory=threading.Event)
    checkpoint_response: dict = field(default_factory=dict)
    status: str = "pending"   # pending | running | waiting | complete | error
    error: Optional[str] = None


# In-memory store — single-user tool, no persistence needed
_runs: dict[str, RunContext] = {}


def create_run() -> RunContext:
    run_id = str(uuid.uuid4())
    ctx = RunContext(run_id=run_id)
    _runs[run_id] = ctx
    return ctx


def get_run(run_id: str) -> Optional[RunContext]:
    return _runs.get(run_id)


def start_run(run_id: str, requirements: str) -> None:
    """Entry point for the background thread. Runs the full pipeline."""
    ctx = _runs[run_id]
    ctx.status = "running"

    # --- callbacks passed into the graph ------------------------------------

    def progress_callback(node_name: str, status: str, elapsed: float) -> None:
        ctx.queue.put({
            "event": "progress",
            "data": {
                "step": node_name,
                "label": _STEP_LABELS.get(node_name, node_name),
                "status": status,
                "elapsed_s": round(elapsed, 1),
            },
        })

    def brief_interaction_fn(state: ArchitectureState) -> dict:
        ctx.status = "waiting"
        ctx.queue.put({
            "event": "checkpoint",
            "data": {
                "checkpoint": "brief",
                "business_brief": state.business_brief,
            },
        })
        timed_out = not ctx.checkpoint_event.wait(timeout=_CHECKPOINT_TIMEOUT)
        ctx.checkpoint_event.clear()
        if timed_out:
            raise TimeoutError("Timed out waiting for brief review (10 min limit).")
        ctx.status = "running"
        return ctx.checkpoint_response

    def approach_interaction_fn(state: ArchitectureState) -> dict:
        ctx.status = "waiting"
        ctx.queue.put({
            "event": "checkpoint",
            "data": {
                "checkpoint": "approaches",
                "candidate_approaches": [
                    {
                        "name": a.name,
                        "summary": a.summary,
                        "key_components": a.key_components,
                        "tradeoffs": a.tradeoffs,
                        "suitability_score": a.suitability_score,
                    }
                    for a in state.candidate_approaches
                ],
            },
        })
        timed_out = not ctx.checkpoint_event.wait(timeout=_CHECKPOINT_TIMEOUT)
        ctx.checkpoint_event.clear()
        if timed_out:
            raise TimeoutError("Timed out waiting for approach selection (10 min limit).")
        ctx.status = "running"
        return ctx.checkpoint_response

    # --- run the pipeline ---------------------------------------------------

    try:
        graph = build_graph(
            progress_callback=progress_callback,
            brief_interaction_fn=brief_interaction_fn,
            approach_interaction_fn=approach_interaction_fn,
        )
        initial_state = ArchitectureState(requirements_input=requirements)
        result = graph.invoke(initial_state)

        # graph.invoke returns a dict; coerce to typed model for renderers
        state = ArchitectureState(**result) if isinstance(result, dict) else result

        ctx.status = "complete"
        ctx.queue.put({
            "event": "complete",
            "data": {
                "final_doc": state.final_doc,
                "mermaid_diagram": state.mermaid_diagram,
                "business_brief": state.business_brief,
                "options_md": _render_options(state),
                "decisions_md": _render_decisions(state),
                "risks_md": _render_risks(state),
                "review_feedback": state.review_feedback,
            },
        })
    except Exception as exc:
        ctx.status = "error"
        ctx.error = str(exc)
        ctx.queue.put({"event": "error", "data": {"message": str(exc)}})
    finally:
        ctx.queue.put(None)  # sentinel — tells SSE generator to close
