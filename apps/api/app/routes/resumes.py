"""Private upload, pending suggestions and explicit approval."""

import hashlib
from datetime import timedelta
from pathlib import PurePath
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import AuthUser, get_current_user
from ..database import get_db
from ..models import CareerFact, Profile, Resume, utc_now
from ..schemas import ApprovalRequest, ApprovalResult, ResumeView, Suggestion
from ..services.resume_parser import MAX_UPLOAD_BYTES, ResumeParseError, detect_file_type, extract_suggestions, extract_text
from ..services.storage import StorageError, delete_resume, upload_resume

router = APIRouter(prefix="/api/v1/resumes", tags=["resumes"])
MAX_RESUMES_PER_DAY = 20


def to_view(resume: Resume) -> ResumeView:
    return ResumeView(
        id=resume.id, originalFilename=resume.original_filename, byteCount=resume.byte_count,
        status=resume.status, createdAt=resume.created_at,
        suggestions=[Suggestion.model_validate(item) for item in resume.suggestions],
    )


@router.post("/upload", response_model=ResumeView, status_code=201)
async def upload(
    file: UploadFile = File(...), user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db),
) -> ResumeView:
    filename = PurePath(file.filename or "").name
    if not filename or len(filename) > 255:
        raise HTTPException(422, "Invalid filename")
    recent_count = db.scalar(select(func.count()).select_from(Resume).where(
        Resume.user_id == user.id, Resume.created_at >= utc_now() - timedelta(days=1),
    )) or 0
    if recent_count >= MAX_RESUMES_PER_DAY:
        raise HTTPException(429, "Daily resume upload limit reached")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Resume must be 5 MB or smaller")
    try:
        content_type, extension = detect_file_type(filename, data)
        text = extract_text(data, extension)
    except ResumeParseError as exc:
        raise HTTPException(422, str(exc)) from exc
    digest = hashlib.sha256(data).hexdigest()
    duplicate = db.scalar(select(Resume).where(Resume.user_id == user.id, Resume.sha256 == digest))
    if duplicate:
        raise HTTPException(409, "This resume is already uploaded")
    resume_id = uuid4()
    path = f"{user.id}/{resume_id}.{extension}"
    suggestions = [item.model_dump() for item in extract_suggestions(text)]
    resume = Resume(
        id=resume_id, user_id=user.id, original_filename=filename, content_type=content_type,
        byte_count=len(data), sha256=digest, storage_path=path,
        status="pending_review", suggestions=suggestions,
    )
    try:
        await upload_resume(user, path, data, content_type)
    except StorageError as exc:
        raise HTTPException(503, str(exc)) from exc
    db.add(resume)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        await delete_resume(user, path)
        raise HTTPException(409, "This resume is already uploaded") from exc
    except Exception:
        db.rollback()
        await delete_resume(user, path)
        raise
    return to_view(resume)


@router.get("", response_model=list[ResumeView])
def list_resumes(user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ResumeView]:
    rows = db.scalars(select(Resume).where(Resume.user_id == user.id).order_by(Resume.created_at.desc())).all()
    return [to_view(row) for row in rows]


@router.get("/{resume_id}", response_model=ResumeView)
def get_resume(resume_id: UUID, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)) -> ResumeView:
    resume = db.scalar(select(Resume).where(Resume.id == resume_id, Resume.user_id == user.id))
    if resume is None:
        raise HTTPException(404, "Resume not found")
    return to_view(resume)


@router.post("/{resume_id}/approve", response_model=ApprovalResult)
def approve(
    resume_id: UUID, payload: ApprovalRequest,
    user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db),
) -> ApprovalResult:
    resume = db.scalar(select(Resume).where(Resume.id == resume_id, Resume.user_id == user.id))
    if resume is None:
        raise HTTPException(404, "Resume not found")
    if resume.status != "pending_review":
        raise HTTPException(409, "Resume was already reviewed")
    available = {item["id"]: item for item in resume.suggestions}
    if len({item.id for item in payload.items}) != len(payload.items) or any(item.id not in available for item in payload.items):
        raise HTTPException(422, "Invalid suggestion selection")
    if any(not item.value for item in payload.items):
        raise HTTPException(422, "Approved values cannot be empty")
    profile = db.get(Profile, user.id)
    approved_contacts: dict[str, str] = {}
    for item in payload.items:
        source = available[item.id]
        value = item.value.strip()
        db.add(CareerFact(
            user_id=user.id, source_resume_id=resume.id, kind=source["kind"], value=value,
            source_excerpt=source["sourceExcerpt"], edited_by_user=value != source["proposed"],
        ))
        if source["kind"] in {"fullName", "email", "phone", "linkedin", "github"}:
            approved_contacts[source["kind"]] = value
    updated = False
    if profile is None and approved_contacts.get("fullName") and approved_contacts.get("email"):
        try:
            ProfilePayload(fullName=approved_contacts["fullName"], email=approved_contacts["email"])
        except ValueError as exc:
            raise HTTPException(422, "Approved contact details are invalid") from exc
        profile = Profile(user_id=user.id, full_name=approved_contacts["fullName"], email=approved_contacts["email"])
        db.add(profile)
        updated = True
    if profile:
        for kind, attribute in {"phone": "phone", "linkedin": "linkedin", "github": "github"}.items():
            if approved_contacts.get(kind) and not getattr(profile, attribute):
                setattr(profile, attribute, approved_contacts[kind])
                updated = True
    resume.status = "approved"
    resume.approved_at = utc_now()
    db.commit()
    return ApprovalResult(approvedCount=len(payload.items), profileUpdated=updated)
