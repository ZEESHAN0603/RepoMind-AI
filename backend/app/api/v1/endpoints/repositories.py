import json
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.core.config import settings
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.db.session import get_db
from app.models.repository import Repository
from app.models.user import User
from app.repositories.file_repository import FileRepository
from app.repositories.ingestion_job_repository import IngestionJobRepository
from app.repositories.repository_repository import RepositoryRepository
from app.schemas.repository import (
    IngestionJobResponse,
    RepositoryBranchResponse,
    RepositoryCreate,
    RepositoryFileNode,
    RepositoryLanguageResponse,
    RepositoryManifestResponse,
    RepositoryOverviewResponse,
    RepositoryResponse,
    RepositoryUpdate,
)
from app.schemas.token import MessageResponse
from app.services.discovery_service import DiscoveryService
from app.services.github_service import GitHubService
from app.services.ingestion_service import IngestionService
from app.services.workspace_service import WorkspaceService
from app.services.zip_service import ZipService

router = APIRouter()
workspace_service = WorkspaceService()
ingestion_service = IngestionService(workspace_service)


@router.get(
    "",
    response_model=List[RepositoryResponse],
    summary="List repositories",
    description="Retrieves all repositories owned by the currently authenticated user.",
)
async def list_repositories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[RepositoryResponse]:
    repo_repository = RepositoryRepository(db)
    repos = await repo_repository.list_by_owner(current_user.id)
    return [RepositoryResponse.model_validate(r) for r in repos]


@router.post(
    "",
    response_model=RepositoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Connect repository",
    description="Connects and triggers background ingestion for a public or private GitHub repository.",
)
async def create_repository(
    payload: RepositoryCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepositoryResponse:
    repo_repository = RepositoryRepository(db)

    # Validate URL and extract owner & name
    owner, repo_name = GitHubService.parse_github_url(payload.repository_url)
    owner = payload.owner or owner
    repo_name = payload.name or repo_name
    canonical_url = f"https://github.com/{owner}/{repo_name}"

    # Check for duplicate registration for this user
    existing = await repo_repository.get_by_owner_and_url(current_user.id, canonical_url)
    if existing:
        raise ConflictException(f"Repository '{owner}/{repo_name}' is already connected.")

    # Determine branch and visibility
    branch = payload.branch or payload.default_branch or "main"
    source_type = payload.source_type or "github_public"
    visibility = "private" if (payload.is_private or source_type == "github_private") else "public"

    new_repo = Repository(
        owner_id=current_user.id,
        name=repo_name,
        owner=owner,
        repository_url=canonical_url,
        source_type=source_type,
        default_branch=branch,
        visibility=visibility,
        status="connected",
        description=payload.description,
    )
    saved_repo = await repo_repository.create(new_repo)

    # Create ingestion job
    job = await ingestion_service.create_job(db, saved_repo.id, "Queued for GitHub acquisition")
    await db.commit()

    # Launch background ingestion pipeline
    background_tasks.add_task(
        ingestion_service.run_pipeline,
        repository_id=saved_repo.id,
        job_id=job.id,
        user_id=current_user.id,
    )

    return RepositoryResponse.model_validate(saved_repo)


@router.post(
    "/upload",
    response_model=RepositoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload repository ZIP archive",
    description="Uploads a ZIP archive, validates its structure, and starts background ingestion.",
)
async def upload_repository_zip(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepositoryResponse:
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise BadRequestException("Uploaded file must be a .zip archive.")

    # Stream file into temporary storage while checking size limit
    temp_dir = workspace_service.create_temp_dir("upload_")
    safe_filename = f"upload_{uuid.uuid4().hex}.zip"
    temp_file_path = temp_dir / safe_filename

    total_bytes = 0
    max_bytes = settings.MAX_UPLOAD_SIZE_BYTES

    try:
        with open(temp_file_path, "wb") as out_file:
            while chunk := await file.read(65536):
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise BadRequestException(
                        f"Uploaded ZIP exceeds maximum limit of {max_bytes // (1024 * 1024)} MB."
                    )
                out_file.write(chunk)
    except Exception as e:
        workspace_service.cleanup_temp_dir(temp_dir)
        if isinstance(e, BadRequestException):
            raise
        raise BadRequestException(f"Failed to receive uploaded file: {e}")

    # Validate ZIP header magic bytes
    try:
        with open(temp_file_path, "rb") as f:
            header = f.read(4)
            ZipService.validate_zip_header(header)
    except Exception as e:
        workspace_service.cleanup_temp_dir(temp_dir)
        raise BadRequestException(f"Invalid ZIP archive: {e}")

    # Derive repository name
    repo_name = name or Path(file.filename).stem or f"archive_{uuid.uuid4().hex[:8]}"

    repo_repository = RepositoryRepository(db)
    new_repo = Repository(
        owner_id=current_user.id,
        name=repo_name,
        owner=current_user.full_name or "local",
        repository_url=f"local://zip/{file.filename}",
        source_type="zip_upload",
        default_branch="main",
        visibility="private",
        status="pending",
        description=description or f"Uploaded archive {file.filename}",
    )
    saved_repo = await repo_repository.create(new_repo)

    job = await ingestion_service.create_job(db, saved_repo.id, "Queued for archive extraction")
    await db.commit()

    # Launch background ingestion pipeline
    background_tasks.add_task(
        ingestion_service.run_pipeline,
        repository_id=saved_repo.id,
        job_id=job.id,
        user_id=current_user.id,
        zip_file_path=temp_file_path,
    )

    return RepositoryResponse.model_validate(saved_repo)


@router.get(
    "/{repository_id}",
    response_model=RepositoryResponse,
    summary="Get repository details",
    description="Retrieves details of a specific repository owned by the user.",
)
async def get_repository(
    repository_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepositoryResponse:
    repo_repository = RepositoryRepository(db)
    repo = await repo_repository.get_by_id(repository_id)
    if not repo:
        raise NotFoundException("Repository not found")
    if repo.owner_id != current_user.id:
        raise ForbiddenException("You do not have access to this repository")
    return RepositoryResponse.model_validate(repo)


@router.patch(
    "/{repository_id}",
    response_model=RepositoryResponse,
    summary="Update repository",
    description="Updates repository branch, name, description, or archived status.",
)
async def update_repository(
    repository_id: str,
    payload: RepositoryUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepositoryResponse:
    repo_repository = RepositoryRepository(db)
    repo = await repo_repository.get_by_id(repository_id)
    if not repo:
        raise NotFoundException("Repository not found")
    if repo.owner_id != current_user.id:
        raise ForbiddenException("You do not have access to this repository")

    if payload.name is not None:
        repo.name = payload.name
    if payload.default_branch is not None:
        repo.default_branch = payload.default_branch
    if payload.description is not None:
        repo.description = payload.description
    if payload.is_archived is not None:
        repo.is_archived = payload.is_archived

    updated = await repo_repository.update(repo)
    return RepositoryResponse.model_validate(updated)


@router.delete(
    "/{repository_id}",
    response_model=MessageResponse,
    summary="Delete repository",
    description="Removes a connected repository from the platform and cleans up disk workspace.",
)
async def delete_repository(
    repository_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    repo_repository = RepositoryRepository(db)
    repo = await repo_repository.get_by_id(repository_id)
    if not repo:
        raise NotFoundException("Repository not found")
    if repo.owner_id != current_user.id:
        raise ForbiddenException("You do not have access to this repository")

    # Delete database records (cascades to files, jobs, branches, languages, manifests)
    await repo_repository.delete(repo)

    # Safely clean up workspace files on disk
    workspace_service.delete_repository_workspace(current_user.id, repository_id)

    return MessageResponse(message="Repository successfully deleted")


@router.post(
    "/{repository_id}/sync",
    response_model=IngestionJobResponse,
    summary="Trigger repository re-ingestion",
    description="Queues and starts a re-ingestion job for an existing repository.",
)
async def sync_repository(
    repository_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IngestionJobResponse:
    repo_repository = RepositoryRepository(db)
    repo = await repo_repository.get_by_id(repository_id)
    if not repo:
        raise NotFoundException("Repository not found")
    if repo.owner_id != current_user.id:
        raise ForbiddenException("You do not have access to this repository")

    if repo.source_type == "zip_upload":
        raise BadRequestException("ZIP-uploaded repositories cannot be re-synced from remote. Please upload a new archive.")

    job = await ingestion_service.create_job(db, repo.id, "Re-sync requested")
    await db.commit()

    background_tasks.add_task(
        ingestion_service.run_pipeline,
        repository_id=repo.id,
        job_id=job.id,
        user_id=current_user.id,
    )

    return IngestionJobResponse.model_validate(job)


@router.get(
    "/{repository_id}/jobs",
    response_model=List[IngestionJobResponse],
    summary="List ingestion jobs",
    description="Retrieves the ingestion job history and current progress for a repository.",
)
async def list_repository_jobs(
    repository_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[IngestionJobResponse]:
    repo_repository = RepositoryRepository(db)
    repo = await repo_repository.get_by_id(repository_id)
    if not repo:
        raise NotFoundException("Repository not found")
    if repo.owner_id != current_user.id:
        raise ForbiddenException("You do not have access to this repository")

    job_repo = IngestionJobRepository(db)
    jobs = await job_repo.list_for_repository(repository_id)
    return [IngestionJobResponse.model_validate(j) for j in jobs]


@router.get(
    "/{repository_id}/jobs/{job_id}",
    response_model=IngestionJobResponse,
    summary="Get ingestion job status",
    description="Returns the progress and status of a specific ingestion job.",
)
async def get_ingestion_job(
    repository_id: str,
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IngestionJobResponse:
    repo_repository = RepositoryRepository(db)
    repo = await repo_repository.get_by_id(repository_id)
    if not repo:
        raise NotFoundException("Repository not found")
    if repo.owner_id != current_user.id:
        raise ForbiddenException("You do not have access to this repository")

    job_repo = IngestionJobRepository(db)
    job = await job_repo.get_by_id(job_id)
    if not job or job.repository_id != repository_id:
        raise NotFoundException("Ingestion job not found")

    return IngestionJobResponse.model_validate(job)


@router.get(
    "/{repository_id}/branches",
    response_model=List[RepositoryBranchResponse],
    summary="List repository branches",
    description="Returns branches discovered for the repository.",
)
async def list_repository_branches(
    repository_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[RepositoryBranchResponse]:
    repo_repository = RepositoryRepository(db)
    repo = await repo_repository.get_by_id(repository_id)
    if not repo:
        raise NotFoundException("Repository not found")
    if repo.owner_id != current_user.id:
        raise ForbiddenException("You do not have access to this repository")

    file_repo = FileRepository(db)
    branches = await file_repo.list_branches_by_repo(repository_id)
    return [RepositoryBranchResponse.model_validate(b) for b in branches]


@router.get(
    "/{repository_id}/files",
    response_model=List[RepositoryFileNode],
    summary="Get repository file tree",
    description="Returns hierarchical file tree representing the discovered repository codebase.",
)
async def get_repository_file_tree(
    repository_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[RepositoryFileNode]:
    repo_repository = RepositoryRepository(db)
    repo = await repo_repository.get_by_id(repository_id)
    if not repo:
        raise NotFoundException("Repository not found")
    if repo.owner_id != current_user.id:
        raise ForbiddenException("You do not have access to this repository")

    file_repo = FileRepository(db)
    files = await file_repo.list_files_by_repo(repository_id)
    tree = DiscoveryService.build_tree_from_files(files)
    return tree


@router.get(
    "/{repository_id}/overview",
    response_model=RepositoryOverviewResponse,
    summary="Get repository overview",
    description="Returns aggregate repository statistics including languages, manifests, and branches.",
)
async def get_repository_overview(
    repository_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepositoryOverviewResponse:
    repo_repository = RepositoryRepository(db)
    repo = await repo_repository.get_by_id(repository_id)
    if not repo:
        raise NotFoundException("Repository not found")
    if repo.owner_id != current_user.id:
        raise ForbiddenException("You do not have access to this repository")

    file_repo = FileRepository(db)
    job_repo = IngestionJobRepository(db)

    branches = await file_repo.list_branches_by_repo(repository_id)
    languages = await file_repo.list_languages_by_repo(repository_id)
    manifests = await file_repo.list_manifests_by_repo(repository_id)
    latest_job = await job_repo.get_latest_for_repository(repository_id)

    manifest_responses = []
    for m in manifests:
        try:
            fw_list = json.loads(m.detected_frameworks)
        except Exception:
            fw_list = []
        manifest_responses.append(
            RepositoryManifestResponse(
                id=m.id,
                file_path=m.file_path,
                ecosystem=m.ecosystem,
                manifest_type=m.manifest_type,
                detected_frameworks=fw_list,
            )
        )

    return RepositoryOverviewResponse(
        repository=RepositoryResponse.model_validate(repo),
        available_branches=[RepositoryBranchResponse.model_validate(b) for b in branches],
        languages=[RepositoryLanguageResponse.model_validate(l) for l in languages],
        manifests=manifest_responses,
        latest_job=IngestionJobResponse.model_validate(latest_job) if latest_job else None,
        file_count=repo.file_count,
        folder_count=repo.folder_count,
        size_bytes=repo.size_bytes,
    )
