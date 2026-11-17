from collections import defaultdict, deque
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.call_resolver import CallResolver
from app.analysis.entry_point_detector import EntryPointDetector
from app.analysis.python_parser import PythonAstParser
from app.analysis.registry import ParserRegistry
from app.analysis.schemas import FileParseResult, ParseStatus
from app.core.exceptions import NotFoundException
from app.core.logging import logger
from app.models.api_route_endpoint import ApiRouteEndpoint
from app.models.code_call import CodeCall
from app.models.code_import_export import CodeImportExport
from app.models.code_symbol import CodeSymbol
from app.models.execution_entry_point import ExecutionEntryPoint
from app.models.execution_snapshot import ExecutionSnapshot
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.repositories.execution_repository import ExecutionRepository
from app.repositories.file_repository import FileRepository
from app.repositories.repository_repository import RepositoryRepository
from app.services.execution_graph_builder import ExecutionFlowGraphBuilder
from app.services.workspace_service import WorkspaceService


class ExecutionFlowService:
    """
    Orchestrates repository execution-flow extraction, static call resolution,
    entry-point detection, graph synthesis, and cached snapshot retrieval.
    """

    def __init__(self, workspace_service: Optional[WorkspaceService] = None) -> None:
        self.workspace_service = workspace_service or WorkspaceService()

    async def analyze_execution_flows(
        self,
        session: AsyncSession,
        repository_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Parses repository source files, extracts function calls and entry points,
        resolves calls using CallResolver, and saves a precomputed ExecutionSnapshot.
        """
        repo_repo = RepositoryRepository(session)
        file_repo = FileRepository(session)
        exec_repo = ExecutionRepository(session)

        repo = await repo_repo.get_by_id(repository_id)
        if not repo:
            raise NotFoundException("Repository not found")

        workspace_path = self.workspace_service.get_repository_workspace_path(user_id, repository_id)

        # 1. Fetch discovered files
        all_files = await file_repo.list_files_by_repo(repository_id)
        source_files = [f for f in all_files if f.file_type == "file" and not f.is_binary]

        # 2. Fetch existing symbols, endpoints, and imports
        sym_stmt = select(CodeSymbol).where(CodeSymbol.repository_id == repository_id)
        sym_res = await session.execute(sym_stmt)
        symbols = list(sym_res.scalars().all())

        ep_stmt = select(ApiRouteEndpoint).where(ApiRouteEndpoint.repository_id == repository_id)
        ep_res = await session.execute(ep_stmt)
        endpoints = list(ep_res.scalars().all())

        imp_stmt = select(CodeImportExport).where(CodeImportExport.repository_id == repository_id)
        imp_res = await session.execute(imp_stmt)
        imports = list(imp_res.scalars().all())

        # Map file_id -> file path
        file_id_to_path: Dict[str, str] = {
            f.id: f.path.replace("\\", "/").lstrip("/") for f in source_files
        }
        file_path_to_file: Dict[str, RepositoryFile] = {
            f.path.replace("\\", "/").lstrip("/"): f for f in source_files
        }

        # Group symbols and imports by file_path for CallResolver
        symbols_by_file: Dict[str, List[CodeSymbol]] = {}
        for s in symbols:
            s_fp = file_id_to_path.get(s.file_id)
            if s_fp:
                if s_fp not in symbols_by_file:
                    symbols_by_file[s_fp] = []
                symbols_by_file[s_fp].append(s)

        imports_by_file: Dict[str, List[CodeImportExport]] = {}
        for imp in imports:
            i_fp = file_id_to_path.get(imp.file_id)
            if i_fp:
                if i_fp not in imports_by_file:
                    imports_by_file[i_fp] = []
                imports_by_file[i_fp].append(imp)

        all_file_paths = list(file_path_to_file.keys())
        resolver = CallResolver(
            workspace_files=all_file_paths,
            symbols_by_file=symbols_by_file,
            imports_by_file=imports_by_file,
        )

        calls_to_save: List[CodeCall] = []

        # 3. Parse files on disk for calls
        for f in source_files:
            if not workspace_path.exists():
                continue
            disk_path = workspace_path / f.path
            if not disk_path.is_file():
                continue

            try:
                with open(disk_path, "r", encoding="utf-8", errors="replace") as fh:
                    code_content = fh.read()
            except Exception as e:
                logger.warning("Could not read file %s for call extraction: %s", f.path, e)
                continue

            parser = ParserRegistry.get_parser(language=f.language, file_path=f.path)
            parse_res: FileParseResult = parser.parse_source(code_content, file_path=f.path)

            if parse_res.calls:
                norm_fp = f.path.replace("\\", "/").lstrip("/")
                resolved_calls = resolver.resolve_calls_for_file(norm_fp, parse_res.calls)

                for rc in resolved_calls:
                    target_file = file_path_to_file.get(rc.callee_file_path) if rc.callee_file_path else None
                    calls_to_save.append(
                        CodeCall(
                            repository_id=repository_id,
                            caller_symbol_id=rc.caller_symbol_id,
                            callee_symbol_id=rc.callee_symbol_id,
                            caller_name=rc.caller_name,
                            callee_name=rc.callee_name,
                            caller_file_id=f.id,
                            callee_file_id=target_file.id if target_file else None,
                            caller_file_path=rc.caller_file_path,
                            callee_file_path=rc.callee_file_path,
                            line_number=rc.line_number,
                            call_type=rc.call_type,
                            resolution_status=rc.resolution_status,
                            confidence=rc.confidence,
                            arguments_json=json.dumps(rc.arguments),
                            evidence=rc.evidence,
                        )
                    )

        # 4. Detect Entry Points
        detected_eps = EntryPointDetector.detect_entry_points(
            files=source_files,
            symbols=symbols,
            endpoints=endpoints,
        )

        entry_points_to_save: List[ExecutionEntryPoint] = []
        for ep in detected_eps:
            f_ent = file_path_to_file.get(ep.file_path)
            entry_points_to_save.append(
                ExecutionEntryPoint(
                    repository_id=repository_id,
                    symbol_id=ep.symbol_id,
                    file_id=f_ent.id if f_ent else None,
                    file_path=ep.file_path,
                    entry_type=ep.entry_type,
                    display_name=ep.display_name,
                    symbol_name=ep.symbol_name,
                    route_path=ep.route_path,
                    http_method=ep.http_method,
                    line_number=ep.line_number,
                    confidence=ep.confidence,
                    description=ep.description,
                )
            )

        # 5. Persist calls and entry points
        await exec_repo.delete_calls_by_repo(repository_id)
        await exec_repo.delete_entry_points_by_repo(repository_id)

        if calls_to_save:
            await exec_repo.save_calls_batch(calls_to_save)
        if entry_points_to_save:
            await exec_repo.save_entry_points_batch(entry_points_to_save)

        # 6. Build and cache ExecutionSnapshot
        builder = ExecutionFlowGraphBuilder(
            repository_id=repository_id,
            repository_name=repo.name,
            files=source_files,
            symbols=symbols,
            endpoints=endpoints,
            calls=calls_to_save,
            entry_points=entry_points_to_save,
            workspace_path=workspace_path if workspace_path.exists() else None,
        )
        workspace_payload = builder.build_workspace()

        await exec_repo.save_or_update_snapshot(
            repository_id=repository_id,
            workspace_data=workspace_payload,
            entry_point_count=len(entry_points_to_save),
            call_count=len(calls_to_save),
        )
        await session.commit()

        return {
            "repository_id": repository_id,
            "calls_extracted": len(calls_to_save),
            "entry_points_detected": len(entry_points_to_save),
            "traces_generated": len(workspace_payload.get("traces", [])),
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_or_build_workspace(
        self,
        session: AsyncSession,
        repository_id: str,
        user_id: str,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Returns the ExecutionTraceWorkspace, utilizing cached snapshot when available."""
        exec_repo = ExecutionRepository(session)
        repo_repo = RepositoryRepository(session)

        repo = await repo_repo.get_by_id(repository_id)
        if not repo:
            raise NotFoundException("Repository not found")

        if not force_refresh:
            snap = await exec_repo.get_snapshot_by_repo(repository_id)
            if snap:
                try:
                    return json.loads(snap.workspace_data_json)
                except Exception:
                    pass

        # Trigger analysis if no snapshot exists
        res = await self.analyze_execution_flows(session, repository_id, user_id)
        snap = await exec_repo.get_snapshot_by_repo(repository_id)
        if snap:
            return json.loads(snap.workspace_data_json)

        return {
            "repositoryId": repository_id,
            "repositoryName": repo.name,
            "functions": [],
            "traces": [],
        }

    async def list_entry_points(
        self,
        session: AsyncSession,
        repository_id: str,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        exec_repo = ExecutionRepository(session)
        eps = await exec_repo.list_entry_points_by_repo(repository_id)
        if not eps:
            await self.analyze_execution_flows(session, repository_id, user_id)
            eps = await exec_repo.list_entry_points_by_repo(repository_id)

        return [
            {
                "id": ep.id,
                "entry_type": ep.entry_type,
                "display_name": ep.display_name,
                "file_path": ep.file_path,
                "symbol_name": ep.symbol_name,
                "route_path": ep.route_path,
                "http_method": ep.http_method,
                "line_number": ep.line_number,
                "confidence": ep.confidence,
                "description": ep.description,
            }
            for ep in eps
        ]

    async def get_symbol_calls(
        self,
        session: AsyncSession,
        repository_id: str,
        symbol_id: str,
    ) -> Dict[str, Any]:
        exec_repo = ExecutionRepository(session)
        calls_dict = await exec_repo.list_calls_for_symbol(repository_id, symbol_id)

        def map_call(c: CodeCall) -> Dict[str, Any]:
            return {
                "id": c.id,
                "caller_name": c.caller_name,
                "callee_name": c.callee_name,
                "caller_file_path": c.caller_file_path,
                "callee_file_path": c.callee_file_path,
                "line_number": c.line_number,
                "call_type": c.call_type,
                "resolution_status": c.resolution_status,
                "confidence": c.confidence,
                "arguments": json.loads(c.arguments_json) if c.arguments_json else [],
                "evidence": c.evidence,
            }

        return {
            "symbol_id": symbol_id,
            "incoming": [map_call(c) for c in calls_dict["incoming"]],
            "outgoing": [map_call(c) for c in calls_dict["outgoing"]],
        }

    async def trace_execution_path(
        self,
        session: AsyncSession,
        repository_id: str,
        source_symbol_id: str,
        target_symbol_id: str,
    ) -> Dict[str, Any]:
        """Finds shortest execution call path from source_symbol_id to target_symbol_id using BFS."""
        exec_repo = ExecutionRepository(session)
        all_calls = await exec_repo.list_calls_by_repo(repository_id)

        adj: Dict[str, List[CodeCall]] = defaultdict(list)
        for c in all_calls:
            if c.caller_symbol_id and c.callee_symbol_id:
                adj[c.caller_symbol_id].append(c)

        queue = deque([(source_symbol_id, [])])
        visited = {source_symbol_id}

        while queue:
            curr, path = queue.popleft()
            if curr == target_symbol_id:
                steps = []
                for idx, c in enumerate(path):
                    steps.append({
                        "step": idx + 1,
                        "from_symbol": c.caller_name or c.caller_symbol_id,
                        "to_symbol": c.callee_name or c.callee_symbol_id,
                        "call_type": c.call_type,
                        "line_number": c.line_number,
                        "evidence": c.evidence,
                    })
                return {
                    "source_symbol_id": source_symbol_id,
                    "target_symbol_id": target_symbol_id,
                    "path_found": True,
                    "path_length": len(path),
                    "steps": steps,
                }

            for edge in adj.get(curr, []):
                nxt = edge.callee_symbol_id
                if nxt and nxt not in visited:
                    visited.add(nxt)
                    queue.append((nxt, path + [edge]))

        return {
            "source_symbol_id": source_symbol_id,
            "target_symbol_id": target_symbol_id,
            "path_found": False,
            "path_length": 0,
            "steps": [],
        }
