from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.postgres.password_reset_token import PasswordResetToken


class PasswordResetTokenRepository:
    """Repository for password-reset token operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, token: PasswordResetToken) -> PasswordResetToken:
        self._session.add(token)
        await self._session.flush()
        return token

    async def get_valid_token(self, token_str: str) -> PasswordResetToken | None:
        """Return a token that is not used and not expired."""
        result = await self._session.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token == token_str,
                PasswordResetToken.used == False,  # noqa: E712
                PasswordResetToken.expires_at > datetime.now(UTC),
            )
        )
        return result.scalar_one_or_none()

    async def mark_used(self, token: PasswordResetToken) -> None:
        token.used = True
        await self._session.flush()

    async def invalidate_all_for_user(self, user_id) -> None:
        """Mark all unused tokens for a user as used."""
        await self._session.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.used == False,  # noqa: E712
            )
            .values(used=True)
        )
        await self._session.flush()
