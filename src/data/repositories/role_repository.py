from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.constants.enum import UserRole
from src.data.models.postgres.role import Role
from src.data.repositories.base import BaseRepository


class RoleRepository(BaseRepository[Role]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Role, session)

    async def get_by_name(self, role: UserRole) -> Role | None:
        result = await self.session.execute(
            select(Role).where(Role.name == role)
        )
        return result.scalar_one_or_none()