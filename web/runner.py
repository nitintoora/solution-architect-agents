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


def _make_interaction_fn(ctx: RunContext, checkpoint_name: str, payload_builder):
    """Return a generic interaction_fn closure for any checkpoint.

    payload_builder(state) -> dict  — builds the SSE data payload from state.
    """
    def interaction_fn(state: ArchitectureState) -> dict:
        ctx.status = "waiting"
        ctx.queue.put({
            "event": "checkpoint",
            "data": {"checkpoint": checkpoint_name, **payload_builder(state)},
        })
        timed_out = not ctx.checkpoint_event.wait(timeout=_CHECKPOINT_TIMEOUT)
        ctx.checkpoint_event.clear()
        if timed_out:
            raise TimeoutError(
                f"Timed out waiting for checkpoint '{checkpoint_name}' (10 min limit)."
            )
        ctx.status = "running"
        return ctx.checkpoint_response

    return interaction_fn


def start_run(run_id: str, requirements: str) -> None:
    """Entry point for the background thread. Runs the full pipeline."""
    ctx = _runs[run_id]
    ctx.status = "running"

    # --- progress callback --------------------------------------------------

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

    # --- HITL interaction functions -----------------------------------------

    brief_interaction_fn = _make_interaction_fn(ctx, "brief", lambda s: {
        "business_brief": s.business_brief,
    })

    approach_interaction_fn = _make_interaction_fn(ctx, "approaches", lambda s: {
        "candidate_approaches": [
            {
                "name": a.name,
                "summary": a.summary,
                "key_components": a.key_components,
                "tradeoffs": a.tradeoffs,
                "suitability_score": a.suitability_score,
            }
            for a in s.candidate_approaches
        ],
    })

    architect_interaction_fn = _make_interaction_fn(ctx, "architect", lambda s: {
        "architecture": s.architecture,
        "mermaid_diagram": s.mermaid_diagram,
        "decisions": [
            {
                "title": d.title,
                "context": d.context,
                "decision": d.decision,
                "reasoning": d.reasoning,
                "alternatives_considered": d.alternatives_considered,
            }
            for d in s.decisions
        ],
    })

    risk_interaction_fn = _make_interaction_fn(ctx, "risks", lambda s: {
        "risks": [
            {
                "description": r.description,
                "likelihood": r.likelihood,
                "impact": r.impact,
                "mitigation": r.mitigation,
            }
            for r in s.risks
        ],
    })

    draft_interaction_fn = _make_interaction_fn(ctx, "draft", lambda s: {
        "draft_doc": s.draft_doc,
    })

    feedback_interaction_fn = _make_interaction_fn(ctx, "review_feedback", lambda s: {
        "review_feedback": s.review_feedback,
    })

    final_interaction_fn = _make_interaction_fn(ctx, "final", lambda s: {
        "final_doc": s.final_doc,
    })

    # --- run the pipeline ---------------------------------------------------

    try:
        graph = build_graph(
            progress_callback=progress_callback,
            brief_interaction_fn=brief_interaction_fn,
            approach_interaction_fn=approach_interaction_fn,
            architect_interaction_fn=architect_interaction_fn,
            risk_interaction_fn=risk_interaction_fn,
            draft_interaction_fn=draft_interaction_fn,
            feedback_interaction_fn=feedback_interaction_fn,
            final_interaction_fn=final_interaction_fn,
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
