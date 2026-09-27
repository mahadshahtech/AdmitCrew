from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from auth import require_staff
from agents.task_agent import task_agent


router = APIRouter(
    prefix="/api/tasks",
    tags=["Task & Deadline Agent"],
    dependencies=[Depends(require_staff)],
)


class TaskCreateInput(BaseModel):
    lead_id: int = Field(gt=0)
    application_id: int | None = Field(default=None, gt=0)
    title: str
    description: str | None = None
    task_type: str
    due_at: str
    priority: str = "normal"


class DeadlineTaskInput(BaseModel):
    application_id: int = Field(gt=0)


@router.post("")
def create_task(data: TaskCreateInput):
    result = task_agent.create_task(
        lead_id=data.lead_id,
        application_id=data.application_id,
        title=data.title,
        description=data.description,
        task_type=data.task_type,
        due_at=data.due_at,
        priority=data.priority,
    )
    if result.get("error") == "lead_not_found":
        raise HTTPException(status_code=404, detail="Student lead not found.")
    if result.get("error") == "application_not_found":
        raise HTTPException(status_code=404, detail="Application not found.")
    if result.get("error") == "application_lead_mismatch":
        raise HTTPException(
            status_code=422,
            detail="The application does not belong to the specified student.",
        )
    if result.get("error"):
        raise HTTPException(status_code=422, detail=result)
    return result


@router.post("/generate-application-deadline")
def generate_application_deadline_task(data: DeadlineTaskInput):
    result = task_agent.generate_application_deadline_task(data.application_id)
    if result.get("error") == "application_not_found":
        raise HTTPException(status_code=404, detail="Application not found.")
    return result


@router.get("")
def list_all_tasks(
    status: str | None = None,
    lead_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    if status is not None and status not in task_agent.STATUSES:
        raise HTTPException(status_code=422, detail="Invalid task status.")
    return {
        "tasks": task_agent.list_all_tasks(
            status=status,
            lead_id=lead_id,
            limit=limit,
            offset=offset,
        )
    }


@router.get("/lead/{lead_id}")
def list_lead_tasks(lead_id: int):
    tasks = task_agent.list_tasks_for_lead(lead_id)
    if tasks is None:
        raise HTTPException(status_code=404, detail="Student lead not found.")
    return {"lead_id": lead_id, "tasks": tasks}


@router.get("/application/{application_id}")
def list_application_tasks(application_id: int):
    tasks = task_agent.list_tasks_for_application(application_id)
    if tasks is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    return {"application_id": application_id, "tasks": tasks}


@router.get("/overdue")
def list_overdue_tasks():
    return {"tasks": task_agent.get_overdue_tasks()}


@router.get("/upcoming")
def list_upcoming_tasks(
    days: int = Query(default=7, ge=0, le=3660),
):
    return {"days": days, "tasks": task_agent.get_upcoming_tasks(days)}


@router.patch("/{task_id}/complete")
def complete_task(task_id: int):
    result = task_agent.complete_task(task_id)
    if result.get("error") == "task_not_found":
        raise HTTPException(status_code=404, detail="Task not found.")
    if result.get("error") == "task_cancelled":
        raise HTTPException(status_code=409, detail="Cancelled tasks cannot be completed.")
    return result


@router.patch("/{task_id}/cancel")
def cancel_task(task_id: int):
    result = task_agent.cancel_task(task_id)
    if result.get("error") == "task_not_found":
        raise HTTPException(status_code=404, detail="Task not found.")
    if result.get("error") == "task_completed":
        raise HTTPException(status_code=409, detail="Completed tasks cannot be cancelled.")
    return result
