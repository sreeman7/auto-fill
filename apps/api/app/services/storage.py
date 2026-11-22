"""Use the caller's JWT so Supabase private-bucket RLS applies."""

from urllib.parse import quote

import httpx

from ..auth import AuthUser
from ..config import settings


class StorageError(RuntimeError):
    pass


def object_url(path: str) -> str:
    encoded = "/".join(quote(segment, safe="") for segment in path.split("/"))
    return f"{settings.supabase_url}/storage/v1/object/resumes/{encoded}"


async def upload_resume(user: AuthUser, path: str, data: bytes, content_type: str) -> None:
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise StorageError("Private storage is not configured")
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                object_url(path), content=data,
                headers={
                    "apikey": settings.supabase_publishable_key,
                    "Authorization": f"Bearer {user.token}",
                    "Content-Type": content_type,
                    "x-upsert": "false",
                },
            )
    except httpx.HTTPError as exc:
        raise StorageError("Private storage unavailable") from exc
    if response.status_code not in (200, 201):
        raise StorageError("Private storage rejected the upload")


async def download_resume(user: AuthUser, path: str) -> bytes:
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise StorageError("Private storage is not configured")
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                object_url(path),
                headers={"apikey": settings.supabase_publishable_key, "Authorization": f"Bearer {user.token}"},
            )
    except httpx.HTTPError as exc:
        raise StorageError("Private storage unavailable") from exc
    if response.status_code != 200 or len(response.content) > 5 * 1024 * 1024:
        raise StorageError("Could not read the private resume")
    return response.content


async def delete_resume(user: AuthUser, path: str) -> None:
    if not settings.supabase_url or not settings.supabase_publishable_key:
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.delete(
                object_url(path),
                headers={"apikey": settings.supabase_publishable_key, "Authorization": f"Bearer {user.token}"},
            )
    except httpx.HTTPError:
        pass  # A failed cleanup is handled by an operations audit later.


async def remove_resume_strict(user: AuthUser, path: str) -> None:
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise StorageError("Private storage is not configured")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.delete(
                object_url(path),
                headers={"apikey": settings.supabase_publishable_key, "Authorization": f"Bearer {user.token}"},
            )
    except httpx.HTTPError as exc:
        raise StorageError("Private storage unavailable during deletion") from exc
    if response.status_code not in (200, 204, 404):
        raise StorageError("Private storage rejected the deletion")
