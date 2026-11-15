from typing import List
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.repository_branch import RepositoryBranch
from app.models.repository_file import RepositoryFile
from app.models.repository_language import RepositoryLanguage
from app.models.repository_manifest import RepositoryDependencyManifest


class FileRepository:
    """Data access repository for repository files, branches, languages, and manifests."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # File operations
    async def save_files_batch(self, files: List[RepositoryFile]) -> None:
        self.session.add_all(files)
        await self.session.flush()

    async def delete_files_by_repo(self, repo_id: str) -> None:
        await self.session.execute(
            delete(RepositoryFile).where(RepositoryFile.repository_id == repo_id)
        )
        await self.session.flush()

    async def list_files_by_repo(self, repo_id: str) -> List[RepositoryFile]:
        query = (
            select(RepositoryFile)
            .where(RepositoryFile.repository_id == repo_id)
            .order_by(RepositoryFile.path.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    # Branch operations
    async def replace_branches(self, repo_id: str, branches: List[RepositoryBranch]) -> None:
        await self.session.execute(
            delete(RepositoryBranch).where(RepositoryBranch.repository_id == repo_id)
        )
        self.session.add_all(branches)
        await self.session.flush()

    async def list_branches_by_repo(self, repo_id: str) -> List[RepositoryBranch]:
        query = (
            select(RepositoryBranch)
            .where(RepositoryBranch.repository_id == repo_id)
            .order_by(RepositoryBranch.name.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    # Language operations
    async def replace_languages(self, repo_id: str, languages: List[RepositoryLanguage]) -> None:
        await self.session.execute(
            delete(RepositoryLanguage).where(RepositoryLanguage.repository_id == repo_id)
        )
        self.session.add_all(languages)
        await self.session.flush()

    async def list_languages_by_repo(self, repo_id: str) -> List[RepositoryLanguage]:
        query = (
            select(RepositoryLanguage)
            .where(RepositoryLanguage.repository_id == repo_id)
            .order_by(RepositoryLanguage.percentage.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    # Manifest operations
    async def replace_manifests(self, repo_id: str, manifests: List[RepositoryDependencyManifest]) -> None:
        await self.session.execute(
            delete(RepositoryDependencyManifest).where(RepositoryDependencyManifest.repository_id == repo_id)
        )
        self.session.add_all(manifests)
        await self.session.flush()

    async def list_manifests_by_repo(self, repo_id: str) -> List[RepositoryDependencyManifest]:
        query = (
            select(RepositoryDependencyManifest)
            .where(RepositoryDependencyManifest.repository_id == repo_id)
            .order_by(RepositoryDependencyManifest.file_path.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

