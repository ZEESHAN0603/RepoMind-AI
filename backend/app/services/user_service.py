from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserResponse, UserUpdate


class UserService:
    """Service handling user profile retrieval, updates, and account deletion."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)

    async def get_user_profile(self, user_id: str) -> UserResponse:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundException("User not found")
        return UserResponse.model_validate(user)

    async def update_profile(self, user: User, payload: UserUpdate) -> UserResponse:
        if payload.email is not None:
            new_email = payload.email.strip().lower()
            if new_email != user.email:
                existing = await self.user_repo.get_by_email(new_email)
                if existing:
                    raise ConflictException("Email is already taken by another account")
                user.email = new_email

        if payload.full_name is not None:
            user.full_name = payload.full_name.strip()

        updated_user = await self.user_repo.update(user)
        return UserResponse.model_validate(updated_user)

    async def delete_account(self, user: User) -> None:
        await self.user_repo.delete(user)

