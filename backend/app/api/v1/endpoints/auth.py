from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.token import MessageResponse, RefreshTokenRequest, Token
from app.schemas.user import UserLogin, UserRegister, UserResponse
from app.services.auth_service import AuthService

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user account",
    description="Registers a new user with Argon2 password hashing and unique email validation.",
)
async def register(
    payload: UserRegister,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    auth_service = AuthService(db)
    return await auth_service.register(payload)


@router.post(
    "/login",
    response_model=Token,
    summary="Authenticate user",
    description="Verifies user credentials and returns JWT access and refresh tokens.",
)
async def login(
    payload: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> Token:
    auth_service = AuthService(db)
    return await auth_service.authenticate(payload.email, payload.password)


@router.post(
    "/refresh",
    response_model=Token,
    summary="Refresh access token",
    description="Rotates refresh tokens and provides a newly minted access token pair.",
)
async def refresh_token(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> Token:
    auth_service = AuthService(db)
    return await auth_service.refresh_tokens(payload.refresh_token)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Log out user",
    description="Revokes the provided refresh token to invalidate the user session.",
)
async def logout(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    auth_service = AuthService(db)
    await auth_service.logout(payload.refresh_token)
    return MessageResponse(message="Successfully logged out")


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get authenticated user info",
    description="Returns current authenticated user identity using the JWT access token.",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse.model_validate(current_user)

