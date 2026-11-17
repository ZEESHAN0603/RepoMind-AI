from collections import defaultdict, deque
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.dependency_engine import DependencyAnalysisEngine
from app.core.exceptions import NotFoundException
from app.core.logging import logger
from app.models.code_dependency import CodeDependency
from app.models.code_import_export import CodeImportExport
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.models.repository_manifest import RepositoryDependencyManifest
from app.repositories.dependency_repository import DependencyRepository
from app.repositories.file_repository import FileRepository
from app.repositories.repository_repository import RepositoryRepository
from app.schemas.dependency import (
    CircularDependencyCycle,
    DependencyAnalysisData,
    DependencyRelationship,
    DirectDependenciesResponse,
    ExternalPackagesResponse,
    TransitiveDependenciesResponse,
    UnresolvedDependenciesResponse,
)


class DependencyService:
    """
    Business service orchestrating repository dependency analysis, circular dependency detection,
    transitive chain exploration, and cached snapshot retrieval.
    """

    async def get_or_build_graph(
        self,
        session: AsyncSession,
        repository_id: str,
        force_refresh: bool = False,
    ) -> DependencyAnalysisData:
        """
        Retrieves precomputed dependency graph or synthesizes a fresh one.
        """
        dep_repo = DependencyRepository(session)

        if not force_refresh:
            snapshot = await dep_repo.get_snapshot(repository_id)
            if snapshot and snapshot.graph_data_json:
                try:
                    data_dict = json.loads(snapshot.graph_data_json)
                    return DependencyAnalysisData.model_validate(data_dict)
                except Exception as ex:
                    logger.warning("Failed to deserialize dependency snapshot: %s", ex)

        # Synthesize fresh dependency graph
        return await self.analyze_repository_dependencies(session, repository_id)

    async def analyze_repository_dependencies(
        self,
        session: AsyncSession,
        repository_id: str,
    ) -> DependencyAnalysisData:
        """
        Executes complete static dependency extraction and cycle detection.
        Persists both cached snapshot JSON and individual relational dependency records.
        """
        repo_repo = RepositoryRepository(session)
        file_repo = FileRepository(session)
        dep_repo = DependencyRepository(session)

        repo = await repo_repo.get_by_id(repository_id)
        if not repo:
            raise NotFoundException("Repository not found")

        # 1. Fetch discovered files and manifests (normalized to POSIX forward slashes)
        all_files = await file_repo.list_files_by_repo(repository_id)
        file_paths = [f.path.replace("\\", "/").lstrip("/") for f in all_files if f.file_type == "file"]
        file_languages = {f.path.replace("\\", "/").lstrip("/"): f.language for f in all_files if f.language}
        file_path_to_id = {f.path.replace("\\", "/").lstrip("/"): f.id for f in all_files}

        # 2. Fetch existing static import statements
        imp_stmt = select(CodeImportExport).where(CodeImportExport.repository_id == repository_id)
        imp_res = await session.execute(imp_stmt)
        imports = list(imp_res.scalars().all())

        # Map file_id -> normalized POSIX file path
        id_to_path = {f.id: f.path.replace("\\", "/").lstrip("/") for f in all_files}

        imports_data = []
        for imp in imports:
            src_path = id_to_path.get(imp.file_id, "")
            if src_path:
                imports_data.append(
                    {
                        "source_file": src_path,
                        "source_module": imp.source_module,
                        "symbol_name": imp.symbol_name,
                        "line_number": imp.line_number,
                    }
                )

        # 3. Execute Analysis Engine
        engine = DependencyAnalysisEngine(
            workspace_files=file_paths,
            file_languages=file_languages,
        )
        analysis_data = engine.analyze(
            repository_id=repository_id,
            imports_data=imports_data,
        )

        # 4. Persist Snapshot
        payload_json = analysis_data.model_dump_json(by_alias=True)
        await dep_repo.save_snapshot(
            repository_id=repository_id,
            graph_data_json=payload_json,
            total_modules=analysis_data.total_modules,
            total_imports=analysis_data.total_imports,
            internal_count=analysis_data.internal_count,
            external_count=analysis_data.external_count,
            circular_count=analysis_data.circular_count,
            unresolved_count=analysis_data.unresolved_count,
        )

        # 5. Persist Relational CodeDependency Edges
        await dep_repo.clear_dependencies(repository_id)
        entities_to_save: List[CodeDependency] = []

        for rel in analysis_data.relationships:
            src_id = file_path_to_id.get(rel.source_path, "")
            tgt_id = file_path_to_id.get(rel.target_path) if rel.category == "internal" else None

            if not src_id:
                continue

            entities_to_save.append(
                CodeDependency(
                    repository_id=repository_id,
                    source_file_id=src_id,
                    target_file_id=tgt_id,
                    source_path=rel.source_path,
                    target_path=rel.target_path if rel.category == "internal" else None,
                    target_module=rel.target_module,
                    dependency_type="package" if rel.category == "external" else "file",
                    category=rel.category,
                    imported_symbols_json=json.dumps(rel.import_specifiers),
                    line_number=rel.line_number or 1,
                    is_circular=(rel.category == "circular"),
                    confidence=rel.confidence,
                )
            )

        await dep_repo.save_dependencies(entities_to_save)
        await session.commit()

        return analysis_data

    async def get_cycles(
        self,
        session: AsyncSession,
        repository_id: str,
    ) -> List[CircularDependencyCycle]:
        """Returns all detected circular dependency cycles for a repository."""
        data = await self.get_or_build_graph(session, repository_id)
        return data.cycles

    async def get_direct_dependencies(
        self,
        session: AsyncSession,
        repository_id: str,
        file_path: str,
        direction: str = "both",
    ) -> DirectDependenciesResponse:
        """Returns 1-hop direct dependencies or dependents for a file."""
        data = await self.get_or_build_graph(session, repository_id)
        norm_path = file_path.replace("\\", "/").lstrip("/")

        matched: List[DependencyRelationship] = []
        for rel in data.relationships:
            if direction == "downstream" and rel.source_path == norm_path:
                matched.append(rel)
            elif direction == "upstream" and rel.target_path == norm_path:
                matched.append(rel)
            elif direction == "both" and (rel.source_path == norm_path or rel.target_path == norm_path):
                matched.append(rel)

        return DirectDependenciesResponse(
            file_path=file_path,
            direction=direction,  # type: ignore
            dependencies=matched,
            count=len(matched),
        )

    async def get_transitive_dependencies(
        self,
        session: AsyncSession,
        repository_id: str,
        file_path: str,
        max_depth: int = 5,
    ) -> TransitiveDependenciesResponse:
        """Computes transitive dependency chains via BFS graph traversal."""
        data = await self.get_or_build_graph(session, repository_id)
        norm_path = file_path.replace("\\", "/").lstrip("/")

        # Build adjacency
        adj: Dict[str, List[str]] = defaultdict(list)
        for rel in data.relationships:
            if rel.category in ("internal", "circular"):
                adj[rel.source_path].append(rel.target_path)

        # BFS with depth tracking
        reachable: Set[str] = set()
        chains: List[List[str]] = []
        queue = deque([(norm_path, [norm_path], 0)])

        while queue:
            curr, path, depth = queue.popleft()
            if depth >= max_depth:
                continue

            for nxt in adj.get(curr, []):
                if nxt not in path:  # Prevent infinite loop in cycles
                    reachable.add(nxt)
                    new_path = path + [nxt]
                    chains.append(new_path)
                    queue.append((nxt, new_path, depth + 1))

        return TransitiveDependenciesResponse(
            file_path=file_path,
            max_depth=max_depth,
            chains=chains,
            reachable_nodes=sorted(list(reachable)),
            total_reachable=len(reachable),
        )

    async def get_unresolved_dependencies(
        self,
        session: AsyncSession,
        repository_id: str,
    ) -> UnresolvedDependenciesResponse:
        """Returns unresolved import statements and missing target files."""
        data = await self.get_or_build_graph(session, repository_id)
        unresolved = [r for r in data.relationships if r.category == "unresolved"]
        return UnresolvedDependenciesResponse(
            repository_id=repository_id,
            unresolved_count=len(unresolved),
            unresolved_imports=unresolved,
        )

    async def get_external_packages(
        self,
        session: AsyncSession,
        repository_id: str,
    ) -> ExternalPackagesResponse:
        """Returns external third-party package dependencies and consumer counts."""
        data = await self.get_or_build_graph(session, repository_id)
        pkg_consumers: Dict[str, List[str]] = defaultdict(list)

        for rel in data.relationships:
            if rel.category == "external":
                pkg_name = rel.target_module or rel.target_path.replace("pkg:", "")
                pkg_consumers[pkg_name].append(rel.source_path)

        packages = [
            {
                "name": name,
                "consumerCount": len(set(consumers)),
                "consumers": sorted(list(set(consumers))),
            }
            for name, consumers in sorted(pkg_consumers.items(), key=lambda x: len(x[1]), reverse=True)
        ]

        return ExternalPackagesResponse(
            repository_id=repository_id,
            package_count=len(packages),
            packages=packages,
        )
