from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.token import RefreshToken


class TokenRepository:
    """Data access repository for refresh tokens."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, user_id: str, token_str: str, expires_at: datetime) -> RefreshToken:
        refresh_token = RefreshToken(
            user_id=user_id,
            token=token_str,
            expires_at=expires_at,
            is_revoked=False,
        )
        self.session.add(refresh_token)
        await self.session.flush()
        return refresh_token

    async def get_by_token(self, token_str: str) -> Optional[RefreshToken]:
        query = select(RefreshToken).where(RefreshToken.token == token_str)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def revoke(self, token_str: str) -> bool:
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.token == token_str)
            .values(is_revoked=True)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0

    async def revoke_all_for_user(self, user_id: str) -> None:
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .values(is_revoked=True)
        )
        await self.session.execute(stmt)
        await self.session.flush()

