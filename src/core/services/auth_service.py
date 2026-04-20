import uuid
from datetime import UTC, datetime, timedelta

from jose import ExpiredSignatureError, JWTError
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import get_settings
from src.core.exceptions.auth import (
    AuthenticationError,
    ConflictError,
    InvalidTokenTypeError,
    TokenExpiredError,
    TokenRevokedError,
)
from src.data.models.postgres.role import Role
from src.data.models.postgres.token import RefreshToken
from src.data.models.postgres.user import User
from src.data.repositories.token_repository import TokenRepository
from src.data.repositories.user_repository import UserRepository
from src.observability.logging.logger import get_logger
from src.schemas.auth import LoginRequest, SignupRequest, TokenResponse, UserResponse
from src.utils.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

logger = get_logger(__name__)
settings = get_settings()

pwd = CryptContext(schemes=["argon2"])
_DUMMY_HASH = pwd.hash("dummy_password")


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        """
          init  .

        Args:
            session (AsyncSession): Input parameter.
        """
        self._session = session
        self._user_repo = UserRepository(session)
        self._token_repo = TokenRepository(session)

    # ── SIGNUP ──────────────────────────────────────────────────────────────
    async def signup(self, data: SignupRequest) -> UserResponse:
        """
        Signup.

        Args:
            data (SignupRequest): Input parameter.

        Returns:
            UserResponse: The expected output.
        """
        if await self._user_repo.email_exists(data.email):
            logger.warning("signup_duplicate_email", email=data.email)
            # FIX: was AuthenticationError("Unable to create account") which
            # returned 401, causing the frontend axios interceptor to treat it
            # as an expired token and attempt a pointless refresh cycle.
            # A duplicate email is a conflict (409), not an auth failure (401).
            raise ConflictError("An account with this email already exists")

        result = await self._session.execute(select(Role).where(Role.name == data.role))
        role_record = result.scalar_one_or_none()
        if role_record is None:
            role_record = Role(name=data.role)
            self._session.add(role_record)
            await self._session.flush()

        user = User(
            email=data.email.lower().strip(),
            hashed_password=hash_password(data.password),
            role_id=role_record.id,
            full_name=data.full_name,
        )
        saved = await self._user_repo.save(user)
        logger.info("signup_success", email=data.email, user_id=str(saved.id))
        return UserResponse.model_validate(saved)

    # ── LOGIN ────────────────────────────────────────────────────────────────
    async def login(self, data: LoginRequest) -> TokenResponse:
        """
        Login.

        Args:
            data (LoginRequest): Input parameter.

        Returns:
            TokenResponse: The expected output.
        """
        user = await self._user_repo.get_by_email(data.email.lower().strip())

        password_valid = verify_password(
            data.password,
            user.hashed_password if user else _DUMMY_HASH,
        )
        if not user or not password_valid or not user.is_active:
            logger.warning("login_failed", email=data.email)
            raise AuthenticationError()

        await self._token_repo.cleanup_expired(user.id)
        tokens = await self._issue_token_pair(user)
        logger.info("login_success", email=data.email, user_id=str(user.id))
        return tokens

    # ── REFRESH ──────────────────────────────────────────────────────────────
    async def refresh(self, refresh_token: str) -> TokenResponse:
        # 1. Decode
        """
        Refresh.

        Args:
            refresh_token (str): Input parameter.

        Returns:
            TokenResponse: The expected output.
        """
        try:
            payload = decode_token(refresh_token)
        except ExpiredSignatureError:
            raise TokenExpiredError()
        except JWTError as err:
            raise AuthenticationError("Invalid token") from err

        # 2. Validate token type
        if payload.get("token_type") != "refresh":
            raise InvalidTokenTypeError()

        jti: str = payload["jti"]
        user_id: str = payload["sub"]

        # 3. Look up stored token
        stored = await self._token_repo.get_by_jti(jti)
        if stored is None:
            raise AuthenticationError("Token not found")

        # 4. Reuse detection — if already revoked, revoke ALL tokens for user
        if stored.revoked:
            logger.warning(
                "refresh_token_reuse_detected",
                jti=jti,
                user_id=user_id,
            )
            await self._token_repo.revoke_all_for_user(stored.user_id)
            raise TokenRevokedError()

        # 5. Revoke old token (rotation)
        await self._token_repo.revoke(stored)

        # 6. Load user and issue new pair
        user = await self._user_repo.get_by_id(stored.user_id)
        if not user or not user.is_active:
            raise AuthenticationError()

        tokens = await self._issue_token_pair(user)
        logger.info("token_refreshed", user_id=user_id)
        return tokens

    async def logout(self, refresh_token: str) -> None:
        """
        Logout.

        Args:
            refresh_token (str): Input parameter.
        """
        try:
            payload = decode_token(refresh_token)
        except Exception:
            return

        jti = payload.get("jti")
        if not jti:
            return

        stored = await self._token_repo.get_by_jti(jti)
        if stored and not stored.revoked:
            await self._token_repo.revoke(stored)
            logger.info("logout_success", jti=jti)

    # ── INTERNAL ─────────────────────────────────────────────────────────────
    async def _issue_token_pair(self, user: User) -> TokenResponse:
        jti = str(uuid.uuid4())
        role_name = (
            user.role.name.value
            if hasattr(user.role.name, "value")
            else str(user.role.name)
        )

        access_token = create_access_token(
            subject=str(user.id),
            role=role_name,
            jti=str(uuid.uuid4()),
        )
        refresh_token_str = create_refresh_token(
            subject=str(user.id),
            jti=jti,
        )

        # Persist refresh token
        expires_at = datetime.now(UTC) + timedelta(
            days=settings.refresh_token_expire_days
        )
        refresh_record = RefreshToken(
            user_id=user.id,
            jti=jti,
            expires_at=expires_at,
            revoked=False,
        )
        self._session.add(refresh_record)
        await self._session.flush()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token_str,
            expires_in=settings.access_token_expire_minutes * 60,
        )

    async def get_agents_by_lead(self, lead_id: str) -> list[UserResponse]:
        """Get all agents associated with a specific lead."""
        agents = await self._user_repo.get_agents_by_lead(lead_id)
        return [UserResponse.model_validate(agent) for agent in agents]

    async def get_all_users(self) -> list[UserResponse]:
        """Get all the users."""
        users = await self._user_repo.get_all_user()
        return users
