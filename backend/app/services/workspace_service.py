import os
import shutil
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.core.exceptions import BadRequestException
from app.core.logging import logger


class WorkspaceService:
    """Manages secure on-disk workspaces for ingested repositories."""

    def __init__(self, base_storage_dir: Optional[str] = None) -> None:
        self.base_dir = Path(base_storage_dir or settings.STORAGE_DIR).resolve()
        self.workspaces_root = self.base_dir / "workspaces"
        self.temp_root = self.base_dir / "tmp"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        self.workspaces_root.mkdir(parents=True, exist_ok=True)
        self.temp_root.mkdir(parents=True, exist_ok=True)

    def get_repository_workspace_path(self, user_id: str, repository_id: str) -> Path:
        """Computes and validates the isolated filesystem path for a user repository."""
        # Prevent any directory traversal in user_id or repository_id
        safe_user = Path(user_id).name
        safe_repo = Path(repository_id).name
        ws_path = (self.workspaces_root / safe_user / safe_repo).resolve()

        # Enforce that ws_path must be strictly inside workspaces_root
        try:
            ws_path.relative_to(self.workspaces_root)
        except ValueError:
            raise BadRequestException("Invalid repository workspace path")

        return ws_path

    def prepare_repository_workspace(self, user_id: str, repository_id: str, clean: bool = True) -> Path:
        """Prepares an empty or existing workspace directory."""
        ws_path = self.get_repository_workspace_path(user_id, repository_id)
        if clean and ws_path.exists():
            shutil.rmtree(ws_path, ignore_errors=True)
        ws_path.mkdir(parents=True, exist_ok=True)
        return ws_path

    def delete_repository_workspace(self, user_id: str, repository_id: str) -> None:
        """Safely cleans up the repository workspace on disk."""
        try:
            ws_path = self.get_repository_workspace_path(user_id, repository_id)
            if ws_path.exists():
                shutil.rmtree(ws_path, ignore_errors=True)
                logger.info("Deleted workspace for repository: %s", repository_id)
        except Exception as e:
            logger.warning("Failed to delete workspace for repo %s: %s", repository_id, e)

    def create_temp_dir(self, prefix: str = "ingest_") -> Path:
        """Creates a secure temporary directory inside the storage temp area."""
        import uuid
        temp_dir = self.temp_root / f"{prefix}{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir

    def cleanup_temp_dir(self, temp_dir: Path) -> None:
        """Cleans up a temporary directory."""
        if temp_dir.exists() and temp_dir != self.temp_root:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def get_snapshot_path(self, user_id: str, repository_id: str, snapshot_id: str = "baseline") -> Path:
        """Returns isolated on-disk path for a repository version snapshot."""
        safe_user = Path(user_id).name
        safe_repo = Path(repository_id).name
        safe_snap = Path(snapshot_id.replace(":", "_").replace("/", "_")).name
        snap_path = (self.base_dir / "snapshots" / safe_user / safe_repo / safe_snap).resolve()
        return snap_path

    def create_snapshot(self, user_id: str, repository_id: str, snapshot_id: str = "baseline") -> Path:
        """Creates an on-disk snapshot of the current repository workspace state."""
        ws_path = self.get_repository_workspace_path(user_id, repository_id)
        snap_path = self.get_snapshot_path(user_id, repository_id, snapshot_id)
        if snap_path.exists():
            shutil.rmtree(snap_path, ignore_errors=True)
        snap_path.parent.mkdir(parents=True, exist_ok=True)
        if ws_path.exists():
            shutil.copytree(
                ws_path,
                snap_path,
                ignore=shutil.ignore_patterns(".git*", "__pycache__", "node_modules", ".venv", "dist", "coverage"),
            )
        return snap_path

