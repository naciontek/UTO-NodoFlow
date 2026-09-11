from typing import Literal
from fastapi import APIRouter, HTTPException, Request
from .contracts import SubmitTask, NodeRegistration
from .repository import IdempotencyConflict

router = APIRouter()

@router.post("/tasks", status_code=202)
async def create_task(body: SubmitTask, request: Request):
    try:
        return await request.app.state.repository.submit(body)
    except IdempotencyConflict:
        raise HTTPException(409, "La clave de idempotencia ya se usó con otros datos")

@router.get("/tasks")
async def list_tasks(request: Request, state: Literal["PENDING","RUNNING","RETRY_PENDING","SUCCEEDED","FAILED"] | None = None):
    return await request.app.state.repository.list(state)

@router.get("/tasks/{task_id}")
async def get_task(task_id: str, request: Request):
    task = await request.app.state.repository.get(task_id)
    if task is None:
        raise HTTPException(404, "Tarea no encontrada")
    return task

@router.get("/nodes")
async def nodes(request: Request):
    return await request.app.state.repository.nodes(request.app.state.settings.liveness_seconds)

@router.post("/internal/nodes/heartbeat")
async def heartbeat(body: NodeRegistration, request: Request):
    await request.app.state.repository.register(body)
    return {"registered": True, "node_id": body.node_id}
