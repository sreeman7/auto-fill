"""Review and correct user-approved career facts."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import AuthUser, get_current_user
from ..database import get_db
from ..models import CareerFact
from ..schemas import CareerFactView, FactUpdate

router = APIRouter(prefix="/api/v1/facts", tags=["facts"])


def to_view(fact: CareerFact) -> CareerFactView:
    return CareerFactView(
        id=fact.id, kind=fact.kind, value=fact.value, sourceExcerpt=fact.source_excerpt,
        editedByUser=fact.edited_by_user, verifiedAt=fact.verified_at,
    )


def owned_fact(db: Session, user: AuthUser, fact_id: UUID) -> CareerFact:
    fact = db.scalar(select(CareerFact).where(CareerFact.id == fact_id, CareerFact.user_id == user.id))
    if fact is None:
        raise HTTPException(404, "Fact not found")
    return fact


@router.get("", response_model=list[CareerFactView])
def list_facts(user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)) -> list[CareerFactView]:
    facts = db.scalars(select(CareerFact).where(CareerFact.user_id == user.id).order_by(CareerFact.verified_at.desc())).all()
    return [to_view(fact) for fact in facts]


@router.patch("/{fact_id}", response_model=CareerFactView)
def update_fact(fact_id: UUID, payload: FactUpdate, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)) -> CareerFactView:
    fact = owned_fact(db, user, fact_id)
    fact.value = payload.value
    fact.edited_by_user = True
    db.commit()
    return to_view(fact)


@router.delete("/{fact_id}", status_code=204)
def delete_fact(fact_id: UUID, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    fact = owned_fact(db, user, fact_id)
    db.delete(fact)
    db.commit()
