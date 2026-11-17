from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.repository_version import RepositoryVersion
from app.models.repository_update_run import RepositoryUpdateRun
from app.models.version_file_change import VersionFileChange
from app.models.version_symbol_change import VersionSymbolChange
from app.models.version_impact_record import VersionImpactRecord


class UpdateRepository:
    """Database repository for Phase 9 repository versions and update intelligence runs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # 1. Version Operations
    async def create_version(self, version: RepositoryVersion) -> RepositoryVersion:
        self.session.add(version)
        await self.session.flush()
        return version

    async def get_version_by_id(self, version_id: str) -> Optional[RepositoryVersion]:
        stmt = select(RepositoryVersion).where(RepositoryVersion.id == version_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_version_by_commit(self, repo_id: str, commit_sha: str) -> Optional[RepositoryVersion]:
        stmt = select(RepositoryVersion).where(
            RepositoryVersion.repository_id == repo_id,
            RepositoryVersion.commit_sha == commit_sha,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_versions_by_repo(self, repo_id: str, limit: int = 50) -> List[RepositoryVersion]:
        stmt = (
            select(RepositoryVersion)
            .where(RepositoryVersion.repository_id == repo_id)
            .order_by(desc(RepositoryVersion.created_at))
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # 2. Update Run Operations
    async def create_update_run(self, run: RepositoryUpdateRun) -> RepositoryUpdateRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def update_update_run(self, run: RepositoryUpdateRun) -> RepositoryUpdateRun:
        await self.session.flush()
        return run

    async def get_update_run_by_id(self, run_id: str) -> Optional[RepositoryUpdateRun]:
        stmt = (
            select(RepositoryUpdateRun)
            .where(RepositoryUpdateRun.id == run_id)
            .options(
                selectinload(RepositoryUpdateRun.base_version),
                selectinload(RepositoryUpdateRun.target_version),
                selectinload(RepositoryUpdateRun.file_changes),
                selectinload(RepositoryUpdateRun.symbol_changes),
                selectinload(RepositoryUpdateRun.impact_records),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_update_runs_by_repo(self, repo_id: str, limit: int = 50) -> List[RepositoryUpdateRun]:
        stmt = (
            select(RepositoryUpdateRun)
            .where(RepositoryUpdateRun.repository_id == repo_id)
            .options(
                selectinload(RepositoryUpdateRun.base_version),
                selectinload(RepositoryUpdateRun.target_version),
            )
            .order_by(desc(RepositoryUpdateRun.created_at))
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # 3. Batch Saving Diffs
    async def save_file_changes_batch(self, changes: List[VersionFileChange]) -> None:
        self.session.add_all(changes)
        await self.session.flush()

    async def save_symbol_changes_batch(self, changes: List[VersionSymbolChange]) -> None:
        self.session.add_all(changes)
        await self.session.flush()

    async def save_impact_records_batch(self, records: List[VersionImpactRecord]) -> None:
        self.session.add_all(records)
        await self.session.flush()

    async def list_file_changes_by_run(
        self, run_id: str, change_type: Optional[str] = None
    ) -> List[VersionFileChange]:
        stmt = select(VersionFileChange).where(VersionFileChange.update_run_id == run_id)
        if change_type:
            stmt = stmt.where(VersionFileChange.change_type == change_type)
        stmt = stmt.order_by(VersionFileChange.path)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def list_symbol_changes_by_run(
        self, run_id: str, symbol_type: Optional[str] = None
    ) -> List[VersionSymbolChange]:
        stmt = select(VersionSymbolChange).where(VersionSymbolChange.update_run_id == run_id)
        if symbol_type:
            stmt = stmt.where(VersionSymbolChange.symbol_type == symbol_type)
        stmt = stmt.order_by(VersionSymbolChange.symbol_name)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def list_impact_records_by_run(
        self, run_id: str, impact_level: Optional[str] = None
    ) -> List[VersionImpactRecord]:
        stmt = select(VersionImpactRecord).where(VersionImpactRecord.update_run_id == run_id)
        if impact_level:
            stmt = stmt.where(VersionImpactRecord.impact_level == impact_level)
        stmt = stmt.order_by(VersionImpactRecord.depth, VersionImpactRecord.affected_identifier)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
