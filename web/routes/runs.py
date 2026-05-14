import asyncio
import json
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from web.runner import create_run, get_run, start_run
from src.agents.requirements_clarifier import get_clarifying_questions
from src.agents.refiner import refine_text, refine_risks, refine_architect_output

router = APIRouter()


class ClarifyRequest(BaseModel):
    requirements: str = Field(min_length=10)


class CreateRunRequest(BaseModel):
    requirements: str = Field(min_length=10)


class RefineRequest(BaseModel):
    checkpoint: str
    message: str
    current_output: Optional[str] = None        # text checkpoints
    current_decisions: Optional[list] = None    # architect checkpoint
    current_risks: Optional[list] = None        # risks checkpoint


class RespondRequest(BaseModel):
    checkpoint: str
    # brief checkpoint
    business_brief: Optional[str] = None
    # approaches checkpoint
    selected_approach: Optional[str] = None
    # architect checkpoint
    architecture_feedback: Optional[str] = None
    # risks checkpoint
    risk_feedback: Optional[str] = None
    # draft checkpoint
    draft_doc: Optional[str] = None
    # review_feedback checkpoint
    review_note: Optional[str] = None
    # final checkpoint
    final_doc: Optional[str] = None


@router.post("/clarify")
async def clarify_requirements(body: ClarifyRequest):
    loop = asyncio.get_event_loop()
    questions = await loop.run_in_executor(None, get_clarifying_questions, body.requirements)
    return {"questions": questions}


@router.post("/runs", status_code=201)
async def create_run_endpoint(body: CreateRunRequest):
    ctx = create_run()
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, start_run, ctx.run_id, body.requirements)
    return {"run_id": ctx.run_id}


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str):
    ctx = get_run(run_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_generator():
        while True:
            try:
                item = ctx.queue.get_nowait()
            except Exception:
                await asyncio.sleep(0.05)
                continue

            if item is None:  # sentinel — pipeline finished or errored
                break

            yield f"event: {item['event']}\ndata: {json.dumps(item['data'])}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/runs/{run_id}/refine")
async def refine_checkpoint(run_id: str, body: RefineRequest):
    ctx = get_run(run_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Run not found")

    loop = asyncio.get_event_loop()

    if body.checkpoint == "architect":
        result = await loop.run_in_executor(
            None,
            refine_architect_output,
            body.current_output or "",
            body.current_decisions or [],
            body.message,
        )
        return {"updated_text": result["architecture"], "updated_decisions": result["decisions"], "updated_risks": None}

    elif body.checkpoint == "risks":
        updated = await loop.run_in_executor(
            None,
            refine_risks,
            body.current_risks or [],
            body.message,
        )
        return {"updated_text": None, "updated_decisions": None, "updated_risks": updated}

    else:
        # All text checkpoints: brief, draft, review_feedback, final
        updated = await loop.run_in_executor(
            None,
            refine_text,
            body.current_output or "",
            body.message,
        )
        return {"updated_text": updated, "updated_decisions": None, "updated_risks": None}


@router.post("/runs/{run_id}/respond")
async def respond_to_checkpoint(run_id: str, body: RespondRequest):
    ctx = get_run(run_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Run not found")
    if ctx.status != "waiting":
        raise HTTPException(status_code=409, detail="Run is not waiting for a checkpoint response")

    if body.checkpoint == "brief":
        if body.business_brief and body.business_brief.strip():
            ctx.checkpoint_response = {
                "business_brief": body.business_brief.strip(),
                "human_brief_feedback": "(edited via web UI)",
            }
        else:
            ctx.checkpoint_response = {}

    elif body.checkpoint == "approaches":
        if body.selected_approach and body.selected_approach.strip():
            ctx.checkpoint_response = {"human_selected_approach": body.selected_approach.strip()}
        else:
            ctx.checkpoint_response = {}

    elif body.checkpoint == "architect":
        if body.architecture_feedback and body.architecture_feedback.strip():
            feedback = body.architecture_feedback.strip()
            ctx.checkpoint_response = {
                "human_architect_feedback": feedback,
            }
        else:
            ctx.checkpoint_response = {}

    elif body.checkpoint == "risks":
        if body.risk_feedback and body.risk_feedback.strip():
            ctx.checkpoint_response = {"human_risk_feedback": body.risk_feedback.strip()}
        else:
            ctx.checkpoint_response = {}

    elif body.checkpoint == "draft":
        if body.draft_doc and body.draft_doc.strip():
            ctx.checkpoint_response = {"draft_doc": body.draft_doc.strip()}
        else:
            ctx.checkpoint_response = {}

    elif body.checkpoint == "review_feedback":
        if body.review_note and body.review_note.strip():
            note = body.review_note.strip()
            ctx.checkpoint_response = {
                "human_review_note": note,
            }
        else:
            ctx.checkpoint_response = {}

    elif body.checkpoint == "final":
        if body.final_doc and body.final_doc.strip():
            ctx.checkpoint_response = {"final_doc": body.final_doc.strip()}
        else:
            ctx.checkpoint_response = {}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown checkpoint: {body.checkpoint!r}")

    ctx.checkpoint_event.set()
    return {"ok": True}
