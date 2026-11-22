"""Validate access tokens against Supabase Auth before any private operation."""

from dataclasses import dataclass
from uuid import UUID

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings


@dataclass(frozen=True)
class AuthUser:
    id: UUID
    token: str
    email: str


bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> AuthUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication is not configured")
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                f"{settings.supabase_url}/auth/v1/user",
                headers={
                    "apikey": settings.supabase_publishable_key,
                    "Authorization": f"Bearer {credentials.credentials}",
                },
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication service unavailable") from exc
    if response.status_code != 200:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session")
    try:
        user = response.json()
        user_id = UUID(user["id"])
        email = str(user.get("email") or "")
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid user identity") from exc
    if not user.get("email_confirmed_at"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Verify your email before using cloud features")
    return AuthUser(id=user_id, token=credentials.credentials, email=email)
