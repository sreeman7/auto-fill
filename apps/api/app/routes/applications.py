"""Manual, user-scoped application tracker."""

from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import AuthUser, get_current_user
from ..database import get_db
from ..models import Application, utc_now
from ..services.application_tracking import PRE_SUBMISSION, canonical_job_url, search_key, url_fingerprint

router = APIRouter(prefix="/api/v1/applications", tags=["applications"])
Status = Literal["saved", "in_progress", "ready_for_review", "applied", "assessment", "interview", "offer", "rejected", "withdrawn"]
Sort = Literal["updated_desc", "updated_asc", "company_asc", "company_desc", "applied_desc", "applied_asc"]


class ApplicationFields(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    company: str = Field(min_length=1, max_length=160)
    jobTitle: str = Field(min_length=1, max_length=200)
    jobUrl: str = Field(min_length=1, max_length=2000)
    location: str = Field(default="", max_length=160)
    resumeVersion: str = Field(default="", max_length=255)
    notes: str = Field(default="", max_length=5000)
    interviewDates: list[date] = Field(default_factory=list, max_length=20)
    followUpDates: list[date] = Field(default_factory=list, max_length=20)

    @field_validator("jobUrl")
    @classmethod
    def valid_url(cls, value: str) -> str:
        canonical_job_url(value)
        return value

    @field_validator("interviewDates", "followUpDates")
    @classmethod
    def unique_dates(cls, value: list[date]) -> list[date]:
        if len(set(value)) != len(value):
            raise ValueError("Dates must be unique")
        return sorted(value)


class ApplicationCreate(ApplicationFields):
    allowPossibleDuplicate: bool = False


class ApplicationUpdate(ApplicationFields):
    status: Status
    appliedOn: date | None = None
    confirmSubmitted: bool = False
    allowPossibleDuplicate: bool = False


def to_view(row: Application) -> dict:
    return {
        "id": str(row.id), "company": row.company, "jobTitle": row.job_title,
        "jobUrl": row.job_url, "location": row.location, "resumeVersion": row.resume_version,
        "status": row.status, "appliedOn": row.applied_on.isoformat() if row.applied_on else None,
        "notes": row.notes, "interviewDates": row.interview_dates,
        "followUpDates": row.follow_up_dates, "createdAt": row.created_at.isoformat(),
        "updatedAt": row.updated_at.isoformat(),
    }


def ensure_not_duplicate(db: Session, user_id: UUID, payload: ApplicationFields,
                         allow_possible: bool, excluding: UUID | None = None) -> None:
    query = select(Application).where(Application.user_id == user_id)
    if excluding:
        query = query.where(Application.id != excluding)
    exact = db.scalar(query.where(Application.url_fingerprint == url_fingerprint(payload.jobUrl)))
    if exact:
        raise HTTPException(409, {"code": "duplicate_url", "message": "This job URL is already tracked.", "matches": [to_view(exact)]})
    if not allow_possible:
        possible = db.scalars(query.where(Application.company_key == search_key(payload.company)[:160],
                                          Application.title_key == search_key(payload.jobTitle)[:200]).limit(5)).all()
        if possible:
            raise HTTPException(409, {"code": "possible_duplicate", "message": "A job with this company and title is already tracked. Review it before adding another role.",
                                      "matches": [to_view(row) for row in possible]})


def assign_fields(row: Application, payload: ApplicationFields) -> None:
    row.company = payload.company
    row.company_key = search_key(payload.company)[:160]
    row.job_title = payload.jobTitle
    row.title_key = search_key(payload.jobTitle)[:200]
    row.job_url = payload.jobUrl
    row.canonical_url = canonical_job_url(payload.jobUrl)
    row.url_fingerprint = url_fingerprint(payload.jobUrl)
    row.location = payload.location
    row.resume_version = payload.resumeVersion
    row.notes = payload.notes
    row.interview_dates = [value.isoformat() for value in payload.interviewDates]
    row.follow_up_dates = [value.isoformat() for value in payload.followUpDates]
    row.updated_at = utc_now()


def owned(db: Session, user_id: UUID, application_id: UUID) -> Application:
    row = db.scalar(select(Application).where(Application.id == application_id, Application.user_id == user_id))
    if not row:
        raise HTTPException(404, "Application not found")
    return row


@router.get("")
def list_applications(q: str = Query(default="", max_length=200), status: Status | None = None,
                      sort: Sort = "updated_desc", limit: int = Query(default=50, ge=1, le=100),
                      offset: int = Query(default=0, ge=0), user: AuthUser = Depends(get_current_user),
                      db: Session = Depends(get_db)) -> dict:
    query = select(Application).where(Application.user_id == user.id)
    if status:
        query = query.where(Application.status == status)
    if q.strip():
        escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        query = query.where(or_(Application.company.ilike(pattern, escape="\\"),
                                Application.job_title.ilike(pattern, escape="\\"),
                                Application.location.ilike(pattern, escape="\\"),
                                Application.notes.ilike(pattern, escape="\\"),
                                Application.job_url.ilike(pattern, escape="\\")))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    ordering = {
        "updated_desc": (Application.updated_at.desc(), Application.id.desc()),
        "updated_asc": (Application.updated_at.asc(), Application.id.asc()),
        "company_asc": (Application.company_key.asc(), Application.updated_at.desc()),
        "company_desc": (Application.company_key.desc(), Application.updated_at.desc()),
        "applied_desc": (Application.applied_on.desc(), Application.updated_at.desc()),
        "applied_asc": (Application.applied_on.asc().nulls_last(), Application.updated_at.desc()),
    }
    rows = db.scalars(query.order_by(*ordering[sort]).limit(limit).offset(offset)).all()
    return {"items": [to_view(row) for row in rows], "total": total, "limit": limit, "offset": offset}


@router.post("", status_code=201)
def create_application(payload: ApplicationCreate, user: AuthUser = Depends(get_current_user),
                       db: Session = Depends(get_db)) -> dict:
    ensure_not_duplicate(db, user.id, payload, payload.allowPossibleDuplicate)
    row = Application(user_id=user.id, status="saved", applied_on=None)
    assign_fields(row, payload)
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "This job URL is already tracked") from exc
    return to_view(row)


@router.get("/{application_id}")
def get_application(application_id: UUID, user: AuthUser = Depends(get_current_user),
                    db: Session = Depends(get_db)) -> dict:
    return to_view(owned(db, user.id, application_id))


@router.put("/{application_id}")
def update_application(application_id: UUID, payload: ApplicationUpdate,
                       user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    row = owned(db, user.id, application_id)
    ensure_not_duplicate(db, user.id, payload, payload.allowPossibleDuplicate, row.id)
    if payload.status in PRE_SUBMISSION:
        if payload.appliedOn is not None:
            raise HTTPException(422, "A pre-submission status cannot have an applied date")
        applied_on = None
    else:
        if row.applied_on is None and not payload.confirmSubmitted:
            raise HTTPException(422, "Confirm that you submitted the application on the website before marking it applied")
        applied_on = payload.appliedOn or row.applied_on or date.today()
        if applied_on > date.today():
            raise HTTPException(422, "Applied date cannot be in the future")
    assign_fields(row, payload)
    row.status = payload.status
    row.applied_on = applied_on
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "This job URL is already tracked") from exc
    return to_view(row)


@router.delete("/{application_id}", status_code=204)
def delete_application(application_id: UUID, user: AuthUser = Depends(get_current_user),
                       db: Session = Depends(get_db)) -> None:
    db.delete(owned(db, user.id, application_id))
    db.commit()
