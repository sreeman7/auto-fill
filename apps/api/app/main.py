"""auto-fill API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routes.profile import router as profile_router
from .routes.resumes import router as resumes_router
from .routes.account import router as account_router
from .routes.facts import router as facts_router

app = FastAPI(title="auto-fill API", version="0.2.0")
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


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
