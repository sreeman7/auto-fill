"""Authenticated, explicitly approved screening responses."""

import hashlib
import hmac
import json
from datetime import timedelta
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import AuthUser, get_current_user
from ..config import settings
from ..database import get_db
from ..models import ApprovedAnswer, CareerFact, ScreeningDraft, utc_now
from ..services.screening import ScreeningError, compose_answer, interpret_with_model, sensitive_reason

router = APIRouter(prefix="/api/v1/screening", tags=["screening"])
MAX_DRAFTS_PER_DAY = 20


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=10, max_length=1000)
    jobContext: str = Field(default="", max_length=2000)
    maxWords: Literal[60, 120, 200] = 120


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    answer: str = Field(min_length=1, max_length=2000)
    confirmed: Literal[True]


def sign_record(kind: str, record_id: UUID, user_id: UUID, payload: dict) -> str:
    if len(settings.tailor_signing_key) < 32:
        raise HTTPException(503, "Draft signing key is not configured")
    data = json.dumps({"kind": kind, "id": str(record_id), "userId": str(user_id), "payload": payload},
                      sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(settings.tailor_signing_key.encode("utf-8"), data, hashlib.sha256).hexdigest()


def answer_data(answer: ApprovedAnswer) -> dict:
    return {"sourceDraftId": str(answer.source_draft_id), "question": answer.question, "answer": answer.answer,
            "intent": answer.intent, "sourceFactIds": answer.source_fact_ids, "editedByUser": answer.edited_by_user}


def answer_view(answer: ApprovedAnswer) -> dict:
    return {"id": str(answer.id), **answer_data(answer), "createdAt": answer.created_at.isoformat()}


@router.post("/draft")
async def draft_answer(payload: DraftRequest, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    sensitive = sensitive_reason(payload.question)
    if sensitive:
        return {"sensitive": True, "reason": f"This asks about {sensitive}. Answer it yourself on the application page; auto-fill will not draft or save it."}
    if len(settings.tailor_signing_key) < 32:
        raise HTTPException(503, "Draft signing key is not configured")
    facts = db.scalars(select(CareerFact).where(CareerFact.user_id == user.id).order_by(CareerFact.verified_at.desc())).all()
    if not facts:
        raise HTTPException(409, "Approve career facts before drafting a screening answer")
    if len(facts) > 80 or sum(len(fact.value) for fact in facts) > 30000:
        raise HTTPException(422, "Too many approved facts for one request; remove or shorten some facts")
    count = db.scalar(select(func.count()).select_from(ScreeningDraft).where(
        ScreeningDraft.user_id == user.id, ScreeningDraft.created_at >= utc_now() - timedelta(days=1),
    )) or 0
    if count >= MAX_DRAFTS_PER_DAY:
        raise HTTPException(429, "Daily screening draft limit reached")
    try:
        result = await interpret_with_model(payload.question, payload.jobContext, facts)
        if result.interpretation.sensitive:
            return {"sensitive": True, "reason": "This question may request sensitive information. Answer it yourself on the application page; auto-fill will not draft or save it."}
        grounded = compose_answer(payload.question, payload.jobContext, payload.maxWords, result, facts)
    except ScreeningError as exc:
        raise HTTPException(503, str(exc)) from exc
    draft_id = uuid4()
    record = ScreeningDraft(id=draft_id, user_id=user.id, payload=grounded,
                            signature=sign_record("screening-draft", draft_id, user.id, grounded),
                            model=settings.openai_model, input_tokens=result.input_tokens, output_tokens=result.output_tokens)
    db.add(record)
    db.commit()
    return {"sensitive": False, "draftId": str(record.id), "createdAt": record.created_at.isoformat(),
            "inputTokens": record.input_tokens, "outputTokens": record.output_tokens,
            **{key: value for key, value in grounded.items() if key not in {"factSnapshots", "usedFactIds"}}}


@router.post("/{draft_id}/approve", status_code=201)
def approve_answer(draft_id: UUID, payload: ApprovalRequest, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    draft = db.scalar(select(ScreeningDraft).where(ScreeningDraft.id == draft_id, ScreeningDraft.user_id == user.id))
    if draft is None:
        raise HTTPException(404, "Screening draft not found")
    if not hmac.compare_digest(draft.signature, sign_record("screening-draft", draft.id, draft.user_id, draft.payload)):
        raise HTTPException(409, "Screening draft was changed; create a new draft")
    created_at = draft.created_at if draft.created_at.tzinfo else draft.created_at.replace(tzinfo=utc_now().tzinfo)
    if created_at < utc_now() - timedelta(days=1):
        raise HTTPException(410, "Screening draft expired; create a new draft")
    if sensitive_reason(draft.payload["question"]):
        raise HTTPException(422, "Sensitive questions cannot be saved here")
    if db.scalar(select(ApprovedAnswer).where(ApprovedAnswer.user_id == user.id, ApprovedAnswer.source_draft_id == draft.id)):
        raise HTTPException(409, "This draft was already approved")
    current = {str(fact.id): fact.value for fact in db.scalars(select(CareerFact).where(CareerFact.user_id == user.id)).all()}
    if any(current.get(item["factId"]) != item["value"] for item in draft.payload["factSnapshots"]):
        raise HTTPException(409, "Approved facts changed; create a new draft")
    record_id = uuid4()
    edited_by_user = payload.answer != draft.payload["answer"]
    data = {"sourceDraftId": str(draft.id), "question": draft.payload["question"], "answer": payload.answer,
            "intent": draft.payload["intent"], "sourceFactIds": [] if edited_by_user else draft.payload["usedFactIds"],
            "editedByUser": edited_by_user}
    record = ApprovedAnswer(id=record_id, user_id=user.id, source_draft_id=draft.id, question=data["question"],
                            answer=data["answer"], intent=data["intent"], source_fact_ids=data["sourceFactIds"],
                            edited_by_user=data["editedByUser"], signature=sign_record("approved-answer", record_id, user.id, data))
    db.add(record)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "This draft was already approved") from exc
    return answer_view(record)


@router.get("/answers")
def list_answers(user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(ApprovedAnswer).where(ApprovedAnswer.user_id == user.id).order_by(ApprovedAnswer.created_at.desc()).limit(50)).all()
    for item in rows:
        if not hmac.compare_digest(item.signature, sign_record("approved-answer", item.id, item.user_id, answer_data(item))):
            raise HTTPException(409, "A saved answer was changed outside auto-fill")
    return [answer_view(item) for item in rows]


@router.delete("/answers/{answer_id}", status_code=204)
def delete_answer(answer_id: UUID, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    answer = db.scalar(select(ApprovedAnswer).where(ApprovedAnswer.id == answer_id, ApprovedAnswer.user_id == user.id))
    if answer is None:
        raise HTTPException(404, "Saved answer not found")
    db.delete(answer)
    db.commit()
