"""auto-fill API."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import database_ready
from .security import protect_and_monitor
from .routes.profile import router as profile_router
from .routes.resumes import router as resumes_router
from .routes.account import router as account_router
from .routes.facts import router as facts_router
from .routes.tailor import router as tailor_router
from .routes.screening import router as screening_router
from .routes.applications import router as applications_router

app = FastAPI(title="auto-fill API", version="0.7.0")
app.middleware("http")(protect_and_monitor)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=False,
    allow_methods=["GET", "PUT", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Confirm-Delete"],
)
app.include_router(profile_router)
app.include_router(resumes_router)
app.include_router(account_router)
app.include_router(facts_router)
app.include_router(tailor_router)
app.include_router(screening_router)
app.include_router(applications_router)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/ready")
def ready() -> dict[str, str]:
    if not database_ready():
        raise HTTPException(503, "Database unavailable")
    return {"status": "ready"}
