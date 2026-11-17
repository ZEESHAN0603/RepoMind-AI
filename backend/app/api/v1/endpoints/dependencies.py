from typing import List, Literal, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.core.exceptions import ForbiddenException, NotFoundException
from app.db.session import get_db
from app.models.user import User
from app.repositories.repository_repository import RepositoryRepository
from app.schemas.dependency import (
    CircularDependencyCycle,
    DependencyAnalysisData,
    DirectDependenciesResponse,
    ExternalPackagesResponse,
    TransitiveDependenciesResponse,
    UnresolvedDependenciesResponse,
)
from app.services.dependency_service import DependencyService

router = APIRouter()
dependency_service = DependencyService()


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
    "/{repository_id}/dependencies/graph",
    response_model=DependencyAnalysisData,
    status_code=status.HTTP_200_OK,
    summary="Get repository dependency graph",
    description="Returns interactive multi-module dependency graph, nodes, edges, cycles, and metrics.",
)
async def get_dependency_graph(
    repository_id: str,
    force_refresh: bool = Query(False, description="Force re-synthesis of dependency graph"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DependencyAnalysisData:
    await _verify_repo_access(repository_id, current_user.id, db)
    return await dependency_service.get_or_build_graph(
        session=db,
        repository_id=repository_id,
        force_refresh=force_refresh,
    )


@router.post(
    "/{repository_id}/dependencies/analyze",
    response_model=DependencyAnalysisData,
    status_code=status.HTTP_200_OK,
    summary="Trigger dependency analysis",
    description="Forces a complete dependency re-analysis across all repository files.",
)
async def analyze_dependencies(
    repository_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DependencyAnalysisData:
    await _verify_repo_access(repository_id, current_user.id, db)
    return await dependency_service.get_or_build_graph(
        session=db,
        repository_id=repository_id,
        force_refresh=True,
    )


@router.get(
    "/{repository_id}/dependencies/cycles",
    response_model=List[CircularDependencyCycle],
    status_code=status.HTTP_200_OK,
    summary="Get circular dependencies",
    description="Returns detected circular dependency cycles, severity ratings, and refactoring recommendations.",
)
async def get_dependency_cycles(
    repository_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[CircularDependencyCycle]:
    await _verify_repo_access(repository_id, current_user.id, db)
    return await dependency_service.get_cycles(session=db, repository_id=repository_id)


@router.get(
    "/{repository_id}/dependencies/direct",
    response_model=DirectDependenciesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get direct dependencies or dependents for a file",
    description="Returns 1-hop upstream or downstream dependencies for a given repository file path.",
)
async def get_direct_dependencies(
    repository_id: str,
    file_path: str = Query(..., description="Target file relative path in repository"),
    direction: Literal["upstream", "downstream", "both"] = Query("both", description="Dependency query direction"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DirectDependenciesResponse:
    await _verify_repo_access(repository_id, current_user.id, db)
    return await dependency_service.get_direct_dependencies(
        session=db,
        repository_id=repository_id,
        file_path=file_path,
        direction=direction,
    )


@router.get(
    "/{repository_id}/dependencies/transitive",
    response_model=TransitiveDependenciesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get transitive dependency chain",
    description="Traverses BFS paths from a source file to discover transitive dependency chains.",
)
async def get_transitive_dependencies(
    repository_id: str,
    file_path: str = Query(..., description="Target file relative path in repository"),
    max_depth: int = Query(5, ge=1, le=20, description="Maximum BFS traversal depth"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransitiveDependenciesResponse:
    await _verify_repo_access(repository_id, current_user.id, db)
    return await dependency_service.get_transitive_dependencies(
        session=db,
        repository_id=repository_id,
        file_path=file_path,
        max_depth=max_depth,
    )


@router.get(
    "/{repository_id}/dependencies/unresolved",
    response_model=UnresolvedDependenciesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get unresolved dependencies",
    description="Returns imports that could not be resolved to internal repository files or external packages.",
)
async def get_unresolved_dependencies(
    repository_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnresolvedDependenciesResponse:
    await _verify_repo_access(repository_id, current_user.id, db)
    return await dependency_service.get_unresolved_dependencies(session=db, repository_id=repository_id)


@router.get(
    "/{repository_id}/dependencies/packages",
    response_model=ExternalPackagesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get external package dependencies",
    description="Lists all third-party package dependencies and the internal files importing them.",
)
async def get_external_packages(
    repository_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExternalPackagesResponse:
    await _verify_repo_access(repository_id, current_user.id, db)
    return await dependency_service.get_external_packages(session=db, repository_id=repository_id)
