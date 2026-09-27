from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth import require_staff
from agents.document_agent import document_agent


router = APIRouter(
    prefix="/api/documents",
    tags=["Document Agent"],
    dependencies=[Depends(require_staff)],
)


class DocumentCheckInput(BaseModel):
    lead_id: int
    document_type: str
    filename: str
    document_name: str
    expiry_date: str | None = None
    ielts_score: float | None = None


@router.post("/check")
def check_document(data: DocumentCheckInput):
    return document_agent.check_document(
        lead_id=data.lead_id,
        document_type=data.document_type,
        filename=data.filename,
        document_name=data.document_name,
        expiry_date=data.expiry_date,
        ielts_score=data.ielts_score,
    )


@router.get("")
def get_all_documents():
    return {
        "documents": document_agent.get_all_documents()
    }


@router.get("/lead/{lead_id}")
def get_lead_documents(lead_id: int):
    return {
        "lead_id": lead_id,
        "documents": document_agent.get_documents_for_lead(
            lead_id
        ),
    }