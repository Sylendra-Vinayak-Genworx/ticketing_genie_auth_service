import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from fastapi import Response
from jose import jwt
from passlib.context import CryptContext

from src.config.settings import get_settings

settings = get_settings()


pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto"
)


def hash_password(password: str) -> str:
    """Hash a plaintext password using argon2."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password using constant-time comparison.
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    subject: str,
    role: str,
    jti: str | None = None,
) -> str:
    """
    Create a short-
    set_auth_cookies(response, tokens.refresh_token)
    return AccessTokenResponse(
        access_token=tokens.access_token,
        expires_in=tokens.expires_in,
    )lived JWT access token.
    """
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)

    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "jti": jti or str(uuid.uuid4()),
        "token_type": "access",
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(subject: str, jti: str) -> str:
    """
    Create a long-lived JWT refresh token.
    """
    now = datetime.now(UTC)
    expire = now + timedelta(days=settings.refresh_token_expire_days)

    payload: dict[str, Any] = {
        "sub": subject,
        "jti": jti,
        "token_type": "refresh",
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token signature and expiry.
    """
    return dict(
        jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    )

def set_auth_cookies(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,       
        samesite=settings.cookie_samesite,   
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/api/v1/auth",                 
    )

def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(
        key="refresh_token",
        path="/api/v1/auth"
    )