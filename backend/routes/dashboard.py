from fastapi import APIRouter, Depends, HTTPException, Query

from auth import require_staff
from agents.dashboard_agent import dashboard_agent


router = APIRouter(
    prefix="/api/dashboard",
    tags=["Staff Dashboard"],
    dependencies=[Depends(require_staff)],
)


@router.get("/overview")
def get_dashboard_overview(
    upcoming_days: int = Query(default=7, ge=0, le=365),
):
    return dashboard_agent.get_overview(upcoming_days=upcoming_days)


@router.get("/pipeline")
def get_application_pipeline():
    return dashboard_agent.get_pipeline()


@router.get("/attention")
def get_attention_queue(
    limit: int = Query(default=50, ge=1, le=200),
):
    return dashboard_agent.get_attention(limit=limit)


@router.get("/activity")
def get_recent_activity(
    limit: int = Query(default=20, ge=1, le=100),
):
    return {"activity": dashboard_agent.get_recent_activity(limit=limit)}


@router.get("/students/{lead_id}")
def get_student_case(
    lead_id: int,
    activity_limit: int = Query(default=20, ge=1, le=100),
):
    case = dashboard_agent.get_student_case(
        lead_id=lead_id,
        activity_limit=activity_limit,
    )
    if case is None:
        raise HTTPException(status_code=404, detail="Student lead not found.")
    return case
