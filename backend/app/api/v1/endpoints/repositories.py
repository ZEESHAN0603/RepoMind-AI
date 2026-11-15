from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.core.exceptions import ForbiddenException, NotFoundException
from app.db.session import get_db
from app.models.repository import Repository
from app.models.user import User
from app.repositories.repository_repository import RepositoryRepository
from app.schemas.repository import RepositoryCreate, RepositoryResponse
from app.schemas.token import MessageResponse

router = APIRouter()


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
    description="Connects a new repository to the platform for the authenticated user.",
)
async def create_repository(
    payload: RepositoryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepositoryResponse:
    repo_repository = RepositoryRepository(db)
    new_repo = Repository(
        owner_id=current_user.id,
        name=payload.name,
        owner=payload.owner,
        repository_url=payload.repository_url,
        source_type=payload.source_type,
        default_branch=payload.default_branch,
        visibility=payload.visibility,
        status="connected",
    )
    saved_repo = await repo_repository.create(new_repo)
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


@router.delete(
    "/{repository_id}",
    response_model=MessageResponse,
    summary="Delete repository",
    description="Removes a connected repository from the platform.",
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
    await repo_repository.delete(repo)
    return MessageResponse(message="Repository successfully deleted")

