from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.data.models.postgres.team import Team
from src.data.repositories.base import BaseRepository


class TeamRepository(BaseRepository[Team]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Team, session)

    async def get_by_name(self, name: str) -> Team | None:
        result = await self.session.execute(
            select(Team).where(Team.name == name)
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> tuple[int, list[Team]]:
        count_result = await self.session.execute(
            select(func.count()).select_from(Team)
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            select(Team).options(joinedload(Team.lead))
        )
        return total, list(result.scalars().unique().all())

    async def get_by_lead_id(self, lead_id: UUID) -> Team | None:
        result = await self.session.execute(
            select(Team).where(Team.lead_id == str(lead_id))
        )
        return result.scalar_one_or_none()