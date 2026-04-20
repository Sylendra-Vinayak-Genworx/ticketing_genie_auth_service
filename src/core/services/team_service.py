from __future__ import annotations

import logging
import secrets
import string
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions.auth import ConflictError, NotFoundError
from src.core.services.auth_service import AuthService
from src.data.models.postgres.team import Team
from src.data.models.postgres.user import User
from src.data.repositories.team_repository import TeamRepository
from src.data.repositories.user_repository import UserRepository
from src.schemas.team_schema import (
    AddMemberRequest,
    TeamCreateRequest,
)

logger = logging.getLogger(__name__)


class TeamService:
    def __init__(self, session: AsyncSession) -> None:
        """
          init  .

        Args:
            session (AsyncSession): Input parameter.
        """
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
        2. Validate lead_id exists.
        3. Create Team row with lead_id.
        4. Update lead_id on members.
        """
        if await self._team_repo.get_by_name(payload.name):
            raise ConflictError(f"Team '{payload.name}' already exists.")

        lead_user = await self._user_repo.get_by_id(payload.lead_id)
        if not lead_user:
            raise NotFoundError(f"Lead user {payload.lead_id} not found.")

        # Create team row
        team = Team(
            name=payload.name,
            description=payload.description,
            lead_id=str(lead_user.id),
        )
        team = await self._team_repo.save(team)
        logger.info(
            "team_created: id=%s name=%r lead=%s", team.id, team.name, lead_user.id
        )

        # Update members
        members: list[User] = [lead_user]
        for member_id in payload.member_ids:
            if member_id == lead_user.id:
                continue
            user = await self._user_repo.get_by_id(member_id)
            if user:
                user.lead_id = str(lead_user.id)
                await self._user_repo.save(user)
                members.append(user)

        await self._session.commit()
        return team, members

    async def get_team(self, team_id: UUID) -> tuple[Team, list[User]]:
        """
        Get team.

        Args:
            team_id (UUID): Input parameter.

        Returns:
            tuple[Team, list[User]]: The expected output.
        """
        team = await self._team_repo.get_by_id(team_id)
        if not team:
            raise NotFoundError(f"Team {team_id} not found.")
        members = await self._user_repo.get_agents_by_lead(str(team.lead_id))
        return team, members

    async def list_teams(self) -> tuple[int, list[tuple[Team, list[User]]]]:
        """
        List teams.

        Returns:
            tuple[int, list[tuple[Team, list[User]]]]: The expected output.
        """
        total, teams = await self._team_repo.list_all()
        result = []
        for team in teams:
            members = (
                await self._user_repo.get_agents_by_lead(str(team.lead_id))
                if team.lead_id
                else []
            )
            result.append((team, members))
        return total, result

    async def delete_team(self, team_id: UUID) -> None:
        """
        Delete team.

        Args:
            team_id (UUID): Input parameter.
        """
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
        """
        Add member.

        Args:
            team_id (UUID): Input parameter.
            payload (AddMemberRequest): Input parameter.

        Returns:
            User: The expected output.
        """
        team = await self._team_repo.get_by_id(team_id)
        if not team:
            raise NotFoundError(f"Team {team_id} not found.")
        if not team.lead_id:
            raise ConflictError(f"Team {team_id} has no lead assigned.")

        user = await self._user_repo.get_by_id(payload.user_id)
        if not user:
            raise NotFoundError(f"User {payload.user_id} not found.")

        user.lead_id = str(team.lead_id)
        await self._user_repo.save(user)
        await self._session.commit()
        return user

    async def remove_member(self, team_id: UUID, user_id: UUID) -> None:
        """
        Remove member.

        Args:
            team_id (UUID): Input parameter.
            user_id (UUID): Input parameter.
        """
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


def generate_temp_password(length: int = 12) -> str:
    """Generate a random temporary password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #
