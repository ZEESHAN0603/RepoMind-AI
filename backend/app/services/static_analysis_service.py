import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.registry import ParserRegistry
from app.analysis.schemas import FileParseResult, ParseStatus
from app.core.config import settings
from app.core.exceptions import NotFoundException
from app.core.logging import logger
from app.models.api_route_endpoint import ApiRouteEndpoint
from app.models.code_import_export import CodeImportExport
from app.models.code_symbol import CodeSymbol
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.repositories.code_intelligence_repository import CodeIntelligenceRepository
from app.repositories.file_repository import FileRepository
from app.repositories.repository_repository import RepositoryRepository
from app.services.workspace_service import WorkspaceService

# Maximum single-file size for static AST parsing (2 MB) to preserve memory constraints
MAX_FILE_PARSE_BYTES = 2 * 1024 * 1024


class StaticAnalysisService:
    """Orchestrates repository-wide static code intelligence and AST analysis."""

    def __init__(self, workspace_service: Optional[WorkspaceService] = None) -> None:
        self.workspace_service = workspace_service or WorkspaceService()

    async def analyze_repository(
        self,
        session: AsyncSession,
        repository_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Executes static analysis across all discovered source files in a repository.
        Replaces previous analysis results cleanly to prevent duplication.
        """
        repo_repo = RepositoryRepository(session)
        file_repo = FileRepository(session)
        ci_repo = CodeIntelligenceRepository(session)

        repo = await repo_repo.get_by_id(repository_id)
        if not repo:
            raise NotFoundException("Repository not found")

        workspace_path = self.workspace_service.get_repository_workspace_path(user_id, repository_id)
        if not workspace_path.exists():
            raise NotFoundException("Repository workspace files are not available on disk")

        # Fetch discovered files
        all_files = await file_repo.list_files_by_repo(repository_id)
        source_files = [f for f in all_files if f.file_type == "file" and not f.is_binary]

        symbols_to_save: List[CodeSymbol] = []
        imports_to_save: List[CodeImportExport] = []
        endpoints_to_save: List[ApiRouteEndpoint] = []

        files_parsed = 0
        files_partial = 0
        files_failed = 0
        files_skipped = 0
        parse_errors: List[Dict[str, Any]] = []

        for file_entity in source_files:
            file_disk_path = workspace_path / file_entity.path

            # Guard against oversized files or missing files
            if not file_disk_path.is_file():
                files_skipped += 1
                continue

            try:
                file_size = file_disk_path.stat().st_size
                if file_size > MAX_FILE_PARSE_BYTES:
                    files_skipped += 1
                    continue

                with open(file_disk_path, "r", encoding="utf-8", errors="replace") as f:
                    code_content = f.read()
            except Exception as e:
                logger.warning("Could not read file %s for analysis: %s", file_entity.path, e)
                files_failed += 1
                parse_errors.append({"file": file_entity.path, "error": str(e)})
                continue

            # Determine parser
            parser = ParserRegistry.get_parser(
                language=file_entity.language,
                file_path=file_entity.path,
            )

            parse_res: FileParseResult = parser.parse_source(code_content, file_path=file_entity.path)

            if parse_res.status == ParseStatus.SUCCESS:
                files_parsed += 1
            elif parse_res.status == ParseStatus.PARTIAL:
                files_partial += 1
            elif parse_res.status == ParseStatus.FAILED:
                files_failed += 1
            elif parse_res.status in (ParseStatus.UNSUPPORTED, ParseStatus.SKIPPED):
                files_skipped += 1

            if parse_res.errors:
                for err in parse_res.errors:
                    parse_errors.append({
                        "file": file_entity.path,
                        "line": err.line,
                        "column": err.column,
                        "message": err.message,
                    })

            # Convert symbols
            for sym in parse_res.symbols:
                params_json = json.dumps([p.to_dict() for p in sym.parameters])
                decorators_json = json.dumps(sym.decorators)
                bases_json = json.dumps(sym.bases_or_interfaces)

                symbols_to_save.append(
                    CodeSymbol(
                        repository_id=repository_id,
                        file_id=file_entity.id,
                        name=sym.name,
                        symbol_type=sym.symbol_type.value,
                        scope=sym.scope,
                        signature=sym.signature,
                        docstring=sym.docstring,
                        start_line=sym.start_line,
                        end_line=sym.end_line,
                        start_column=sym.start_column,
                        end_column=sym.end_column,
                        is_async=sym.is_async,
                        is_exported=sym.is_exported,
                        visibility=sym.visibility,
                        parameters=params_json,
                        return_type=sym.return_type,
                        decorators=decorators_json,
                        bases_or_interfaces=bases_json,
                        confidence=sym.confidence.value,
                    )
                )

            # Convert imports/exports
            for ie in parse_res.imports_exports:
                imports_to_save.append(
                    CodeImportExport(
                        repository_id=repository_id,
                        file_id=file_entity.id,
                        statement_type=ie.statement_type,
                        source_module=ie.source_module,
                        symbol_name=ie.symbol_name,
                        alias=ie.alias,
                        is_relative=ie.is_relative,
                        is_default=ie.is_default,
                        line_number=ie.line_number,
                    )
                )

            # Convert endpoints
            for ep in parse_res.endpoints:
                endpoints_to_save.append(
                    ApiRouteEndpoint(
                        repository_id=repository_id,
                        file_id=file_entity.id,
                        http_method=ep.http_method,
                        path=ep.path,
                        handler_name=ep.handler_name,
                        framework=ep.framework,
                        start_line=ep.start_line,
                        end_line=ep.end_line,
                        confidence=ep.confidence.value,
                        metadata_json=json.dumps(ep.metadata),
                    )
                )

        # Clear existing analysis results to avoid duplicate accumulation
        await ci_repo.delete_symbols_by_repo(repository_id)
        await ci_repo.delete_imports_exports_by_repo(repository_id)
        await ci_repo.delete_endpoints_by_repo(repository_id)

        # Save new records in batches
        if symbols_to_save:
            await ci_repo.save_symbols_batch(symbols_to_save)
        if imports_to_save:
            await ci_repo.save_imports_exports_batch(imports_to_save)
        if endpoints_to_save:
            await ci_repo.save_endpoints_batch(endpoints_to_save)

        # Update repository timestamp
        repo.last_analyzed_at = datetime.now(timezone.utc)
        await repo_repo.update(repo)
        await session.commit()

        stats = await ci_repo.get_analysis_stats(repository_id)

        return {
            "repository_id": repository_id,
            "files_analyzed": len(source_files),
            "files_parsed": files_parsed,
            "files_partial": files_partial,
            "files_failed": files_failed,
            "files_skipped": files_skipped,
            "symbols_extracted": len(symbols_to_save),
            "endpoints_extracted": len(endpoints_to_save),
            "imports_exports_extracted": len(imports_to_save),
            "stats": stats,
            "errors": parse_errors[:50],  # Return up to 50 parser error notices
        }

