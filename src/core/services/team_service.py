"""
TeamService
~~~~~~~~~~~
Teams are defined by a lead + all users where User.lead_id == lead.id.
No join table — membership is encoded directly on the User row.

Lead derivation
---------------
The client does NOT send lead_id. The backend finds whichever member
has role=team_lead in the members list, creates them first, and uses
their new user.id as the team's lead_id. All other members get
user.lead_id = that lead's id.
"""
from __future__ import annotations

import logging
import secrets
import string
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import get_settings
from src.core.exceptions.auth import AuthenticationError, ConflictError, NotFoundError
from src.core.services.auth_service import AuthService
from src.core.services.email_service import email_service
from src.data.models.postgres.team import Team
from src.data.models.postgres.user import User
from src.data.repositories.team_repository import TeamRepository
from src.data.repositories.user_repository import UserRepository
from src.schemas.team_schema import (
    AddMemberRequest,
    MemberCreateRequest,
    TeamCreateRequest,

)
from src.schemas.auth import SignupRequest
logger = logging.getLogger(__name__)


class TeamService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._team_repo = TeamRepository(session)
        self._user_repo = UserRepository(session)
        self._auth_svc = AuthService(session)

    # ------------------------------------------------------------------ #
    # Team CRUD                                                            #
    # ------------------------------------------------------------------ #

    async def create_team(self, payload: TeamCreateRequest) -> tuple[Team, list[User]]:
        """
        1. Validate team name is unique.
        2. Find the team_lead member — create them first, get their user.id.
        3. Create Team row with lead_id = new lead's user.id.
        4. Create remaining members with lead_id = lead's user.id.
        """
        if await self._team_repo.get_by_name(payload.name):
            raise ConflictError(f"Team '{payload.name}' already exists.")

        # Split lead from regular members (schema guarantees exactly one lead)
        lead_payload = next(m for m in payload.members if m.role.value == "team_lead")
        other_members = [m for m in payload.members if m.role.value != "team_lead"]

        # Create lead user first — no lead_id on themselves (they ARE the lead)
        lead_user = await self._create_and_invite_member(
            lead_id=None,
            team_name=payload.name,
            payload=lead_payload,
        )

        # Create team row now that we have the lead's id
        team = Team(
            name=payload.name,
            description=payload.description,
            lead_id=str(lead_user.id),
        )
        team = await self._team_repo.save(team)
        logger.info("team_created: id=%s name=%r lead=%s", team.id, team.name, lead_user.id)

        # Create remaining members with lead_id pointing to the new lead
        members: list[User] = [lead_user]
        for member_payload in other_members:
            user = await self._create_and_invite_member(
                lead_id=lead_user.id,
                team_name=team.name,
                payload=member_payload,
            )
            members.append(user)

        await self._session.commit()
        return team, members

    async def get_team(self, team_id: UUID) -> tuple[Team, list[User]]:
        team = await self._team_repo.get_by_id(team_id)
        if not team:
            raise NotFoundError(f"Team {team_id} not found.")
        members = await self._user_repo.get_agents_by_lead(str(team.lead_id))
        return team, members

    async def list_teams(self) -> tuple[int, list[tuple[Team, list[User]]]]:
        total, teams = await self._team_repo.list_all()
        result = []
        for team in teams:
            members = (
                await self._user_repo.get_agents_by_lead(str(team.lead_id))
                if team.lead_id else []
            )
            result.append((team, members))
        return total, result

    async def delete_team(self, team_id: UUID) -> None:
        team = await self._team_repo.get_by_id(team_id)
        if not team:
            raise NotFoundError(f"Team {team_id} not found.")

        if team.lead_id:
            members = await self._user_repo.get_agents_by_lead(str(team.lead_id))
            for member in members:
                member.lead_id = None
                await self._user_repo.save(member)

        await self._team_repo.delete(team)
        await self._session.commit()
        logger.info("team_deleted: id=%s", team_id)

    # ------------------------------------------------------------------ #
    # Member management                                                    #
    # ------------------------------------------------------------------ #

    async def add_member(self, team_id: UUID, payload: AddMemberRequest) -> User:
        team = await self._team_repo.get_by_id(team_id)
        if not team:
            raise NotFoundError(f"Team {team_id} not found.")
        if not team.lead_id:
            raise ConflictError(f"Team {team_id} has no lead assigned.")

        user = await self._create_and_invite_member(
            lead_id=UUID(str(team.lead_id)),
            team_name=team.name,
            payload=MemberCreateRequest(
                email=payload.email,
                full_name=payload.full_name,
                role=payload.role,
            ),
        )
        await self._session.commit()
        return user

    async def remove_member(self, team_id: UUID, user_id: UUID) -> None:
        team = await self._team_repo.get_by_id(team_id)
        if not team:
            raise NotFoundError(f"Team {team_id} not found.")

        user = await self._user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User {user_id} not found.")

        if str(user.lead_id) != str(team.lead_id):
            raise ConflictError(f"User {user_id} is not a member of team {team_id}.")

        user.lead_id = None
        await self._user_repo.save(user)
        await self._session.commit()
        logger.info("member_removed: user=%s team=%s", user_id, team_id)

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    async def _create_and_invite_member(
    self,
    lead_id: UUID | None,
    team_name: str,
    payload: MemberCreateRequest,
) -> User:

        temp_password = _generate_temp_password()

        try:
            signup_data = SignupRequest(
                email=payload.email,
                full_name=payload.full_name,
                password=temp_password,
                role=payload.role.value,
            )

            user_response = await self._auth_svc.signup(signup_data)

            user = await self._user_repo.get_by_id(user_response.id)

            if lead_id:
                user.lead_id = str(lead_id)
                await self._user_repo.save(user)

        except AuthenticationError:
            raise ConflictError(f"Email '{payload.email}' is already registered.")

        settings = get_settings()

        try:
            email_service.send_team_invite(
                to=payload.email,
                full_name=payload.full_name,
                role=payload.role.value,
                team_name=team_name,
                temporary_password=temp_password,
                login_url=settings.FRONTEND_URL + "/login",
            )
        except Exception:
            logger.exception("invite_email_failed")

        return user


def _generate_temp_password(length: int = 12) -> str:
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        while True:
            pwd = "".join(secrets.choice(alphabet) for _ in range(length))
            if (
                any(c.isupper() for c in pwd)
                and any(c.islower() for c in pwd)
                and any(c.isdigit() for c in pwd)
                and any(c in "!@#$%^&*" for c in pwd)
            ):
                return pwd