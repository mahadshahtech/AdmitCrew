from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from auth import require_staff
from agents.lead_agent import lead_agent

router = APIRouter(
    prefix="/api/leads",
    tags=["Lead Agent"],
    dependencies=[Depends(require_staff)],
)


class LeadInput(BaseModel):
    name: str
    phone: str
    preferred_country: str | None = None
    marks: float | None = None
    ielts_score: float | None = None
    budget: str | None = None


@router.post("")
def create_or_update_lead(data: LeadInput):
    return lead_agent.save_lead(
        name=data.name,
        phone=data.phone,
        preferred_country=data.preferred_country,
        marks=data.marks,
        ielts_score=data.ielts_score,
        budget=data.budget,
    )


@router.get("")
def list_leads(
    search: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    return lead_agent.get_all_leads(search=search, limit=limit, offset=offset)


@router.get("/{phone}")
def get_lead(phone: str):
    lead = lead_agent.find_by_phone(phone)

    if lead is None:
        return {"found": False}

    return {
        "found": True,
        "lead": lead,
    }