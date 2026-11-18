import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_secret
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.logging import logger
from app.db.session import async_session_maker
from app.models.ingestion_job import RepositoryIngestionJob
from app.models.repository import Repository
from app.models.repository_branch import RepositoryBranch
from app.repositories.file_repository import FileRepository
from app.repositories.github_connection_repository import GitHubConnectionRepository
from app.repositories.ingestion_job_repository import IngestionJobRepository
from app.repositories.repository_repository import RepositoryRepository
from app.services.detection_service import TechnologyDetectionService
from app.services.discovery_service import DiscoveryService
from app.services.github_service import GitHubService
from app.services.static_analysis_service import StaticAnalysisService
from app.services.workspace_service import WorkspaceService
from app.services.zip_service import ZipService


class IngestionService:
    """Orchestrates background ingestion, extraction, indexing, and analysis for repositories."""

    def __init__(self, workspace_service: Optional[WorkspaceService] = None) -> None:
        self.workspace_service = workspace_service or WorkspaceService()

    async def create_job(
        self,
        session: AsyncSession,
        repository_id: str,
        initial_stage: str = "Queued",
    ) -> RepositoryIngestionJob:
        """Creates a new queued IngestionJob or returns active job if already running."""
        job_repo = IngestionJobRepository(session)
        latest = await job_repo.get_latest_for_repository(repository_id)

        # Prevent duplicate active concurrent jobs
        if latest and latest.status in ("queued", "cloning", "extracting", "discovering", "analyzing"):
            logger.info("Ingestion job already running for repo %s: job %s", repository_id, latest.id)
            return latest

        job = RepositoryIngestionJob(
            repository_id=repository_id,
            status="queued",
            progress_percent=5,
            current_stage=initial_stage,
            started_at=datetime.now(timezone.utc),
        )
        return await job_repo.create(job)

    async def run_pipeline(
        self,
        repository_id: str,
        job_id: str,
        user_id: str,
        zip_file_path: Optional[Path] = None,
    ) -> None:
        """
        Executes the ingestion pipeline in a background worker context.
        Manages its own scoped database session to ensure transaction isolation.
        """
        temp_dir: Optional[Path] = None

        async with async_session_maker() as session:
            job_repo = IngestionJobRepository(session)
            repo_repo = RepositoryRepository(session)
            file_repo = FileRepository(session)
            github_conn_repo = GitHubConnectionRepository(session)

            job = await job_repo.get_by_id(job_id)
            repo = await repo_repo.get_by_id(repository_id)

            if not job or not repo:
                logger.error("Ingestion failed: Job %s or Repo %s not found", job_id, repository_id)
                return

            try:
                # Stage 1: Preparation & Workspace allocation
                await job_repo.update_progress(job, "processing", "Preparing isolated workspace", 10)
                repo.status = "ingesting"
                await repo_repo.update(repo)
                await session.commit()

                workspace_dir = self.workspace_service.prepare_repository_workspace(
                    user_id=user_id,
                    repository_id=repository_id,
                    clean=True,
                )

                # Stage 2: Acquisition (GitHub download or ZIP extraction)
                if repo.source_type.startswith("github"):
                    await job_repo.update_progress(job, "cloning", "Fetching repository from GitHub", 25)
                    await session.commit()

                    owner, repo_name = GitHubService.parse_github_url(repo.repository_url)

                    # Check for authenticated GitHub token if private
                    access_token = None
                    gh_conn = await github_conn_repo.get_by_user_id(user_id)
                    if gh_conn and gh_conn.encrypted_access_token:
                        access_token = decrypt_secret(gh_conn.encrypted_access_token)

                    # Update metadata & branches
                    try:
                        meta = await GitHubService.get_repository_metadata(owner, repo_name, access_token)
                        repo.visibility = meta.get("visibility", repo.visibility)
                        repo.description = meta.get("description") or repo.description
                        if not repo.default_branch or repo.default_branch == "main":
                            repo.default_branch = meta.get("default_branch", "main")
                    except Exception as e:
                        logger.warning("Could not refresh GitHub metadata during ingestion: %s", e)

                    # Retrieve branches
                    branches_data = await GitHubService.get_repository_branches(owner, repo_name, access_token)
                    if branches_data:
                        branch_entities = [
                            RepositoryBranch(
                                repository_id=repo.id,
                                name=b["name"],
                                commit_sha=b.get("commit_sha"),
                                is_default=(b["name"] == repo.default_branch),
                            )
                            for b in branches_data
                        ]
                        await file_repo.replace_branches(repo.id, branch_entities)

                    # Fetch commit SHA for target branch
                    target_branch = repo.default_branch or "main"
                    commit_sha = await GitHubService.get_latest_commit_sha(owner, repo_name, target_branch, access_token)
                    if commit_sha:
                        repo.current_commit_sha = commit_sha

                    # Download archive streamingly
                    temp_dir = self.workspace_service.create_temp_dir("github_")
                    temp_zip = temp_dir / "repo.zip"

                    await GitHubService.download_archive(
                        owner=owner,
                        repo=repo_name,
                        branch=target_branch,
                        destination_zip_path=temp_zip,
                        access_token=access_token,
                    )

                    await job_repo.update_progress(job, "extracting", "Safely extracting repository archive", 40)
                    await session.commit()

                    ZipService.validate_and_extract(temp_zip, workspace_dir)

                elif repo.source_type == "zip_upload":
                    await job_repo.update_progress(job, "extracting", "Extracting uploaded ZIP archive", 30)
                    await session.commit()

                    if not zip_file_path or not zip_file_path.exists():
                        raise BadRequestException("Uploaded archive file is missing or expired")

                    ZipService.validate_and_extract(zip_file_path, workspace_dir)

                    # Record a default branch for ZIP uploads
                    await file_repo.replace_branches(
                        repo.id,
                        [RepositoryBranch(repository_id=repo.id, name="main", is_default=True)],
                    )

                # Stage 3: File Discovery & Tree indexing
                await job_repo.update_progress(job, "discovering", "Discovering files and structure", 60)
                await session.commit()

                files, file_count, folder_count, total_bytes = DiscoveryService.discover_repository(
                    workspace_dir=workspace_dir,
                    repository_id=repo.id,
                )

                # Persist discovered files in database
                await file_repo.delete_files_by_repo(repo.id)
                await file_repo.save_files_batch(files)

                # Create baseline workspace snapshot for version comparisons
                try:
                    self.workspace_service.create_snapshot(user_id=user_id, repository_id=repo.id, snapshot_id="baseline")
                    from app.repositories.update_repository import UpdateRepository
                    from app.models.repository_version import RepositoryVersion
                    up_repo = UpdateRepository(session)
                    existing_v = await up_repo.list_versions_by_repo(repo.id, limit=1)
                    if not existing_v:
                        base_version = RepositoryVersion(
                            repository_id=repo.id,
                            version_tag="v1.0.0",
                            commit_sha=repo.current_commit_sha,
                            source_type="github_commit" if repo.source_type.startswith("github") else "snapshot",
                        )
                        await up_repo.create_version(base_version)
                except Exception as snap_ex:
                    logger.warning("Could not create baseline workspace snapshot: %s", snap_ex)

                # Stage 4: Technology, Language & Framework Detection
                await job_repo.update_progress(job, "analyzing", "Detecting languages and frameworks", 80)
                await session.commit()

                languages = TechnologyDetectionService.calculate_language_distribution(files, repo.id)
                await file_repo.replace_languages(repo.id, languages)

                manifests = TechnologyDetectionService.detect_manifests(workspace_dir, repo.id)
                await file_repo.replace_manifests(repo.id, manifests)

                # Static code intelligence & symbol analysis
                try:
                    await job_repo.update_progress(job, "analyzing", "Extracting code symbols and static intelligence", 90)
                    await session.commit()
                    analysis_svc = StaticAnalysisService(self.workspace_service)
                    await analysis_svc.analyze_repository(session, repo.id, user_id)
                except Exception as analysis_err:
                    logger.warning("Static analysis encountered warning on repo %s: %s", repo.id, analysis_err)

                # Code chunking & vector embedding indexing (Phase 5)
                try:
                    await job_repo.update_progress(job, "analyzing", "Generating code embeddings and vector index", 95)
                    await session.commit()
                    from app.services.chunking_service import ChunkingService
                    from app.services.embedding_service import EmbeddingService
                    embed_svc = EmbeddingService(chunking_service=ChunkingService(self.workspace_service))
                    await embed_svc.index_repository_embeddings(session, repo.id, user_id)
                except Exception as embed_err:
                    logger.warning("Embedding generation encountered warning on repo %s: %s", repo.id, embed_err)

                # Stage 5: Finalization & Success
                repo.file_count = file_count
                repo.folder_count = folder_count
                repo.size_bytes = total_bytes
                repo.status = "completed"
                repo.last_analyzed_at = datetime.now(timezone.utc)
                await repo_repo.update(repo)

                await job_repo.update_progress(
                    job=job,
                    status="completed",
                    stage="Ingestion completed successfully",
                    percent=100,
                )
                await session.commit()
                logger.info("Successfully ingested repository: %s (files: %d, size: %d bytes)", repo.id, file_count, total_bytes)

            except Exception as exc:
                await session.rollback()
                error_msg = str(exc)
                logger.error("Ingestion failed for repo %s: %s", repository_id, error_msg, exc_info=True)

                # Re-fetch job and repo in fresh transaction to record failure
                try:
                    job.retry_count += 1
                    await job_repo.update_progress(
                        job=job,
                        status="failed",
                        stage="Ingestion failed",
                        percent=job.progress_percent,
                        error_message=error_msg,
                    )
                    repo.status = "failed"
                    await repo_repo.update(repo)
                    await session.commit()
                except Exception as inner_ex:
                    logger.error("Failed to persist job failure state: %s", inner_ex)

            finally:
                # Cleanup temporary directories and uploaded files
                if temp_dir:
                    self.workspace_service.cleanup_temp_dir(temp_dir)
                if zip_file_path and zip_file_path.exists():
                    try:
                        zip_file_path.unlink(missing_ok=True)
                    except Exception:
                        pass

