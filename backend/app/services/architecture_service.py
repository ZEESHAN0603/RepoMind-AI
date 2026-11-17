import json
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.api_route_endpoint import ApiRouteEndpoint
from app.models.code_import_export import CodeImportExport
from app.models.code_symbol import CodeSymbol
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.repositories.architecture_repository import ArchitectureRepository
from app.services.architecture_graph_builder import ArchitectureGraphBuilder


class ArchitectureService:
    """Orchestrates architecture intelligence graph synthesis, caching, and querying."""

    async def get_or_build_graph(
        self,
        session: AsyncSession,
        repository_id: str,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        arch_repo = ArchitectureRepository(session)

        if not force_refresh:
            snapshot = await arch_repo.get_snapshot_by_repo(repository_id)
            if snapshot:
                try:
                    return json.loads(snapshot.graph_data_json)
                except Exception:
                    pass

        # Build graph from code intelligence tables
        files_query = select(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
        files_res = await session.execute(files_query)
        files = list(files_res.scalars().all())

        if not files:
            # Empty repository fallback
            return {
                "repositoryId": repository_id,
                "nodes": [],
                "edges": [],
                "views": {
                    vm: {"viewMode": vm, "title": vm.title(), "subtitle": "", "nodes": [], "edges": []}
                    for vm in ("system", "frontend", "backend", "api", "database", "modules")
                },
            }

        symbols_query = select(CodeSymbol).where(CodeSymbol.repository_id == repository_id)
        sym_res = await session.execute(symbols_query)
        symbols = list(sym_res.scalars().all())

        imports_query = select(CodeImportExport).where(CodeImportExport.repository_id == repository_id)
        imp_res = await session.execute(imports_query)
        imports = list(imp_res.scalars().all())

        endpoints_query = select(ApiRouteEndpoint).where(ApiRouteEndpoint.repository_id == repository_id)
        ep_res = await session.execute(endpoints_query)
        endpoints = list(ep_res.scalars().all())

        builder = ArchitectureGraphBuilder(
            repository_id=repository_id,
            files=files,
            symbols=symbols,
            imports_exports=imports,
            endpoints=endpoints,
        )

        graph_data = builder.build_graph()

        # Save snapshot
        await arch_repo.save_or_update_snapshot(repository_id, graph_data)
        await session.commit()

        return graph_data

    async def get_view(
        self,
        session: AsyncSession,
        repository_id: str,
        view_mode: str,
    ) -> Dict[str, Any]:
        graph = await self.get_or_build_graph(session, repository_id)
        views = graph.get("views", {})
        if view_mode not in views:
            raise NotFoundException(f"Architecture view '{view_mode}' not found")
        return views[view_mode]

    async def get_node_details(
        self,
        session: AsyncSession,
        repository_id: str,
        node_id: str,
    ) -> Dict[str, Any]:
        graph = await self.get_or_build_graph(session, repository_id)
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])

        target_node = next((n for n in nodes if n["id"] == node_id), None)
        if not target_node:
            raise NotFoundException(f"Architecture node '{node_id}' not found")

        # Find connected relationships
        incoming_edges = [e for e in edges if e["target"] == node_id]
        outgoing_edges = [e for e in edges if e["source"] == node_id]

        return {
            "node": target_node,
            "incomingRelationships": incoming_edges,
            "outgoingRelationships": outgoing_edges,
            "totalConnections": len(incoming_edges) + len(outgoing_edges),
        }
