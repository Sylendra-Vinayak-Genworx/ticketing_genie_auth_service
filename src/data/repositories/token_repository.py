from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.postgres.token import RefreshToken
from src.data.repositories.base import BaseRepository


class TokenRepository(BaseRepository[RefreshToken]):


    def __init__(self, session: AsyncSession) -> None:
        super().__init__(RefreshToken, session)

    async def get_by_jti(self, jti: str) -> RefreshToken | None:
        """
        Find a refresh token record by its JWT ID.
        """
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.jti == jti)
        )
        return result.scalar_one_or_none()

    async def revoke(self, token: RefreshToken) -> None:
        """
        Mark a single refresh token as revoked.
        """
        token.revoked = True
        await self.session.flush()

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        """
        Immediately revoke ALL active refresh tokens for a user.
        """
        await self.session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked.is_(False),
            )
            .values(revoked=True)
        )
        await self.session.flush()

    async def count_active_sessions(self, user_id: UUID) -> int:
        """
        Count how many active (non-revoked, non-expired) sessions a user has.
        """
        now = datetime.now(UTC)
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked.is_(False),
                RefreshToken.expires_at > now,
            )
        )
        return len(result.scalars().all())

    async def cleanup_expired(self, user_id: UUID) -> None:
        """
        Revoke expired tokens for a user during login.
        """
        now = datetime.now(UTC)
        await self.session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.expires_at <= now,
                RefreshToken.revoked.is_(False),
            )
            .values(revoked=True)
        )
        await self.session.flush()
