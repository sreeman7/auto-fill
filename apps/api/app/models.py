"""Phase 2 user-scoped records."""

from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Profile(Base):
    __tablename__ = "profiles"

    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    phone: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    city: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    country: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    linkedin: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    github: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    university: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    degree: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    graduation_year: Mapped[str] = mapped_column(String(4), default="", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class Resume(Base):
    __tablename__ = "resumes"
    __table_args__ = (
        UniqueConstraint("user_id", "sha256", name="uq_resume_user_sha256"),
        Index("ix_resumes_user_created", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    byte_count: Mapped[int] = mapped_column(nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending_review", nullable=False)
    suggestions: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    facts: Mapped[list["CareerFact"]] = relationship(back_populates="resume")


class CareerFact(Base):
    __tablename__ = "career_facts"
    __table_args__ = (Index("ix_career_facts_user_kind", "user_id", "kind"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_resume_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    source_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    edited_by_user: Mapped[bool] = mapped_column(default=False, nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    resume: Mapped[Resume] = relationship(back_populates="facts")


class TailoringDraft(Base):
    __tablename__ = "tailoring_drafts"
    __table_args__ = (Index("ix_tailoring_drafts_user_created", "user_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_resume_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    signature: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int] = mapped_column(default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ScreeningDraft(Base):
    __tablename__ = "screening_drafts"
    __table_args__ = (Index("ix_screening_drafts_user_created", "user_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    signature: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int] = mapped_column(default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ApprovedAnswer(Base):
    __tablename__ = "approved_answers"
    __table_args__ = (
        Index("ix_approved_answers_user_created", "user_id", "created_at"),
        UniqueConstraint("user_id", "source_draft_id", name="uq_approved_answer_draft"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_draft_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    question: Mapped[str] = mapped_column(String(1000), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str] = mapped_column(String(30), nullable=False)
    source_fact_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    edited_by_user: Mapped[bool] = mapped_column(default=False, nullable=False)
    signature: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("user_id", "url_fingerprint", name="uq_application_user_url"),
        CheckConstraint("status IN ('saved','in_progress','ready_for_review','applied','assessment','interview','offer','rejected','withdrawn')", name="ck_application_status"),
        CheckConstraint("(status IN ('saved','in_progress','ready_for_review') AND applied_on IS NULL) OR (status IN ('applied','assessment','interview','offer','rejected','withdrawn') AND applied_on IS NOT NULL)", name="ck_application_applied_date"),
        Index("ix_applications_user_status_updated", "user_id", "status", "updated_at"),
        Index("ix_applications_user_company_title", "user_id", "company_key", "title_key"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    company: Mapped[str] = mapped_column(String(160), nullable=False)
    company_key: Mapped[str] = mapped_column(String(160), nullable=False)
    job_title: Mapped[str] = mapped_column(String(200), nullable=False)
    title_key: Mapped[str] = mapped_column(String(200), nullable=False)
    job_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    url_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    location: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    resume_version: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="saved", nullable=False)
    applied_on: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    interview_dates: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    follow_up_dates: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
