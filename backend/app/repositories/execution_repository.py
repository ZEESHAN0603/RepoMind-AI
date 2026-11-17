from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.code_call import CodeCall
from app.models.execution_entry_point import ExecutionEntryPoint
from app.models.execution_snapshot import ExecutionSnapshot


class ExecutionRepository:
    """Async repository for persisting and querying execution-flow calls, entry points, and snapshots."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_calls_batch(self, calls: List[CodeCall]) -> None:
        if not calls:
            return
        self.session.add_all(calls)
        await self.session.flush()

    async def delete_calls_by_repo(self, repository_id: str) -> None:
        stmt = delete(CodeCall).where(CodeCall.repository_id == repository_id)
        await self.session.execute(stmt)
        await self.session.flush()

    async def list_calls_by_repo(self, repository_id: str) -> List[CodeCall]:
        stmt = select(CodeCall).where(CodeCall.repository_id == repository_id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def list_calls_for_symbol(self, repository_id: str, symbol_id: str) -> Dict[str, List[CodeCall]]:
        incoming_stmt = select(CodeCall).where(
            CodeCall.repository_id == repository_id,
            CodeCall.callee_symbol_id == symbol_id,
        )
        outgoing_stmt = select(CodeCall).where(
            CodeCall.repository_id == repository_id,
            CodeCall.caller_symbol_id == symbol_id,
        )
        inc_res = await self.session.execute(incoming_stmt)
        out_res = await self.session.execute(outgoing_stmt)
        return {
            "incoming": list(inc_res.scalars().all()),
            "outgoing": list(out_res.scalars().all()),
        }

    async def save_entry_points_batch(self, entry_points: List[ExecutionEntryPoint]) -> None:
        if not entry_points:
            return
        self.session.add_all(entry_points)
        await self.session.flush()

    async def delete_entry_points_by_repo(self, repository_id: str) -> None:
        stmt = delete(ExecutionEntryPoint).where(ExecutionEntryPoint.repository_id == repository_id)
        await self.session.execute(stmt)
        await self.session.flush()

    async def list_entry_points_by_repo(self, repository_id: str) -> List[ExecutionEntryPoint]:
        stmt = select(ExecutionEntryPoint).where(ExecutionEntryPoint.repository_id == repository_id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def save_or_update_snapshot(
        self,
        repository_id: str,
        workspace_data: Dict[str, Any],
        entry_point_count: int,
        call_count: int,
    ) -> ExecutionSnapshot:
        stmt = select(ExecutionSnapshot).where(ExecutionSnapshot.repository_id == repository_id)
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()

        json_str = json.dumps(workspace_data)

        if existing:
            existing.workspace_data_json = json_str
            existing.entry_point_count = entry_point_count
            existing.call_count = call_count
            existing.analyzed_at = datetime.now(timezone.utc)
            await self.session.flush()
            return existing

        new_snap = ExecutionSnapshot(
            repository_id=repository_id,
            workspace_data_json=json_str,
            entry_point_count=entry_point_count,
            call_count=call_count,
            analyzed_at=datetime.now(timezone.utc),
        )
        self.session.add(new_snap)
        await self.session.flush()
        return new_snap

    async def get_snapshot_by_repo(self, repository_id: str) -> Optional[ExecutionSnapshot]:
        stmt = select(ExecutionSnapshot).where(ExecutionSnapshot.repository_id == repository_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def delete_snapshot_by_repo(self, repository_id: str) -> None:
        stmt = delete(ExecutionSnapshot).where(ExecutionSnapshot.repository_id == repository_id)
        await self.session.execute(stmt)
        await self.session.flush()
