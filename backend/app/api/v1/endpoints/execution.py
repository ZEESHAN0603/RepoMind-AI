from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.core.exceptions import ForbiddenException, NotFoundException
from app.db.session import get_db
from app.models.user import User
from app.repositories.repository_repository import RepositoryRepository
from app.schemas.execution import (
    ExecutionAnalysisSummaryResponse,
    ExecutionEntryPointsListResponse,
    ExecutionExplainRequest,
    ExecutionExplainResponse,
    ExecutionNodeCallsResponse,
    ExecutionTracePathResponse,
    ExecutionWorkspaceResponse,
)
from app.services.execution_explainer_service import ExecutionExplainerService
from app.services.execution_flow_service import ExecutionFlowService

router = APIRouter()
execution_service = ExecutionFlowService()
explainer_service = ExecutionExplainerService()


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


@router.post(
    "/{repository_id}/execution/analyze",
    response_model=ExecutionAnalysisSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger repository execution-flow analysis",
    description="Parses functions, calls, and entry points, resolves cross-file relationships, and builds execution snapshot cache.",
)
async def analyze_execution_flows(
    repository_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExecutionAnalysisSummaryResponse:
    await _verify_repo_access(repository_id, current_user.id, db)
    summary = await execution_service.analyze_execution_flows(
        session=db,
        repository_id=repository_id,
        user_id=current_user.id,
    )
    return ExecutionAnalysisSummaryResponse.model_validate(summary)


@router.get(
    "/{repository_id}/execution/workspace",
    response_model=ExecutionWorkspaceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get execution flow workspace",
    description="Returns precomputed execution flow workspace including discovered functions, traces, and call graphs.",
)
async def get_execution_workspace(
    repository_id: str,
    force_refresh: bool = Query(False, description="Force re-extraction of execution flows"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExecutionWorkspaceResponse:
    await _verify_repo_access(repository_id, current_user.id, db)
    workspace = await execution_service.get_or_build_workspace(
        session=db,
        repository_id=repository_id,
        user_id=current_user.id,
        force_refresh=force_refresh,
    )
    return ExecutionWorkspaceResponse.model_validate(workspace)


@router.get(
    "/{repository_id}/execution/entry-points",
    response_model=ExecutionEntryPointsListResponse,
    status_code=status.HTTP_200_OK,
    summary="List detected execution entry points",
    description="Lists all discovered application entry points (HTTP routes, startup scripts, CLI commands, background jobs).",
)
async def list_entry_points(
    repository_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExecutionEntryPointsListResponse:
    await _verify_repo_access(repository_id, current_user.id, db)
    eps = await execution_service.list_entry_points(
        session=db,
        repository_id=repository_id,
        user_id=current_user.id,
    )
    return ExecutionEntryPointsListResponse(
        repository_id=repository_id,
        total_count=len(eps),
        entry_points=eps,
    )


@router.get(
    "/{repository_id}/execution/nodes/{symbol_id}/calls",
    response_model=ExecutionNodeCallsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get callers and callees for symbol",
    description="Returns incoming callers and outgoing callees with file coordinates and invocation arguments.",
)
async def get_node_calls(
    repository_id: str,
    symbol_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExecutionNodeCallsResponse:
    await _verify_repo_access(repository_id, current_user.id, db)
    calls_res = await execution_service.get_symbol_calls(
        session=db,
        repository_id=repository_id,
        symbol_id=symbol_id,
    )
    return ExecutionNodeCallsResponse.model_validate(calls_res)


@router.get(
    "/{repository_id}/execution/trace-path",
    response_model=ExecutionTracePathResponse,
    status_code=status.HTTP_200_OK,
    summary="Trace shortest execution path between two symbols",
    description="Computes shortest directional call path from source symbol to target symbol.",
)
async def trace_execution_path(
    repository_id: str,
    source_symbol_id: str = Query(..., description="Source function or method symbol ID"),
    target_symbol_id: str = Query(..., description="Target function or method symbol ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExecutionTracePathResponse:
    await _verify_repo_access(repository_id, current_user.id, db)
    path_res = await execution_service.trace_execution_path(
        session=db,
        repository_id=repository_id,
        source_symbol_id=source_symbol_id,
        target_symbol_id=target_symbol_id,
    )
    return ExecutionTracePathResponse.model_validate(path_res)


@router.post(
    "/{repository_id}/execution/explain",
    response_model=ExecutionExplainResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate AI explanation for execution flow",
    description="Synthesizes grounded explanation of execution flow using Ollama or Gemini fallback.",
)
async def explain_execution_flow(
    repository_id: str,
    payload: ExecutionExplainRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExecutionExplainResponse:
    repo = await _verify_repo_access(repository_id, current_user.id, db)
    workspace = await execution_service.get_or_build_workspace(
        session=db,
        repository_id=repository_id,
        user_id=current_user.id,
    )

    traces = workspace.get("traces", [])
    target_trace = None
    if payload.flowId:
        target_trace = next((t for t in traces if t["flow"]["id"] == payload.flowId), None)
    if not target_trace and traces:
        target_trace = traces[0]

    if not target_trace:
        return ExecutionExplainResponse(
            flowId=payload.flowId,
            summary="No discovered execution traces available to explain in this repository.",
            verifiedSteps=[],
            uncertainties=["Static analysis found 0 execution flows."],
            citations=[],
            providerUsed="none",
        )

    flow_obj = target_trace["flow"]
    nodes = target_trace.get("nodes", [])
    steps = flow_obj.get("steps", [])

    explanation = await explainer_service.explain_flow(
        repository_name=repo.name,
        flow_title=flow_obj.get("title", "Execution Flow"),
        entry_point=flow_obj.get("entryPoint", "Entry Point"),
        steps=steps,
        nodes=nodes,
        focus_question=payload.focusQuestion,
    )
    explanation["flowId"] = flow_obj.get("id")

    return ExecutionExplainResponse.model_validate(explanation)
