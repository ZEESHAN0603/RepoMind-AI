from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.github_connection import GitHubConnection


class GitHubConnectionRepository:
    """Data access repository for user GitHub OAuth connections."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_user_id(self, user_id: str) -> Optional[GitHubConnection]:
        query = select(GitHubConnection).where(GitHubConnection.user_id == user_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def upsert(
        self,
        user_id: str,
        github_user_id: Optional[str],
        github_username: Optional[str],
        encrypted_token: Optional[str],
        scope: Optional[str],
    ) -> GitHubConnection:
        existing = await self.get_by_user_id(user_id)
        if existing:
            existing.github_user_id = github_user_id
            existing.github_username = github_username
            existing.encrypted_access_token = encrypted_token
            existing.scope = scope
            await self.session.flush()
            await self.session.refresh(existing)
            return existing

        new_conn = GitHubConnection(
            user_id=user_id,
            github_user_id=github_user_id,
            github_username=github_username,
            encrypted_access_token=encrypted_token,
            scope=scope,
        )
        self.session.add(new_conn)
        await self.session.flush()
        await self.session.refresh(new_conn)
        return new_conn

    async def delete_by_user_id(self, user_id: str) -> bool:
        existing = await self.get_by_user_id(user_id)
        if existing:
            await self.session.delete(existing)
            await self.session.flush()
            return True
        return False

