from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.repository import Repository


class RepositoryRepository:
    """Data access repository for Repository entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, repo_id: str) -> Optional[Repository]:
        query = select(Repository).where(Repository.id == repo_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_by_owner(self, owner_id: str) -> List[Repository]:
        query = select(Repository).where(Repository.owner_id == owner_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create(self, repo: Repository) -> Repository:
        self.session.add(repo)
        await self.session.flush()
        await self.session.refresh(repo)
        return repo

    async def delete(self, repo: Repository) -> None:
        await self.session.delete(repo)
        await self.session.flush()

