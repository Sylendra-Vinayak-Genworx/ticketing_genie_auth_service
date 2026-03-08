"""
Admin Team Management Routes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
POST   /admin/teams                             → create team + bulk members
GET    /admin/teams                             → list all teams
GET    /admin/teams/{team_id}                   → get team + members
DELETE /admin/teams/{team_id}                   → delete team

POST   /admin/teams/{team_id}/members           → add single member
DELETE /admin/teams/{team_id}/members/{user_id} → remove member (unsets lead_id)
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.rest.dependencies.auth import get_db, role_required
from src.core.services.team_service import TeamService
from src.schemas.team_schema import (
    AddMemberRequest,
    MemberResponse,
    TeamCreateRequest,
    TeamListResponse,
    TeamResponse,
)

router = APIRouter(prefix="/admin/teams", tags=["admin-teams"])

_admin = Depends(role_required("admin"))


def _svc(session: AsyncSession = Depends(get_db)) -> TeamService:
    return TeamService(session)


def _to_member_response(user) -> MemberResponse:
    return MemberResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.name.value if user.role else "",
        is_active=user.is_active,
    )


def _to_team_response(team, members) -> TeamResponse:
    return TeamResponse(
        id=team.id,
        name=team.name,
        description=team.description,
        lead_id=team.lead_id,
        members=[_to_member_response(m) for m in members],
    )


# ── Team endpoints ────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=TeamResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a team and optionally bulk-add members",
    dependencies=[_admin],
)
async def create_team(
    payload: TeamCreateRequest,
    svc: TeamService = Depends(_svc),
) -> TeamResponse:
    team, members = await svc.create_team(payload)
    return _to_team_response(team, members)


@router.get(
    "",
    response_model=TeamListResponse,
    summary="List all teams with their members",
    dependencies=[_admin],
)
async def list_teams(
    svc: TeamService = Depends(_svc),
) -> TeamListResponse:
    total, teams_with_members = await svc.list_teams()
    return TeamListResponse(
        total=total,
        teams=[_to_team_response(t, m) for t, m in teams_with_members],
    )


@router.get(
    "/{team_id}",
    response_model=TeamResponse,
    summary="Get team detail with members",
    dependencies=[_admin],
)
async def get_team(
    team_id: UUID,
    svc: TeamService = Depends(_svc),
) -> TeamResponse:
    team, members = await svc.get_team(team_id)
    return _to_team_response(team, members)


@router.delete(
    "/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a team (members are unassigned, not deleted)",
    dependencies=[_admin],
)
async def delete_team(
    team_id: UUID,
    svc: TeamService = Depends(_svc),
) -> None:
    await svc.delete_team(team_id)


# ── Member endpoints ──────────────────────────────────────────────────────────

@router.post(
    "/{team_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user and add them to the team",
    dependencies=[_admin],
)
async def add_member(
    team_id: UUID,
    payload: AddMemberRequest,
    svc: TeamService = Depends(_svc),
) -> MemberResponse:
    user = await svc.add_member(team_id, payload)
    return _to_member_response(user)


@router.delete(
    "/{team_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member from a team (sets lead_id = None)",
    dependencies=[_admin],
)
async def remove_member(
    team_id: UUID,
    user_id: UUID,
    svc: TeamService = Depends(_svc),
) -> None:
    await svc.remove_member(team_id, user_id)