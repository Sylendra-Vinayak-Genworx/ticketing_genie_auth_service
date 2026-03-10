import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from src.constants.enum import UserRole


class SignupRequest(BaseModel):
    """Request body for user registration."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = Field(default=UserRole.USER, description="User role")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123!",
                "role": "user"
            }
        }
    )


class LoginRequest(BaseModel):
    """Request body for user login."""

    email: EmailStr
    password: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123!"
            }
        }
    )


class RefreshRequest(BaseModel):
    """Request body for token refresh."""

    refresh_token: str


    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }
    )


class LogoutRequest(BaseModel):
    """Request body for logout."""

    refresh_token: str


class TokenResponse(BaseModel):
    """Token pair returned on login/refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token TTL in seconds")


class UserResponse(BaseModel):
    """Public user data — never includes password."""

    id: uuid.UUID
    email: str
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    lead_id:uuid.UUID | None
    team_id:uuid.UUID|None
    
    model_config = ConfigDict(from_attributes=True)

    @field_validator("role", mode="before")
    @classmethod
    def extract_role_name(cls, v):
        """Handle Role ORM object → plain string."""
        if hasattr(v, "name"):
            name = v.name
            return name.value if hasattr(name, "value") else str(name)
        return str(v)


class SignupResponse(BaseModel):
    """Response after successful registration."""

    user: UserResponse
    message: str = "Account created successfully"

class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class ProvisionExternalRequest(BaseModel):
    email: EmailStr
    role: str = "user"
    full_name: str = ""
