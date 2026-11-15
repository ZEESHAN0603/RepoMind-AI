from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.core.exceptions import ForbiddenException, NotFoundException
from app.db.session import get_db
from app.models.user import User
from app.repositories.code_intelligence_repository import CodeIntelligenceRepository
from app.repositories.file_repository import FileRepository
from app.repositories.repository_repository import RepositoryRepository
from app.schemas.code_intelligence import (
    AnalysisSummaryResponse,
    ApiRouteEndpointResponse,
    CodeSymbolResponse,
    RepositoryAnalysisOverviewResponse,
    SymbolsListResponse,
)
from app.services.static_analysis_service import StaticAnalysisService

router = APIRouter()
static_analysis_service = StaticAnalysisService()


async def _verify_repo_ownership(
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


@router.post(
    "/{repository_id}/analyze",
    response_model=AnalysisSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger repository static analysis",
    description="Parses source files in the repository workspace and extracts code symbols, imports/exports, and API routes.",
)
async def analyze_repository(
    repository_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisSummaryResponse:
    await _verify_repo_ownership(repository_id, current_user.id, db)
    summary = await static_analysis_service.analyze_repository(
        session=db,
        repository_id=repository_id,
        user_id=current_user.id,
    )
    return AnalysisSummaryResponse.model_validate(summary)


@router.get(
    "/{repository_id}/analysis",
    response_model=RepositoryAnalysisOverviewResponse,
    summary="Get static analysis overview",
    description="Returns aggregate counts of extracted code symbols, endpoints, and imports for a repository.",
)
async def get_repository_analysis(
    repository_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RepositoryAnalysisOverviewResponse:
    repo = await _verify_repo_ownership(repository_id, current_user.id, db)
    ci_repo = CodeIntelligenceRepository(db)
    stats = await ci_repo.get_analysis_stats(repository_id)

    return RepositoryAnalysisOverviewResponse(
        repository_id=repository_id,
        total_symbols=stats["total_symbols"],
        symbols_by_type=stats["symbols_by_type"],
        total_endpoints=stats["total_endpoints"],
        endpoints_by_framework=stats["endpoints_by_framework"],
        total_imports_exports=stats["total_imports_exports"],
        last_analyzed_at=repo.last_analyzed_at,
    )


@router.get(
    "/{repository_id}/symbols",
    response_model=SymbolsListResponse,
    summary="List extracted symbols",
    description="Retrieves a paginated list of extracted code symbols with optional filtering by type, file, or search query.",
)
async def list_repository_symbols(
    repository_id: str,
    symbol_type: Optional[str] = Query(None, description="Filter by symbol type (function, method, class, interface, etc.)"),
    file_id: Optional[str] = Query(None, description="Filter by file ID"),
    search: Optional[str] = Query(None, description="Search symbol name"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SymbolsListResponse:
    await _verify_repo_ownership(repository_id, current_user.id, db)
    ci_repo = CodeIntelligenceRepository(db)
    symbols, total = await ci_repo.list_symbols_by_repo(
        repo_id=repository_id,
        symbol_type=symbol_type,
        file_id=file_id,
        search=search,
        offset=offset,
        limit=limit,
    )

    return SymbolsListResponse(
        items=[CodeSymbolResponse.model_validate(s) for s in symbols],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/{repository_id}/symbols/{symbol_id}",
    response_model=CodeSymbolResponse,
    summary="Get symbol details",
    description="Returns detailed metadata, signature, parameters, and location for a specific symbol.",
)
async def get_symbol_details(
    repository_id: str,
    symbol_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CodeSymbolResponse:
    await _verify_repo_ownership(repository_id, current_user.id, db)
    ci_repo = CodeIntelligenceRepository(db)
    symbol = await ci_repo.get_symbol_by_id(symbol_id)
    if not symbol or symbol.repository_id != repository_id:
        raise NotFoundException("Symbol not found")

    return CodeSymbolResponse.model_validate(symbol)


@router.get(
    "/{repository_id}/files/{file_id}/symbols",
    response_model=List[CodeSymbolResponse],
    summary="Get symbols for file",
    description="Returns all extracted symbols within a specific repository file ordered by start line.",
)
async def get_file_symbols(
    repository_id: str,
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[CodeSymbolResponse]:
    await _verify_repo_ownership(repository_id, current_user.id, db)
    file_repo = FileRepository(db)
    # Validate file belongs to repo
    files = await file_repo.list_files_by_repo(repository_id)
    if not any(f.id == file_id for f in files):
        raise NotFoundException("File not found in this repository")

    ci_repo = CodeIntelligenceRepository(db)
    symbols = await ci_repo.list_symbols_by_file(file_id)
    return [CodeSymbolResponse.model_validate(s) for s in symbols]


@router.get(
    "/{repository_id}/endpoints",
    response_model=List[ApiRouteEndpointResponse],
    summary="List API route endpoints",
    description="Returns all discovered HTTP API endpoints for a repository with optional method and framework filters.",
)
async def list_repository_endpoints(
    repository_id: str,
    framework: Optional[str] = Query(None, description="Filter by framework (FastAPI, Flask, Express, Spring Boot)"),
    http_method: Optional[str] = Query(None, description="Filter by HTTP method (GET, POST, etc.)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ApiRouteEndpointResponse]:
    await _verify_repo_ownership(repository_id, current_user.id, db)
    ci_repo = CodeIntelligenceRepository(db)
    endpoints = await ci_repo.list_endpoints_by_repo(
        repo_id=repository_id,
        framework=framework,
        http_method=http_method,
    )
    return [ApiRouteEndpointResponse.model_validate(ep) for ep in endpoints]

