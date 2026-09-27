from fastapi import FastAPI

from database import init_database
from routes.leads import router as leads_router
from routes.chat import router as chat_router
from routes.documents import router as documents_router
from routes.followups import router as followups_router
from routes.applications import router as applications_router
from routes.tasks import router as tasks_router
from routes.escalations import router as escalations_router
from routes.dashboard import router as dashboard_router
from routes.auth import router as auth_router
from routes.staff import router as staff_router
from routes.programs import router as programs_router


app = FastAPI(
    title="AdmitCrew API",
    description="Agentic admissions assistant backend",
    version="0.1.0",
)


init_database()


app.include_router(leads_router)
app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(followups_router)
app.include_router(applications_router)
app.include_router(tasks_router)
app.include_router(escalations_router)
app.include_router(dashboard_router)
app.include_router(auth_router)
app.include_router(staff_router)
app.include_router(programs_router)


@app.get("/")
def root():
    return {
        "app": "AdmitCrew",
        "status": "running",
        "message": "AdmitCrew backend is alive.",
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }