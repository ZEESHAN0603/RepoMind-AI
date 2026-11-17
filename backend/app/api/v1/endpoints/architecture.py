from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.core.exceptions import ForbiddenException, NotFoundException
from app.db.session import get_db
from app.models.user import User
from app.repositories.repository_repository import RepositoryRepository
from app.schemas.architecture import (
    ArchitectureGraphResponse,
    ArchitectureNodeDetailResponse,
    ArchitectureViewPayloadSchema,
)
from app.services.architecture_service import ArchitectureService

router = APIRouter()
architecture_service = ArchitectureService()


async def _verify_repo_access(
    repository_id: str,
    user_id: str,
    db: AsyncSession,
):
    repo_repo = RepositoryRepository(db)
    repo = await repo_repo.get_by_id(repository_id)
    if not repo:
        raise NotFoundException("Repository not found")
    if repo.owner_id != user_id:
        raise ForbiddenException("You do not have access to this repository")
    return repo


@router.get(
    "/{repository_id}/architecture/graph",
    response_model=ArchitectureGraphResponse,
    status_code=status.HTTP_200_OK,
    summary="Get multi-view architecture graph",
    description="Returns the full interactive architecture graph and all 6 canonical view mode slices for a repository.",
)
async def get_architecture_graph(
    repository_id: str,
    force_refresh: bool = Query(False, description="Force re-synthesis of architecture graph from source intelligence"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArchitectureGraphResponse:
    await _verify_repo_access(repository_id, current_user.id, db)
    graph_data = await architecture_service.get_or_build_graph(
        session=db,
        repository_id=repository_id,
        force_refresh=force_refresh,
    )
    return ArchitectureGraphResponse.model_validate(graph_data)


@router.get(
    "/{repository_id}/architecture/views/{view_mode}",
    response_model=ArchitectureViewPayloadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get specific architecture view slice",
    description="Returns a filtered view mode slice (system, frontend, backend, api, database, modules).",
)
async def get_architecture_view(
    repository_id: str,
    view_mode: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArchitectureViewPayloadSchema:
    await _verify_repo_access(repository_id, current_user.id, db)
    view_data = await architecture_service.get_view(
        session=db,
        repository_id=repository_id,
        view_mode=view_mode,
    )
    return ArchitectureViewPayloadSchema.model_validate(view_data)


@router.get(
    "/{repository_id}/architecture/nodes/{node_id:path}",
    response_model=ArchitectureNodeDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get architecture node details",
    description="Returns comprehensive metadata, incoming relationships, and outgoing relationships for a specific architecture node.",
)
async def get_architecture_node_detail(
    repository_id: str,
    node_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArchitectureNodeDetailResponse:
    await _verify_repo_access(repository_id, current_user.id, db)
    detail_data = await architecture_service.get_node_details(
        session=db,
        repository_id=repository_id,
        node_id=node_id,
    )
    return ArchitectureNodeDetailResponse.model_validate(detail_data)
