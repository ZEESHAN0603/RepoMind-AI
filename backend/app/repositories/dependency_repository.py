import json
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.code_dependency import CodeDependency
from app.models.dependency_snapshot import DependencySnapshot


class DependencyRepository:
    """Database repository for dependency snapshots and relational code dependencies."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_snapshot(self, repository_id: str) -> Optional[DependencySnapshot]:
        """Fetches the precomputed dependency snapshot for a repository."""
        stmt = select(DependencySnapshot).where(DependencySnapshot.repository_id == repository_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def save_snapshot(
        self,
        repository_id: str,
        graph_data_json: str,
        total_modules: int,
        total_imports: int,
        internal_count: int,
        external_count: int,
        circular_count: int,
        unresolved_count: int,
    ) -> DependencySnapshot:
        """Upserts a precomputed dependency analysis snapshot."""
        existing = await self.get_snapshot(repository_id)
        now = datetime.now(timezone.utc)

        if existing:
            existing.graph_data_json = graph_data_json
            existing.total_modules = total_modules
            existing.total_imports = total_imports
            existing.internal_count = internal_count
            existing.external_count = external_count
            existing.circular_count = circular_count
            existing.unresolved_count = unresolved_count
            existing.analyzed_at = now
            return existing

        new_snapshot = DependencySnapshot(
            repository_id=repository_id,
            graph_data_json=graph_data_json,
            total_modules=total_modules,
            total_imports=total_imports,
            internal_count=internal_count,
            external_count=external_count,
            circular_count=circular_count,
            unresolved_count=unresolved_count,
            analyzed_at=now,
        )
        self.session.add(new_snapshot)
        return new_snapshot

    async def clear_dependencies(self, repository_id: str) -> None:
        """Removes all stored relational dependency edges for a repository."""
        stmt = delete(CodeDependency).where(CodeDependency.repository_id == repository_id)
        await self.session.execute(stmt)

    async def save_dependencies(self, dependencies: List[CodeDependency]) -> None:
        """Batch inserts relational code dependency records."""
        if dependencies:
            self.session.add_all(dependencies)

    async def list_dependencies_by_repo(
        self,
        repository_id: str,
        category: Optional[str] = None,
        is_circular: Optional[bool] = None,
    ) -> List[CodeDependency]:
        """Lists relational dependency records matching optional category/circular filters."""
        stmt = select(CodeDependency).where(CodeDependency.repository_id == repository_id)
        if category:
            stmt = stmt.where(CodeDependency.category == category)
        if is_circular is not None:
            stmt = stmt.where(CodeDependency.is_circular == is_circular)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_direct_dependencies(
        self,
        repository_id: str,
        file_path: str,
        direction: str = "both",
    ) -> List[CodeDependency]:
        """Returns direct dependencies (outgoing) or dependents (incoming) for a file path."""
        norm_path = file_path.replace("\\", "/").lstrip("/")
        stmt = select(CodeDependency).where(CodeDependency.repository_id == repository_id)

        if direction == "downstream":
            # Files imported by this file (outgoing edges)
            stmt = stmt.where(CodeDependency.source_path == norm_path)
        elif direction == "upstream":
            # Files importing this file (incoming edges)
            stmt = stmt.where(CodeDependency.target_path == norm_path)
        else:
            stmt = stmt.where(
                (CodeDependency.source_path == norm_path) | (CodeDependency.target_path == norm_path)
            )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())
