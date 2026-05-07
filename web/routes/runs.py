import asyncio
import json
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from web.runner import create_run, get_run, start_run

router = APIRouter()


class CreateRunRequest(BaseModel):
    requirements: str = Field(min_length=10)


class RespondRequest(BaseModel):
    checkpoint: str
    business_brief: Optional[str] = None   # edited brief text (brief checkpoint)
    selected_approach: Optional[str] = None  # approach name (approaches checkpoint)


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

    else:
        raise HTTPException(status_code=400, detail=f"Unknown checkpoint: {body.checkpoint!r}")

    ctx.checkpoint_event.set()
    return {"ok": True}
