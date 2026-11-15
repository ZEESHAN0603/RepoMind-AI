from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_route_endpoint import ApiRouteEndpoint
from app.models.code_import_export import CodeImportExport
from app.models.code_symbol import CodeSymbol


class CodeIntelligenceRepository:
    """Data access repository for code symbols, imports/exports, and API endpoints."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # Symbol operations
    async def save_symbols_batch(self, symbols: List[CodeSymbol]) -> None:
        self.session.add_all(symbols)
        await self.session.flush()

    async def delete_symbols_by_repo(self, repo_id: str) -> None:
        await self.session.execute(
            delete(CodeSymbol).where(CodeSymbol.repository_id == repo_id)
        )
        await self.session.flush()

    async def list_symbols_by_repo(
        self,
        repo_id: str,
        symbol_type: Optional[str] = None,
        file_id: Optional[str] = None,
        search: Optional[str] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Tuple[List[CodeSymbol], int]:
        query = select(CodeSymbol).where(CodeSymbol.repository_id == repo_id)
        count_query = select(func.count(CodeSymbol.id)).where(CodeSymbol.repository_id == repo_id)

        if symbol_type:
            query = query.where(CodeSymbol.symbol_type == symbol_type)
            count_query = count_query.where(CodeSymbol.symbol_type == symbol_type)

        if file_id:
            query = query.where(CodeSymbol.file_id == file_id)
            count_query = count_query.where(CodeSymbol.file_id == file_id)

        if search:
            query = query.where(CodeSymbol.name.ilike(f"%{search}%"))
            count_query = count_query.where(CodeSymbol.name.ilike(f"%{search}%"))

        total_count_res = await self.session.execute(count_query)
        total_count = total_count_res.scalar_one()

        query = query.order_by(CodeSymbol.name.asc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total_count

    async def get_symbol_by_id(self, symbol_id: str) -> Optional[CodeSymbol]:
        query = select(CodeSymbol).where(CodeSymbol.id == symbol_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_symbols_by_file(self, file_id: str) -> List[CodeSymbol]:
        query = (
            select(CodeSymbol)
            .where(CodeSymbol.file_id == file_id)
            .order_by(CodeSymbol.start_line.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    # Import / Export operations
    async def save_imports_exports_batch(self, items: List[CodeImportExport]) -> None:
        self.session.add_all(items)
        await self.session.flush()

    async def delete_imports_exports_by_repo(self, repo_id: str) -> None:
        await self.session.execute(
            delete(CodeImportExport).where(CodeImportExport.repository_id == repo_id)
        )
        await self.session.flush()

    async def list_imports_exports_by_repo(
        self,
        repo_id: str,
        statement_type: Optional[str] = None,
    ) -> List[CodeImportExport]:
        query = select(CodeImportExport).where(CodeImportExport.repository_id == repo_id)
        if statement_type:
            query = query.where(CodeImportExport.statement_type == statement_type)
        query = query.order_by(CodeImportExport.source_module.asc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    # API Endpoint operations
    async def save_endpoints_batch(self, endpoints: List[ApiRouteEndpoint]) -> None:
        self.session.add_all(endpoints)
        await self.session.flush()

    async def delete_endpoints_by_repo(self, repo_id: str) -> None:
        await self.session.execute(
            delete(ApiRouteEndpoint).where(ApiRouteEndpoint.repository_id == repo_id)
        )
        await self.session.flush()

    async def list_endpoints_by_repo(
        self,
        repo_id: str,
        framework: Optional[str] = None,
        http_method: Optional[str] = None,
    ) -> List[ApiRouteEndpoint]:
        query = select(ApiRouteEndpoint).where(ApiRouteEndpoint.repository_id == repo_id)
        if framework:
            query = query.where(ApiRouteEndpoint.framework.ilike(framework))
        if http_method:
            query = query.where(ApiRouteEndpoint.http_method.ilike(http_method))
        query = query.order_by(ApiRouteEndpoint.path.asc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    # Aggregate analysis stats
    async def get_analysis_stats(self, repo_id: str) -> Dict[str, Any]:
        # Count by symbol type
        sym_counts_query = (
            select(CodeSymbol.symbol_type, func.count(CodeSymbol.id))
            .where(CodeSymbol.repository_id == repo_id)
            .group_by(CodeSymbol.symbol_type)
        )
        sym_res = await self.session.execute(sym_counts_query)
        symbols_by_type = {row[0]: row[1] for row in sym_res.all()}

        # Total symbols
        total_symbols = sum(symbols_by_type.values())

        # Endpoints count
        endpoint_count_query = select(func.count(ApiRouteEndpoint.id)).where(
            ApiRouteEndpoint.repository_id == repo_id
        )
        ep_res = await self.session.execute(endpoint_count_query)
        total_endpoints = ep_res.scalar_one()

        # Endpoints by framework
        ep_fw_query = (
            select(ApiRouteEndpoint.framework, func.count(ApiRouteEndpoint.id))
            .where(ApiRouteEndpoint.repository_id == repo_id)
            .group_by(ApiRouteEndpoint.framework)
        )
        ep_fw_res = await self.session.execute(ep_fw_query)
        endpoints_by_framework = {row[0]: row[1] for row in ep_fw_res.all()}

        # Imports count
        imports_count_query = select(func.count(CodeImportExport.id)).where(
            CodeImportExport.repository_id == repo_id
        )
        imp_res = await self.session.execute(imports_count_query)
        total_imports_exports = imp_res.scalar_one()

        return {
            "total_symbols": total_symbols,
            "symbols_by_type": symbols_by_type,
            "total_endpoints": total_endpoints,
            "endpoints_by_framework": endpoints_by_framework,
            "total_imports_exports": total_imports_exports,
        }

