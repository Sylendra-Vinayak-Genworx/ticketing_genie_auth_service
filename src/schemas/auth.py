import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from src.constants.enum import ContactMode, UserRole


class SignupRequest(BaseModel):
    """Request body for user registration."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)
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
    full_name: str | None = None
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    lead_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None          # optional — no column on User, only a relationship
    preferred_mode_of_contact: str = "email"  # ContactMode.EMAIL default
    customer_tier_id: int | None = Field(default=None, validation_alias="customer_tierid")

    model_config = ConfigDict(from_attributes=True)

    @field_validator("role", mode="before")
    @classmethod
    def extract_role_name(cls, v):
        """Handle Role ORM object → plain string."""
        if hasattr(v, "name"):
            name = v.name
            return name.value if hasattr(name, "value") else str(name)
        return str(v)

    @field_validator("preferred_mode_of_contact", mode="before")
    @classmethod
    def extract_contact_mode(cls, v):
        """Handle ContactMode enum → plain string."""
        if v is None:
            return "email"
        return v.value if hasattr(v, "value") else str(v)

    @field_validator("customer_tier_id", mode="before")
    @classmethod
    def map_customer_tier(cls, v):
        """ORM column is customer_tierid — tolerate None."""
        return v


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


class UserUpdateRequest(BaseModel):
    """Payload for updating user profile / tier."""

    full_name: str | None = None
    is_active: bool | None = None
    customer_tier_id: int | None = None
    preferred_mode_of_contact: ContactMode | None = None


class UserCreateRequest(BaseModel):
    """Payload for creating a user independently."""
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    role: UserRole

class UserCreateResponse(BaseModel):
    """Response returning the created user and their temporary password."""
    user: UserResponse
    temporary_password: str