import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.core.exceptions import ForbiddenException, NotFoundException
from app.db.session import get_db
from app.models.user import User
from app.repositories.repository_repository import RepositoryRepository
from app.repositories.update_repository import UpdateRepository
from app.schemas.update import (
    AdHocCompareRequest,
    AIExplainRequest,
    AIExplainResponse,
    FileChangeResponse,
    ImpactGraphResponse,
    ImpactRecordResponse,
    RepositoryVersionResponse,
    SymbolChangeResponse,
    UpdateHistoryResponse,
    UpdateRunCreateRequest,
    UpdateRunDetailResponse,
    UpdateRunResponse,
)
from app.services.update_service import UpdateService

router = APIRouter()
update_service = UpdateService()


async def _verify_repo_access(repository_id: str, user_id: str, db: AsyncSession):
    repo_repo = RepositoryRepository(db)
    repo = await repo_repo.get_by_id(repository_id)
    if not repo:
        raise NotFoundException("Repository not found")
    if repo.owner_id != user_id:
        raise ForbiddenException("You do not have access to this repository")
    return repo


@router.get(
    "/{repository_id}/updates/history",
    response_model=UpdateHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get repository update history",
    description="Returns timeline of analyzed update runs, versions, and sync status.",
)
async def get_repository_update_history(
    repository_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UpdateHistoryResponse:
    await _verify_repo_access(repository_id, current_user.id, db)
    history_data = await update_service.get_history(db, repository_id, current_user.id)
    return UpdateHistoryResponse.model_validate(history_data)


@router.post(
    "/{repository_id}/updates/analyze",
    response_model=UpdateRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger repository update analysis",
    description="Compares two versions or commits, extracts changed symbols, computes impact, and creates an update run.",
)
async def create_update_analysis(
    repository_id: str,
    payload: UpdateRunCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UpdateRunResponse:
    await _verify_repo_access(repository_id, current_user.id, db)
    run = await update_service.run_update_analysis(
        session=db,
        repository_id=repository_id,
        user_id=current_user.id,
        base_version_id=payload.base_version_id,
        target_version_id=payload.target_version_id,
        base_commit_sha=payload.base_commit_sha,
        target_commit_sha=payload.target_commit_sha,
        include_ai_summary=payload.include_ai_summary,
    )
    return UpdateRunResponse.model_validate(run)


@router.get(
    "/{repository_id}/updates/{update_run_id}",
    response_model=UpdateRunDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get update run detail",
    description="Returns full update analysis report including stats, impact metrics, and change lists.",
)
async def get_update_run_detail(
    repository_id: str,
    update_run_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UpdateRunDetailResponse:
    await _verify_repo_access(repository_id, current_user.id, db)
    detail = await update_service.get_update_run_detail(db, repository_id, update_run_id)
    run = detail["run"]

    return UpdateRunDetailResponse(
        id=run.id,
        repository_id=run.repository_id,
        base_version_id=run.base_version_id,
        target_version_id=run.target_version_id,
        base_commit_sha=run.base_commit_sha,
        target_commit_sha=run.target_commit_sha,
        status=run.status,
        total_files_changed=run.total_files_changed,
        total_symbols_changed=run.total_symbols_changed,
        total_additions=run.total_additions,
        total_deletions=run.total_deletions,
        ai_summary_status=run.ai_summary_status,
        analyzed_at=run.analyzed_at,
        created_at=run.created_at,
        base_version=RepositoryVersionResponse.model_validate(run.base_version) if run.base_version else None,
        target_version=RepositoryVersionResponse.model_validate(run.target_version) if run.target_version else None,
        stats=detail["stats"],
        impact_metrics=detail["impact_metrics"],
        impact_summary=detail["impact_summary"],
        ai_summary_markdown=run.ai_summary_markdown,
        file_changes=[FileChangeResponse.model_validate(f) for f in detail["file_changes"]],
        symbol_changes=[
            SymbolChangeResponse(
                id=s.id,
                update_run_id=s.update_run_id,
                file_change_id=s.file_change_id,
                symbol_name=s.symbol_name,
                symbol_type=s.symbol_type,
                scope=s.scope,
                change_type=s.change_type,  # type: ignore
                old_signature=s.old_signature,
                new_signature=s.new_signature,
                evidence=json.loads(s.evidence_json) if s.evidence_json else {},
            )
            for s in detail["symbol_changes"]
        ],
        impact_records=[ImpactRecordResponse.model_validate(r) for r in detail["impact_records"]],
    )


@router.get(
    "/{repository_id}/updates/{update_run_id}/files",
    response_model=List[FileChangeResponse],
    status_code=status.HTTP_200_OK,
    summary="List changed files for update",
    description="Returns files changed in an update run with optional change type filtering.",
)
async def list_update_file_changes(
    repository_id: str,
    update_run_id: str,
    change_type: Optional[str] = Query(None, description="Filter by change type (added, modified, deleted, renamed)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[FileChangeResponse]:
    await _verify_repo_access(repository_id, current_user.id, db)
    update_repo = UpdateRepository(db)
    changes = await update_repo.list_file_changes_by_run(update_run_id, change_type)
    return [FileChangeResponse.model_validate(c) for c in changes]


@router.get(
    "/{repository_id}/updates/{update_run_id}/symbols",
    response_model=List[SymbolChangeResponse],
    status_code=status.HTTP_200_OK,
    summary="List changed symbols for update",
    description="Returns code symbols changed in an update run with signatures and evidence.",
)
async def list_update_symbol_changes(
    repository_id: str,
    update_run_id: str,
    symbol_type: Optional[str] = Query(None, description="Filter by symbol type (function, method, class, endpoint)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[SymbolChangeResponse]:
    await _verify_repo_access(repository_id, current_user.id, db)
    update_repo = UpdateRepository(db)
    changes = await update_repo.list_symbol_changes_by_run(update_run_id, symbol_type)
    return [
        SymbolChangeResponse(
            id=s.id,
            update_run_id=s.update_run_id,
            file_change_id=s.file_change_id,
            symbol_name=s.symbol_name,
            symbol_type=s.symbol_type,
            scope=s.scope,
            change_type=s.change_type,  # type: ignore
            old_signature=s.old_signature,
            new_signature=s.new_signature,
            evidence=json.loads(s.evidence_json) if s.evidence_json else {},
        )
        for s in changes
    ]


@router.get(
    "/{repository_id}/updates/{update_run_id}/impact",
    response_model=List[ImpactRecordResponse],
    status_code=status.HTTP_200_OK,
    summary="List blast radius impact records",
    description="Returns components, files, and callers impacted by an update run.",
)
async def list_update_impact_records(
    repository_id: str,
    update_run_id: str,
    impact_level: Optional[str] = Query(None, description="Filter by impact level"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ImpactRecordResponse]:
    await _verify_repo_access(repository_id, current_user.id, db)
    update_repo = UpdateRepository(db)
    records = await update_repo.list_impact_records_by_run(update_run_id, impact_level)
    return [ImpactRecordResponse.model_validate(r) for r in records]


@router.get(
    "/{repository_id}/updates/{update_run_id}/graph",
    response_model=ImpactGraphResponse,
    status_code=status.HTTP_200_OK,
    summary="Get blast radius impact sub-graph",
    description="Returns interactive nodes and edges for blast radius visualization.",
)
async def get_update_impact_graph(
    repository_id: str,
    update_run_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ImpactGraphResponse:
    await _verify_repo_access(repository_id, current_user.id, db)
    graph_data = await update_service.get_impact_graph(db, repository_id, update_run_id)
    return ImpactGraphResponse.model_validate(graph_data)


@router.post(
    "/{repository_id}/updates/{update_run_id}/explain",
    response_model=AIExplainResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate AI change explanation",
    description="Generates an evidence-grounded markdown summary and risk assessment for an update run.",
)
async def explain_update_run(
    repository_id: str,
    update_run_id: str,
    payload: AIExplainRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AIExplainResponse:
    repo = await _verify_repo_access(repository_id, current_user.id, db)
    detail = await update_service.get_update_run_detail(db, repository_id, update_run_id)
    run = detail["run"]

    file_diff_dicts = [
        {"path": f.path, "change_type": f.change_type, "file_category": f.file_category, "additions": f.additions, "deletions": f.deletions}
        for f in detail["file_changes"]
    ]
    symbol_diff_dicts = [
        {
            "symbol_name": s.symbol_name,
            "symbol_type": s.symbol_type,
            "scope": s.scope,
            "change_type": s.change_type,
            "old_signature": s.old_signature,
            "new_signature": s.new_signature,
        }
        for s in detail["symbol_changes"]
    ]

    base_tag = run.base_version.version_tag if run.base_version else (run.base_commit_sha or "base")
    target_tag = run.target_version.version_tag if run.target_version else (run.target_commit_sha or "target")

    ai_res = await update_service.ai_summary_service.generate_change_summary(
        repository_name=repo.name,
        base_ref=base_tag,
        target_ref=target_tag,
        file_changes=file_diff_dicts,
        symbol_changes=symbol_diff_dicts,
        impact_metrics=detail["impact_metrics"],
        focus=payload.focus,
    )

    # Persist generated summary
    run.ai_summary_markdown = ai_res["ai_summary_markdown"]
    run.ai_summary_status = "completed"
    await db.commit()

    return AIExplainResponse(
        update_run_id=update_run_id,
        ai_summary_markdown=ai_res["ai_summary_markdown"],
        provider_used=ai_res["provider_used"],
        model_used=ai_res["model_used"],
        generated_at=ai_res["generated_at"],
    )


@router.post(
    "/{repository_id}/updates/compare",
    response_model=UpdateRunDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Ad-hoc commit or snapshot comparison",
    description="Compares any target commit/snapshot against base, returning complete diff and impact metrics.",
)
async def compare_repository_updates(
    repository_id: str,
    payload: AdHocCompareRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UpdateRunDetailResponse:
    await _verify_repo_access(repository_id, current_user.id, db)
    run = await update_service.run_update_analysis(
        session=db,
        repository_id=repository_id,
        user_id=current_user.id,
        base_commit_sha=payload.base_commit_sha,
        target_commit_sha=payload.target_commit_sha,
        include_ai_summary=payload.include_ai_summary,
    )
    detail = await update_service.get_update_run_detail(db, repository_id, run.id)
    r = detail["run"]

    return UpdateRunDetailResponse(
        id=r.id,
        repository_id=r.repository_id,
        base_version_id=r.base_version_id,
        target_version_id=r.target_version_id,
        base_commit_sha=r.base_commit_sha,
        target_commit_sha=r.target_commit_sha,
        status=r.status,
        total_files_changed=r.total_files_changed,
        total_symbols_changed=r.total_symbols_changed,
        total_additions=r.total_additions,
        total_deletions=r.total_deletions,
        ai_summary_status=r.ai_summary_status,
        analyzed_at=r.analyzed_at,
        created_at=r.created_at,
        base_version=RepositoryVersionResponse.model_validate(r.base_version) if r.base_version else None,
        target_version=RepositoryVersionResponse.model_validate(r.target_version) if r.target_version else None,
        stats=detail["stats"],
        impact_metrics=detail["impact_metrics"],
        impact_summary=detail["impact_summary"],
        ai_summary_markdown=r.ai_summary_markdown,
        file_changes=[FileChangeResponse.model_validate(f) for f in detail["file_changes"]],
        symbol_changes=[
            SymbolChangeResponse(
                id=s.id,
                update_run_id=s.update_run_id,
                file_change_id=s.file_change_id,
                symbol_name=s.symbol_name,
                symbol_type=s.symbol_type,
                scope=s.scope,
                change_type=s.change_type,  # type: ignore
                old_signature=s.old_signature,
                new_signature=s.new_signature,
                evidence=json.loads(s.evidence_json) if s.evidence_json else {},
            )
            for s in detail["symbol_changes"]
        ],
        impact_records=[ImpactRecordResponse.model_validate(rec) for rec in detail["impact_records"]],
    )
