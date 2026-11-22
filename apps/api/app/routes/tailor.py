"""Authenticated job analysis, grounded proposals, and approved PDF export."""

from datetime import timedelta
from uuid import UUID, uuid4
import hashlib
import hmac
import json

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import AuthUser, get_current_user
from ..config import settings
from ..database import get_db
from ..models import CareerFact, Profile, Resume, TailoringDraft, utc_now
from ..services.resume_parser import ResumeParseError, detect_file_type, extract_text
from ..services.resume_pdf import render_resume_pdf
from ..services.storage import StorageError, download_resume
from ..services.tailoring import TailoringError, analyze_with_model, build_grounded_analysis

router = APIRouter(prefix="/api/v1/tailor", tags=["tailoring"])
MAX_DRAFTS_PER_DAY = 10


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    resumeId: UUID
    jobDescription: str = Field(min_length=100, max_length=16000)


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selectedSuggestionIds: list[UUID] = Field(max_length=20)


def profile_data(profile: Profile) -> dict[str, str]:
    return {"fullName": profile.full_name, "email": profile.email, "phone": profile.phone, "city": profile.city,
            "country": profile.country, "linkedin": profile.linkedin, "github": profile.github}


def signature_for(draft_id: UUID, user_id: UUID, resume_id: UUID, payload: dict) -> str:
    if len(settings.tailor_signing_key) < 32:
        raise HTTPException(503, "Tailoring signing key is not configured")
    data = json.dumps({"draftId": str(draft_id), "userId": str(user_id), "resumeId": str(resume_id), "payload": payload},
                      sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(settings.tailor_signing_key.encode("utf-8"), data, hashlib.sha256).hexdigest()


@router.post("/analyze")
async def analyze(payload: AnalyzeRequest, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if len(settings.tailor_signing_key) < 32:
        raise HTTPException(503, "Tailoring signing key is not configured")
    resume = db.scalar(select(Resume).where(Resume.id == payload.resumeId, Resume.user_id == user.id))
    if resume is None:
        raise HTTPException(404, "Resume not found")
    profile = db.get(Profile, user.id)
    if profile is None:
        raise HTTPException(409, "Save a profile before tailoring a resume")
    facts = db.scalars(select(CareerFact).where(CareerFact.user_id == user.id).order_by(CareerFact.verified_at, CareerFact.id)).all()
    if not facts:
        raise HTTPException(409, "Approve career facts before tailoring a resume")
    if len(facts) > 80 or sum(len(fact.value) for fact in facts) > 30000:
        raise HTTPException(422, "Too many approved facts for one analysis; remove or shorten some facts")
    count = db.scalar(select(func.count()).select_from(TailoringDraft).where(
        TailoringDraft.user_id == user.id, TailoringDraft.created_at >= utc_now() - timedelta(days=1),
    )) or 0
    if count >= MAX_DRAFTS_PER_DAY:
        raise HTTPException(429, "Daily tailoring limit reached")
    try:
        data = await download_resume(user, resume.storage_path)
        _content_type, extension = detect_file_type(resume.original_filename, data)
        original_text = extract_text(data, extension)
    except (StorageError, ResumeParseError) as exc:
        raise HTTPException(503, str(exc)) from exc
    try:
        model_result = await analyze_with_model(payload.jobDescription, facts)
        grounded = build_grounded_analysis(payload.jobDescription, model_result, facts)
    except TailoringError as exc:
        raise HTTPException(503, str(exc)) from exc
    draft_id = uuid4()
    draft = TailoringDraft(id=draft_id, user_id=user.id, source_resume_id=resume.id, payload=grounded,
                           signature=signature_for(draft_id, user.id, resume.id, grounded),
                           model=settings.openai_model, input_tokens=model_result.input_tokens, output_tokens=model_result.output_tokens)
    db.add(draft)
    db.commit()
    return {
        "draftId": str(draft.id), "resumeId": str(resume.id), "originalFilename": resume.original_filename,
        "originalText": original_text[:12000], "createdAt": draft.created_at.isoformat(),
        "inputTokens": draft.input_tokens, "outputTokens": draft.output_tokens,
        **{key: value for key, value in grounded.items() if key != "facts"},
    }


@router.post("/{draft_id}/export")
def export_pdf(draft_id: UUID, payload: ExportRequest, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    draft = db.scalar(select(TailoringDraft).where(TailoringDraft.id == draft_id, TailoringDraft.user_id == user.id))
    if draft is None:
        raise HTTPException(404, "Tailored draft not found")
    expected_signature = signature_for(draft.id, draft.user_id, draft.source_resume_id, draft.payload)
    if not hmac.compare_digest(draft.signature, expected_signature):
        raise HTTPException(409, "Tailored draft was changed; analyze the job again")
    created_at = draft.created_at if draft.created_at.tzinfo else draft.created_at.replace(tzinfo=utc_now().tzinfo)
    if created_at < utc_now() - timedelta(days=1):
        raise HTTPException(410, "Tailored draft expired; analyze the job again")
    selected = {str(item) for item in payload.selectedSuggestionIds}
    if len(selected) != len(payload.selectedSuggestionIds):
        raise HTTPException(422, "Duplicate suggestion selection")
    suggestions = draft.payload["suggestions"]
    if not selected <= {item["id"] for item in suggestions}:
        raise HTTPException(422, "Unknown suggestion selection")
    snapshots = draft.payload["facts"]
    current = {str(fact.id): fact for fact in db.scalars(select(CareerFact).where(CareerFact.user_id == user.id)).all()}
    if any(item["id"] not in current or current[item["id"]].value != item["value"] for item in snapshots):
        raise HTTPException(409, "Approved facts changed; analyze the job again")
    profile = db.get(Profile, user.id)
    if profile is None:
        raise HTTPException(409, "Profile is missing")
    try:
        pdf = render_resume_pdf(profile_data(profile), snapshots, suggestions, selected)
    except ImportError as exc:
        raise HTTPException(503, "PDF export dependency is not installed") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return Response(content=pdf, media_type="application/pdf", headers={
        "Content-Disposition": 'attachment; filename="auto-fill-tailored-resume.pdf"',
        "Cache-Control": "no-store",
    })
