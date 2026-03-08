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
    Create a team from a members list.
    lead_id is NOT required from the client — the backend derives it
    from whichever member has role=team_lead.
    Exactly one member must have role=team_lead.
    """
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    members: list[MemberCreateRequest] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_exactly_one_lead(self) -> "TeamCreateRequest":
        leads = [m for m in self.members if m.role == UserRole.TEAM_LEAD]
        if len(leads) == 0:
            raise ValueError("At least one member must have role 'team_lead'.")
        if len(leads) > 1:
            raise ValueError("Only one member can have role 'team_lead'.")
        return self


class AddMemberRequest(BaseModel):
    """Create a new user and assign them to this team."""
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    role: UserRole


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