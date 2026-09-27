from fastapi import APIRouter, Depends, HTTPException

from auth import require_staff
from agents.followup_agent import followup_agent


router = APIRouter(
    prefix="/api/followups",
    tags=["Follow-up Agent"],
    dependencies=[Depends(require_staff)],
)


@router.post("/run")
def run_followup_detection():
    return followup_agent.run_detection()


@router.get("/pending")
def list_pending_followups():
    return {"followups": followup_agent.list_followups("pending")}


@router.post("/{followup_id}/approve")
def approve_followup(followup_id: int):
    result = followup_agent.approve_followup(followup_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Follow-up not found.")
    if result.get("not_pending"):
        raise HTTPException(status_code=409, detail="Follow-up is not pending.")
    return result


@router.get("/sent")
def list_sent_followups():
    return {"followups": followup_agent.list_followups("sent")}
