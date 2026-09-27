from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth import get_current_staff, require_staff
from agents.escalation_agent import escalation_agent


router = APIRouter(
    prefix="/api/escalations",
    tags=["Staff Escalation & Human Handoff"],
    dependencies=[Depends(require_staff)],
)


class ResolveEscalationInput(BaseModel):
    staff_response: str


@router.get("")
def list_escalations(
    lead_id: int | None = Query(default=None, gt=0),
    status: str | None = None,
):
    if status is not None and status not in escalation_agent.STATUSES:
        raise HTTPException(
            status_code=422,
            detail={"error": "invalid_status", "allowed_statuses": sorted(escalation_agent.STATUSES)},
        )
    return {
        "escalations": escalation_agent.list_escalations(
            lead_id=lead_id,
            status=status,
        )
    }


@router.get("/open")
def list_open_escalations(
    lead_id: int | None = Query(default=None, gt=0),
):
    return {
        "escalations": escalation_agent.list_open_escalations(lead_id=lead_id)
    }


@router.get("/{escalation_id}")
def get_escalation(escalation_id: int):
    escalation = escalation_agent.get_escalation(escalation_id)
    if escalation is None:
        raise HTTPException(status_code=404, detail="Escalation not found.")
    return {"escalation": escalation}


@router.patch("/{escalation_id}/start")
def start_escalation(escalation_id: int):
    result = escalation_agent.start_escalation(escalation_id)
    if result.get("error") == "escalation_not_found":
        raise HTTPException(status_code=404, detail="Escalation not found.")
    if result.get("error") == "escalation_resolved":
        raise HTTPException(status_code=409, detail="Resolved escalations cannot be reopened.")
    if result.get("error") == "invalid_status":
        raise HTTPException(status_code=409, detail=result)
    return result


@router.patch("/{escalation_id}/resolve")
def resolve_escalation(
    escalation_id: int,
    data: ResolveEscalationInput,
    staff: dict = Depends(get_current_staff),
):
    result = escalation_agent.resolve_escalation(
        escalation_id,
        data.staff_response,
        actor_id=staff["id"],
    )
    if result.get("error") == "escalation_not_found":
        raise HTTPException(status_code=404, detail="Escalation not found.")
    if result.get("error") == "staff_response_required":
        raise HTTPException(
            status_code=422,
            detail="A non-empty staff response is required.",
        )
    if result.get("error") == "escalation_already_resolved":
        raise HTTPException(status_code=409, detail=result)
    if result.get("error") == "invalid_status":
        raise HTTPException(status_code=409, detail=result)
    return result
