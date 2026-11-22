from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import AuthUser, get_current_user
from ..database import get_db
from ..models import Profile
from ..schemas import ProfilePayload

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


def to_payload(profile: Profile) -> ProfilePayload:
    return ProfilePayload(
        fullName=profile.full_name, firstName=profile.first_name, lastName=profile.last_name,
        email=profile.email, phone=profile.phone, city=profile.city, country=profile.country,
        linkedin=profile.linkedin, github=profile.github, university=profile.university,
        degree=profile.degree, graduationYear=profile.graduation_year,
    )


@router.get("", response_model=ProfilePayload)
def get_profile(user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)) -> ProfilePayload:
    profile = db.get(Profile, user.id)
    if profile is None:
        raise HTTPException(404, "Profile not found")
    return to_payload(profile)


@router.put("", response_model=ProfilePayload)
def put_profile(payload: ProfilePayload, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)) -> ProfilePayload:
    profile = db.get(Profile, user.id)
    if profile is None:
        profile = Profile(user_id=user.id, full_name=payload.fullName, email=str(payload.email))
        db.add(profile)
    profile.full_name = payload.fullName
    profile.first_name = payload.firstName
    profile.last_name = payload.lastName
    profile.email = str(payload.email)
    profile.phone = payload.phone
    profile.city = payload.city
    profile.country = payload.country
    profile.linkedin = payload.linkedin
    profile.github = payload.github
    profile.university = payload.university
    profile.degree = payload.degree
    profile.graduation_year = payload.graduationYear
    db.commit()
    return to_payload(profile)
