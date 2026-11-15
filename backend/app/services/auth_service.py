from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    UnauthorizedException,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.token_repository import TokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.token import Token
from app.schemas.user import UserRegister, UserResponse


class AuthService:
    """Service orchestrating user registration, authentication, and session tokens."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.token_repo = TokenRepository(session)

    async def register(self, payload: UserRegister) -> UserResponse:
        # Normalize email
        normalized_email = payload.email.strip().lower()

        # Check existing user
        existing_user = await self.user_repo.get_by_email(normalized_email)
        if existing_user:
            raise ConflictException("A user with this email address already exists")

        # Validate password strength (at least 8 chars, checked by pydantic; basic rule)
        if len(payload.password.strip()) < 8:
            raise BadRequestException("Password must be at least 8 characters long")

        # Hash password using Argon2
        hashed_pwd = hash_password(payload.password)

        new_user = User(
            full_name=payload.full_name.strip(),
            email=normalized_email,
            password_hash=hashed_pwd,
            is_active=True,
            is_verified=False,
        )
        created_user = await self.user_repo.create(new_user)
        return UserResponse.model_validate(created_user)

    async def authenticate(self, email: str, password: str) -> Token:
        normalized_email = email.strip().lower()
        user = await self.user_repo.get_by_email(normalized_email)

        if not user or not verify_password(password, user.password_hash):
            raise UnauthorizedException("Invalid email or password")

        if not user.is_active:
            raise UnauthorizedException("Account has been deactivated")

        # Issue tokens
        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)

        # Store refresh token with expiry for revocation tracking
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        await self.token_repo.create(
            user_id=user.id,
            token_str=refresh_token,
            expires_at=expires_at,
        )

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )

    async def refresh_tokens(self, refresh_token_str: str) -> Token:
        payload = decode_token(refresh_token_str)
        if payload.get("type") != "refresh":
            raise UnauthorizedException("Invalid token type for refresh")

        user_id = payload.get("sub")
        if not user_id:
            raise UnauthorizedException("Invalid token claims")

        # Check token record in database
        token_record = await self.token_repo.get_by_token(refresh_token_str)
        if not token_record or token_record.is_revoked:
            raise UnauthorizedException("Refresh token is invalid or has been revoked")

        # Check expiration
        now_utc = datetime.now(timezone.utc)
        record_exp = token_record.expires_at
        if record_exp.tzinfo is None:
            record_exp = record_exp.replace(tzinfo=timezone.utc)
        if record_exp < now_utc:
            raise UnauthorizedException("Refresh token has expired")

        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise UnauthorizedException("User not found or inactive")

        # Revoke old refresh token (Token Rotation)
        await self.token_repo.revoke(refresh_token_str)

        # Issue new pair
        new_access_token = create_access_token(user.id)
        new_refresh_token = create_refresh_token(user.id)
        new_expires_at = now_utc + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        await self.token_repo.create(
            user_id=user.id,
            token_str=new_refresh_token,
            expires_at=new_expires_at,
        )

        return Token(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
        )

    async def logout(self, refresh_token_str: str) -> None:
        await self.token_repo.revoke(refresh_token_str)

