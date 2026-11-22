"""Bounded request and response contracts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ProfilePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    fullName: str = Field(min_length=1, max_length=160)
    firstName: str = Field(default="", max_length=100)
    lastName: str = Field(default="", max_length=100)
    email: EmailStr
    phone: str = Field(default="", max_length=40)
    city: str = Field(default="", max_length=120)
    country: str = Field(default="", max_length=120)
    linkedin: str = Field(default="", max_length=500)
    github: str = Field(default="", max_length=500)
    university: str = Field(default="", max_length=200)
    degree: str = Field(default="", max_length=200)
    graduationYear: str = Field(default="", max_length=4)

    @field_validator("graduationYear")
    @classmethod
    def valid_year(cls, value: str) -> str:
        if value and (not value.isdigit() or len(value) != 4):
            raise ValueError("Graduation year must have four digits")
        return value


FactKind = Literal["fullName", "email", "phone", "linkedin", "github", "education", "experience", "project", "skill"]


class Suggestion(BaseModel):
    id: str
    kind: FactKind
    proposed: str
    sourceExcerpt: str


class ResumeView(BaseModel):
    id: UUID
    originalFilename: str
    byteCount: int
    status: str
    createdAt: datetime
    suggestions: list[Suggestion]


class ApprovalItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    id: str
    value: str = Field(min_length=1, max_length=1000)


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ApprovalItem] = Field(min_length=1, max_length=50)


class ApprovalResult(BaseModel):
    approvedCount: int
    profileUpdated: bool


class CareerFactView(BaseModel):
    id: UUID
    kind: FactKind
    value: str
    sourceExcerpt: str
    editedByUser: bool
    verifiedAt: datetime


class FactUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    value: str = Field(min_length=1, max_length=1000)
