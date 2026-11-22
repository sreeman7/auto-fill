"""Permanent user-requested account deletion."""

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..auth import AuthUser, get_current_user
from ..config import settings
from ..database import get_db
from ..models import Application, CareerFact, Profile, Resume
from ..services.storage import StorageError, remove_resume_strict

router = APIRouter(prefix="/api/v1/account", tags=["account"])


@router.delete("", status_code=204)
async def delete_account(
    user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db),
    x_confirm_delete: str | None = Header(default=None),
) -> None:
    if x_confirm_delete != "delete-my-account":
        raise HTTPException(400, "Explicit deletion confirmation required")
    if not settings.supabase_secret_key:
        raise HTTPException(503, "Account deletion is not configured")
    resumes = db.scalars(select(Resume).where(Resume.user_id == user.id)).all()
    try:
        for resume in resumes:
            await remove_resume_strict(user, resume.storage_path)
    except StorageError as exc:
        raise HTTPException(503, str(exc)) from exc
    db.execute(delete(CareerFact).where(CareerFact.user_id == user.id))
    db.execute(delete(Application).where(Application.user_id == user.id))
    db.execute(delete(Resume).where(Resume.user_id == user.id))
    db.execute(delete(Profile).where(Profile.user_id == user.id))
    db.commit()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.delete(
                f"{settings.supabase_url}/auth/v1/admin/users/{user.id}",
                headers={
                    "apikey": settings.supabase_secret_key,
                    "Authorization": f"Bearer {settings.supabase_secret_key}",
                },
            )
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Account data was removed, but Auth deletion must be retried") from exc
    if response.status_code not in (200, 204, 404):
        raise HTTPException(503, "Account data was removed, but Auth deletion must be retried")
