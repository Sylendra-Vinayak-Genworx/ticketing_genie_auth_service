from typing import Any

from fastapi import status


class ApplicationError(Exception):
    """
    Root exception for all application errors.
    Designed to be caught by a global FastAPI exception handler.
    """

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = "An unexpected error occurred."
    headers: dict[str, str] | None = None

    def __init__(
        self,
        *,
        status_code: int | None = None,
        detail: str | None = None,
        headers: dict[str, str] | None = None,
        details: Any = None,
    ) -> None:
        self.status_code = status_code or self.__class__.status_code
        self.detail = detail or self.__class__.detail
        self.headers = headers or self.__class__.headers
        self.details = details
        super().__init__(self.detail)


class AuthenticationError(ApplicationError):
    """Generic authentication failure — avoids user enumeration."""

    def __init__(self, detail: str = "Invalid credentials") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class AuthorizationError(ApplicationError):
    """User is authenticated but lacks permission."""

    def __init__(self, detail: str = "Insufficient permissions") -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class TokenExpiredError(ApplicationError):
    """JWT has expired."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )


class TokenRevokedError(ApplicationError):
    """Token has been explicitly revoked (logout or reuse detection)."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )


class InvalidTokenTypeError(ApplicationError):
    """Token type mismatch (e.g., refresh used as access)."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── Resource / Business Rule ───────────────────────────────────────────────────

class NotFoundError(ApplicationError):
    """A requested resource does not exist."""

    def __init__(self, detail: str = "Resource not found") -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        )


class ConflictError(ApplicationError):
    """A uniqueness or business-rule constraint was violated."""

    def __init__(self, detail: str = "Conflict") -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )