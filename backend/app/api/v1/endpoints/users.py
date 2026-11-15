from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.token import MessageResponse
from app.schemas.user import UserResponse, UserUpdate
from app.services.user_service import UserService

router = APIRouter()


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get user profile",
    description="Retrieves the profile of the currently authenticated user.",
)
async def get_user_profile(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update user profile",
    description="Updates allowed profile fields (name, email) for the current user.",
)
async def update_user_profile(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    user_service = UserService(db)
    return await user_service.update_profile(current_user, payload)


@router.delete(
    "/me",
    response_model=MessageResponse,
    summary="Delete user account",
    description="Permanently deletes the current user account and cascades owned entities.",
)
async def delete_user_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    user_service = UserService(db)
    await user_service.delete_account(current_user)
    return MessageResponse(message="Account successfully deleted")

