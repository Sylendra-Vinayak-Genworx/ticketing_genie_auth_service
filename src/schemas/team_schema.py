from __future__ import annotations

from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, model_validator

from src.constants.enum import UserRole


# ── Member schemas ────────────────────────────────────────────────────────────

class MemberCreateRequest(BaseModel):
    """Single member to create and assign to a team (via lead_id on User)."""
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    role: UserRole


class MemberResponse(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


# ── Team schemas ──────────────────────────────────────────────────────────────

class TeamCreateRequest(BaseModel):
    """
    Create a team from existing member IDs.
    lead_id is required. member_ids are required.
    """
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    lead_id: UUID
    member_ids: list[UUID] = []

class AddMemberRequest(BaseModel):
    """Assign an existing user to this team."""
    user_id: UUID


class TeamResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    lead_id: UUID | None
    members: list[MemberResponse] = []

    model_config = {"from_attributes": True}


class TeamListResponse(BaseModel):
    total: int
    teams: list[TeamResponse]