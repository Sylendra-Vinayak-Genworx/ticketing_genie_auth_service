from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.postgres.user import User
from src.data.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User entity operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> User | None:
        """
        Find user by email address.
        """
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        """Check if email is already registered."""
        result = await self.session.execute(
            select(User.id).where(User.email == email)
        )
        return result.scalar_one_or_none() is not None
    
    async def get_agents_by_lead(self, lead_id: str) -> list[User]:
        """Get all agents associated with a specific lead."""
        result = await self.session.execute(
            select(User).where(User.lead_id == lead_id)
        )
        return result.scalars().all()
    
    async def get_all_user(self) -> list[User]:
        result= await self.session.execute(
            select(User)
        )
        return result.scalars().all()