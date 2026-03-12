from typing import Annotated
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.rest.dependencies.auth import get_current_active_user
from src.core.services.auth_service import AuthService
from src.data.clients.postgres_client import get_db
from src.data.models.postgres.user import User
from src.data.repositories.user_repository import UserRepository
from src.observability.logging.logger import get_logger
from src.schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    SignupRequest,
    SignupResponse,
    TokenResponse,
    UserResponse,
    UserUpdateRequest,
)
from src.utils.security import clear_auth_cookies, set_auth_cookies
from src.schemas.auth import ProvisionExternalRequest

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


def _get_service(session: Annotated[AsyncSession, Depends(get_db)]) -> AuthService:
    return AuthService(session=session)


# ── SIGNUP ───────────────────────────────────────────────────────────────────
@router.post("/signup", response_model=SignupResponse, status_code=201)
async def signup(
    data: SignupRequest,
    service: Annotated[AuthService, Depends(_get_service)],
) -> SignupResponse:
    user = await service.signup(data)
    return SignupResponse(user=user)


# ── LOGIN ────────────────────────────────────────────────────────────────────
@router.post("/login", response_model=AccessTokenResponse)
async def login(
    data: LoginRequest,
    response: Response,
    service: Annotated[AuthService, Depends(_get_service)],
) -> AccessTokenResponse:
    tokens = await service.login(data)
    set_auth_cookies(response, tokens.refresh_token)
    return AccessTokenResponse(
        access_token=tokens.access_token,
        expires_in=tokens.expires_in,
    )


# ── REFRESH ──────────────────────────────────────────────────────────────────
@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(_get_service)],
) -> AccessTokenResponse:
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token provided")
    tokens = await service.refresh(refresh_token)
    set_auth_cookies(response, tokens.refresh_token)
    return AccessTokenResponse(
        access_token=tokens.access_token,
        expires_in=tokens.expires_in,
    )



@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(_get_service)],
    _current_user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        await service.logout(refresh_token)
    clear_auth_cookies(response)


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> UserResponse:
    return UserResponse.model_validate(current_user)

@router.get(
        "/users",
        response_model=list[UserResponse],
        tags=["Internal"]
)
async def get_all_users(service:Annotated[AuthService,Depends(_get_service)]):
    users=await service.get_all_users()
    return users
    
@router.get(
    "/users/by-email",
    response_model=UserResponse,
    tags=["Internal"],
    summary="Get user by email — internal use by Ticketing Service",
)
async def get_user_by_email(
    email: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    repo = UserRepository(session)
    user = await repo.get_by_email(email.lower().strip())
    if not user:
        raise HTTPException(status_code=404, detail=f"User with email '{email}' not found")
    return UserResponse.model_validate(user)


@router.get(
    "/users/{user_id}",
    response_model=UserResponse,
    tags=["Internal"],
    summary="Get user by UUID — internal use by Ticketing Service",
)
async def get_user_by_id(
    user_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """
    Internal endpoint consumed by Ticketing Service to resolve user details.
    Accepts the UUID string from the JWT sub claim.
    """
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid UUID: '{user_id}'")

    repo = UserRepository(session)
    user = await repo.get_by_id(uid)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    return UserResponse.model_validate(user)


@router.get(
    "/leads/{lead_id}/agents",
    response_model=list[UserResponse],
    tags=["Internal"],
    summary="Get agents by lead ID — internal use by Ticketing Service",
)
async def get_agents_by_lead(
    lead_id: str,
    service: Annotated[AuthService, Depends(_get_service)],
) -> list[UserResponse]:
    """
    Internal endpoint consumed by Ticketing Service to get all agents associated with a specific lead.
    """
    return await service.get_agents_by_lead(lead_id)



@router.post(
    "/provision-external",
    response_model=UserResponse,
    tags=["Internal"],
    summary="Provision a provisional customer account — internal use by Ticketing Service",
    status_code=201,
)
async def provision_external_user(
    data: ProvisionExternalRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    repo = UserRepository(session)

    existing = await repo.get_by_email(data.email.lower().strip())
    if existing:
        return UserResponse.model_validate(existing)

    return None


@router.patch(
    "/users/{user_id}",
    response_model=UserResponse,
    tags=["Internal"],
    summary="Update user profile / tier — internal use by Ticketing Service",
)
async def update_user(
    user_id: str,
    data: UserUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """
    Internal endpoint to update user fields like customer_tier_id, full_name, etc.
    """
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid UUID: '{user_id}'")

    repo = UserRepository(session)
    user = await repo.get_by_id(uid)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    if data.full_name is not None:
        user.full_name = data.full_name
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.customer_tier_id is not None:
        user.customer_tierid = data.customer_tier_id
    if data.preferred_mode_of_contact is not None:
        user.preferred_mode_of_contact = data.preferred_mode_of_contact

    await repo.save(user)
    await session.commit()
    return UserResponse.model_validate(user)