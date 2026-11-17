import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.architecture_snapshot import ArchitectureSnapshot


class ArchitectureRepository:
    """Data access repository for architecture graph snapshots."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_snapshot_by_repo(self, repo_id: str) -> Optional[ArchitectureSnapshot]:
        query = select(ArchitectureSnapshot).where(ArchitectureSnapshot.repository_id == repo_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def save_or_update_snapshot(
        self,
        repo_id: str,
        graph_data: Dict[str, Any],
    ) -> ArchitectureSnapshot:
        existing = await self.get_snapshot_by_repo(repo_id)
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])
        graph_json = json.dumps(graph_data)

        if existing:
            existing.graph_data_json = graph_json
            existing.node_count = len(nodes)
            existing.edge_count = len(edges)
            existing.analyzed_at = datetime.now(timezone.utc)
            await self.session.flush()
            return existing

        new_snapshot = ArchitectureSnapshot(
            repository_id=repo_id,
            graph_data_json=graph_json,
            node_count=len(nodes),
            edge_count=len(edges),
            analyzed_at=datetime.now(timezone.utc),
        )
        self.session.add(new_snapshot)
        await self.session.flush()
        return new_snapshot

    async def delete_snapshot_by_repo(self, repo_id: str) -> None:
        await self.session.execute(
            delete(ArchitectureSnapshot).where(ArchitectureSnapshot.repository_id == repo_id)
        )
        await self.session.flush()
