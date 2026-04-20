import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.rest.dependencies.auth import get_current_active_user, role_required
from src.config.settings import get_settings
from src.core.services.auth_service import AuthService
from src.core.services.email_service import email_service
from src.core.services.team_service import generate_temp_password
from src.data.clients.postgres_client import get_db
from src.data.models.postgres.user import User
from src.data.repositories.user_repository import UserRepository
from src.data.repositories.team_repository import TeamRepository
from src.observability.logging.logger import get_logger
from src.schemas.auth import (
    AccessTokenResponse,
    ForgotPasswordRequest,
    LoginRequest,
    ProvisionExternalRequest,
    ResetPasswordRequest,
    SignupRequest,
    SignupResponse,
    UserCreateRequest,
    UserCreateResponse,
    UserResponse,
    UserUpdateRequest,
)
from src.utils.security import clear_auth_cookies, set_auth_cookies

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])
_admin = Depends(role_required("admin"))


def _get_service(session: Annotated[AsyncSession, Depends(get_db)]) -> AuthService:
    return AuthService(session=session)


# ── SIGNUP ───────────────────────────────────────────────────────────────────
@router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=201,
    summary="User signup",
    description="Create a new user account with the provided details.",
)
async def signup(
    data: SignupRequest,
    service: Annotated[AuthService, Depends(_get_service)],
) -> SignupResponse:
    """
    Signup.

    Args:
        data (SignupRequest): Input parameter.
        service (Annotated[AuthService, Depends(_get_service)]): Input parameter.

    Returns:
        SignupResponse: The expected output.
    """
    user = await service.signup(data)
    return SignupResponse(user=user)


# ── LOGIN ────────────────────────────────────────────────────────────────────
@router.post(
    "/login",
    response_model=AccessTokenResponse,
    summary="User login",
    description="Authenticate a user and return an access token.",
)
async def login(
    data: LoginRequest,
    response: Response,
    service: Annotated[AuthService, Depends(_get_service)],
) -> AccessTokenResponse:
    """
    Login.

    Args:
        data (LoginRequest): Input parameter.
        response (Response): Input parameter.
        service (Annotated[AuthService, Depends(_get_service)]): Input parameter.

    Returns:
        AccessTokenResponse: The expected output.
    """
    tokens = await service.login(data)
    set_auth_cookies(response, tokens.refresh_token)
    return AccessTokenResponse(
        access_token=tokens.access_token,
        expires_in=tokens.expires_in,
    )


# ── REFRESH ──────────────────────────────────────────────────────────────────
@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    summary="Refresh access token",
    description="Obtain a new access token using a valid refresh token.",
)
async def refresh(
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(_get_service)],
) -> AccessTokenResponse:
    """
    Refresh.

    Args:
        request (Request): Input parameter.
        response (Response): Input parameter.
        service (Annotated[AuthService, Depends(_get_service)]): Input parameter.

    Returns:
        AccessTokenResponse: The expected output.
    """
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token provided")
    tokens = await service.refresh(refresh_token)
    set_auth_cookies(response, tokens.refresh_token)
    return AccessTokenResponse(
        access_token=tokens.access_token,
        expires_in=tokens.expires_in,
    )


@router.post(
    "/logout",
    response_model=None,
    status_code=204,
    summary="User logout",
    description="Logout the user by invalidating the refresh token.",
)
async def logout(
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(_get_service)],
    _current_user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    """
    Logout.

    Args:
        request (Request): Input parameter.
        response (Response): Input parameter.
        service (Annotated[AuthService, Depends(_get_service)]): Input parameter.
        _current_user (Annotated[User, Depends(get_current_active_user)]): Input parameter.
    """
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        await service.logout(refresh_token)
    clear_auth_cookies(response)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Retrieve the profile of the currently authenticated user.",
)
async def me(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """
    Me.
    """
    user_response = UserResponse.model_validate(current_user)
    
    # Resolve team_id for the response
    team_repo = TeamRepository(session)
    
    # If user is a lead, they lead a specific team
    is_lead = False
    if current_user.role and hasattr(current_user.role.name, "value"):
        is_lead = current_user.role.name.value == "team_lead"
    elif current_user.role:
        is_lead = str(current_user.role.name) == "team_lead"
        
    if is_lead:
        team = await team_repo.get_by_lead_id(current_user.id)
        if team:
            user_response.team_id = team.id
    elif current_user.lead_id:
        # If user is an agent, they belong to the team their lead leads
        lead_id = current_user.lead_id
        if isinstance(lead_id, str):
            try:
                lead_id = uuid.UUID(lead_id)
            except ValueError:
                lead_id = None
        
        if lead_id:
            team = await team_repo.get_by_lead_id(lead_id)
            if team:
                user_response.team_id = team.id
            
    return user_response


@router.get(
    "/users",
    response_model=list[UserResponse],
    tags=["Internal"],
    summary="Get all users",
    description="Retrieve a list of all users.",
)
async def get_all_users(
    service: Annotated[AuthService, Depends(_get_service)],
) -> list[UserResponse]:
    """
    Get all users.

    Args:
        service (Annotated[AuthService, Depends(_get_service)]): Input parameter.

    Returns:
        list[UserResponse]: The expected output.
    """
    users = await service.get_all_users()
    return users


@router.post(
    "/admin/users",
    response_model=UserCreateResponse,
    status_code=201,
    summary="Create a new user (Admin only)",
    description="Create a new user with administrative privileges and send an invite email.",
    dependencies=[_admin],
)
async def create_user_admin(
    data: UserCreateRequest,
    service: Annotated[AuthService, Depends(_get_service)],
) -> UserCreateResponse:
    # Generate temp password
    """
    Create user admin.

    Args:
        data (UserCreateRequest): Input parameter.
        service (Annotated[AuthService, Depends(_get_service)]): Input parameter.

    Returns:
        UserCreateResponse: The expected output.
    """
    temp_password = generate_temp_password()

    # Create the user using Auth Service (signup handles role creation and hashing)
    signup_data = SignupRequest(
        email=data.email,
        full_name=data.full_name,
        password=temp_password,
        role=data.role.value,
    )
    user_response = await service.signup(signup_data)

    # Send invite email
    try:
        email_service.send_user_invite(
            to=data.email,
            full_name=data.full_name,
            role=data.role.value,
            temporary_password=temp_password,
            login_url=get_settings().FRONTEND_URL + "/login",
        )
    except Exception:
        logger.exception("user_invite_email_failed")

    return UserCreateResponse(user=user_response, temporary_password=temp_password)


@router.get(
    "/users/by-email",
    response_model=UserResponse,
    tags=["Internal"],
    summary="Get user by email — internal use by Ticketing Service",
    description="Retrieve a user's details using their email address.",
)
async def get_user_by_email(
    email: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """
    Get user by email.

    Args:
        email (str): Input parameter.
        session (Annotated[AsyncSession, Depends(get_db)]): Input parameter.

    Returns:
        UserResponse: The expected output.
    """
    repo = UserRepository(session)
    user = await repo.get_by_email(email.lower().strip())
    if not user:
        raise HTTPException(
            status_code=404, detail=f"User with email '{email}' not found"
        )
    return UserResponse.model_validate(user)


@router.get(
    "/users/{user_id}",
    response_model=UserResponse,
    tags=["Internal"],
    summary="Get user by UUID — internal use by Ticketing Service",
    description="Retrieve a user's details using their unique UUID.",
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
    description="Retrieve a list of agents associated with a specific lead.",
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
    description="Provision a provisional account for an external customer.",
    status_code=201,
)
async def provision_external_user(
    data: ProvisionExternalRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """
    Provision external user.

    Args:
        data (ProvisionExternalRequest): Input parameter.
        session (Annotated[AsyncSession, Depends(get_db)]): Input parameter.

    Returns:
        UserResponse: The expected output.
    """
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
    description="Update a user's profile details or customer tier.",
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


# ── FORGOT PASSWORD ──────────────────────────────────────────────────────────
@router.post(
    "/forgot-password",
    response_model=dict,
    status_code=200,
    summary="Forgot password",
    description="Request a password reset link to be sent to the user's email address.",
)
async def forgot_password(
    data: ForgotPasswordRequest,
    service: Annotated[AuthService, Depends(_get_service)],
) -> dict:
    """
    Forgot password.

    Args:
        data (ForgotPasswordRequest): Input parameter.
        service (Annotated[AuthService, Depends(_get_service)]): Input parameter.

    Returns:
        dict: The expected output.
    """
    token = await service.forgot_password(data.email)
    if token:
        try:
            reset_url = f"{get_settings().FRONTEND_URL}/reset-password?token={token}"
            user = await service._user_repo.get_by_email(data.email.lower().strip())
            email_service.send_password_reset(
                to=data.email,
                full_name=user.full_name or "",
                reset_url=reset_url,
            )
        except Exception:
            logger.exception("password_reset_email_failed")
    # Always return success to prevent user enumeration
    return {
        "message": "If that email is registered, you will receive a password reset link."
    }


@router.post(
    "/reset-password",
    response_model=dict,
    status_code=200,
    summary="Reset password",
    description="Reset the user's password using the provided token.",
)
async def reset_password(
    data: ResetPasswordRequest,
    service: Annotated[AuthService, Depends(_get_service)],
) -> dict:
    """
    Reset password.

    Args:
        data (ResetPasswordRequest): Input parameter.
        service (Annotated[AuthService, Depends(_get_service)]): Input parameter.

    Returns:
        dict: The expected output.
    """
    await service.reset_password(data.token, data.new_password)
    return {
        "message": "Password has been reset successfully. Please log in with your new password."
    }
