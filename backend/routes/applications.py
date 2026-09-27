from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from auth import require_staff
from agents.application_agent import application_agent


router = APIRouter(
    prefix="/api/applications",
    tags=["Application Agent"],
    dependencies=[Depends(require_staff)],
)


class ApplicationCreateInput(BaseModel):
    lead_id: int = Field(gt=0)
    university: str
    program: str
    notes: str | None = None


class ApplicationStatusInput(BaseModel):
    status: str


class ApplicationNoteInput(BaseModel):
    note: str


@router.get("")
def list_applications(
    lead_id: int | None = Query(default=None, gt=0),
    status: str | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    if status is not None and status not in application_agent.STATUSES:
        raise HTTPException(status_code=422, detail="Invalid application status.")
    return application_agent.get_all_applications(
        lead_id=lead_id,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.post("")
def create_application(data: ApplicationCreateInput):
    result = application_agent.create_application(
        lead_id=data.lead_id,
        university=data.university,
        program=data.program,
        notes=data.notes,
    )
    if result.get("error") == "lead_not_found":
        raise HTTPException(status_code=404, detail="Student lead not found.")
    if result.get("error") == "program_not_found":
        raise HTTPException(
            status_code=404,
            detail="University/program was not found in AdmitCrew's catalog.",
        )
    return result


@router.get("/lead/{lead_id}")
def list_lead_applications(lead_id: int):
    applications = application_agent.get_applications_for_lead(lead_id)
    if applications is None:
        raise HTTPException(status_code=404, detail="Student lead not found.")
    return {"lead_id": lead_id, "applications": applications}


@router.get("/{application_id}")
def get_application(application_id: int):
    application = application_agent.get_application(application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    return {"application": application}


@router.patch("/{application_id}/status")
def update_application_status(
    application_id: int,
    data: ApplicationStatusInput,
):
    result = application_agent.update_status(application_id, data.status)
    if result.get("error") == "application_not_found":
        raise HTTPException(status_code=404, detail="Application not found.")
    if result.get("error") == "invalid_status":
        raise HTTPException(status_code=422, detail=result)
    if result.get("error") in {"invalid_transition", "documents_not_ready"}:
        raise HTTPException(status_code=409, detail=result)
    return result


@router.post("/{application_id}/notes")
def add_application_note(
    application_id: int,
    data: ApplicationNoteInput,
):
    result = application_agent.add_note(application_id, data.note)
    if result.get("error") == "application_not_found":
        raise HTTPException(status_code=404, detail="Application not found.")
    if result.get("error") == "empty_note":
        raise HTTPException(status_code=422, detail="Note must not be empty.")
    return result
