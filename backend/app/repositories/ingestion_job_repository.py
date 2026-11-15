from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingestion_job import RepositoryIngestionJob


class IngestionJobRepository:
    """Data access repository for Ingestion Job entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, job: RepositoryIngestionJob) -> RepositoryIngestionJob:
        self.session.add(job)
        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def get_by_id(self, job_id: str) -> Optional[RepositoryIngestionJob]:
        query = select(RepositoryIngestionJob).where(RepositoryIngestionJob.id == job_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_latest_for_repository(self, repo_id: str) -> Optional[RepositoryIngestionJob]:
        query = (
            select(RepositoryIngestionJob)
            .where(RepositoryIngestionJob.repository_id == repo_id)
            .order_by(RepositoryIngestionJob.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_for_repository(self, repo_id: str) -> List[RepositoryIngestionJob]:
        query = (
            select(RepositoryIngestionJob)
            .where(RepositoryIngestionJob.repository_id == repo_id)
            .order_by(RepositoryIngestionJob.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_progress(
        self,
        job: RepositoryIngestionJob,
        status: str,
        stage: str,
        percent: int,
        error_message: Optional[str] = None,
    ) -> RepositoryIngestionJob:
        job.status = status
        job.current_stage = stage
        job.progress_percent = percent
        if error_message is not None:
            job.error_message = error_message
        if status in ("completed", "failed") and not job.completed_at:
            job.completed_at = datetime.now(timezone.utc)
        if status not in ("queued",) and not job.started_at:
            job.started_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(job)
        return job

