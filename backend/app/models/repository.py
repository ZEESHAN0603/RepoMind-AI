import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.api_route_endpoint import ApiRouteEndpoint
    from app.models.code_import_export import CodeImportExport
    from app.models.code_symbol import CodeSymbol
    from app.models.code_chunk import CodeChunk
    from app.models.chat_conversation import ChatConversation
    from app.models.ingestion_job import RepositoryIngestionJob
    from app.models.repository_branch import RepositoryBranch
    from app.models.repository_file import RepositoryFile
    from app.models.repository_language import RepositoryLanguage
    from app.models.repository_manifest import RepositoryDependencyManifest
    from app.models.user import User
    from app.models.architecture_snapshot import ArchitectureSnapshot
    from app.models.code_call import CodeCall
    from app.models.code_dependency import CodeDependency
    from app.models.dependency_snapshot import DependencySnapshot
    from app.models.execution_entry_point import ExecutionEntryPoint
    from app.models.execution_snapshot import ExecutionSnapshot
    from app.models.repository_version import RepositoryVersion
    from app.models.repository_update_run import RepositoryUpdateRun


class Repository(Base, TimestampMixin):
    """Repository database model for ingested GitHub or ZIP codebases."""

    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    owner_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    owner: Mapped[str] = mapped_column(String(100), nullable=False)
    repository_url: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), default="github_public", nullable=False)
    default_branch: Mapped[str] = mapped_column(String(100), default="main", nullable=False)
    current_commit_sha: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    visibility: Mapped[str] = mapped_column(String(20), default="public", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="connected", nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    folder_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_analyzed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="repositories")
    branches: Mapped[List["RepositoryBranch"]] = relationship(
        "RepositoryBranch",
        back_populates="repository",
        cascade="all, delete-orphan",
    )
    files: Mapped[List["RepositoryFile"]] = relationship(
        "RepositoryFile",
        back_populates="repository",
        cascade="all, delete-orphan",
    )
    languages: Mapped[List["RepositoryLanguage"]] = relationship(
        "RepositoryLanguage",
        back_populates="repository",
        cascade="all, delete-orphan",
    )
    manifests: Mapped[List["RepositoryDependencyManifest"]] = relationship(
        "RepositoryDependencyManifest",
        back_populates="repository",
        cascade="all, delete-orphan",
    )
    ingestion_jobs: Mapped[List["RepositoryIngestionJob"]] = relationship(
        "RepositoryIngestionJob",
        back_populates="repository",
        cascade="all, delete-orphan",
    )
    symbols: Mapped[List["CodeSymbol"]] = relationship(
        "CodeSymbol",
        back_populates="repository",
        cascade="all, delete-orphan",
    )
    imports_exports: Mapped[List["CodeImportExport"]] = relationship(
        "CodeImportExport",
        back_populates="repository",
        cascade="all, delete-orphan",
    )
    endpoints: Mapped[List["ApiRouteEndpoint"]] = relationship(
        "ApiRouteEndpoint",
        back_populates="repository",
        cascade="all, delete-orphan",
    )
    chunks: Mapped[List["CodeChunk"]] = relationship(
        "CodeChunk",
        back_populates="repository",
        cascade="all, delete-orphan",
    )
    conversations: Mapped[List["ChatConversation"]] = relationship(
        "ChatConversation",
        back_populates="repository",
        cascade="all, delete-orphan",
    )
    architecture_snapshot: Mapped[Optional["ArchitectureSnapshot"]] = relationship(
        "ArchitectureSnapshot",
        back_populates="repository",
        uselist=False,
        cascade="all, delete-orphan",
    )
    calls: Mapped[List["CodeCall"]] = relationship(
        "CodeCall",
        back_populates="repository",
        cascade="all, delete-orphan",
    )
    entry_points: Mapped[List["ExecutionEntryPoint"]] = relationship(
        "ExecutionEntryPoint",
        back_populates="repository",
        cascade="all, delete-orphan",
    )
    execution_snapshot: Mapped[Optional["ExecutionSnapshot"]] = relationship(
        "ExecutionSnapshot",
        back_populates="repository",
        uselist=False,
        cascade="all, delete-orphan",
    )
    dependency_snapshot: Mapped[Optional["DependencySnapshot"]] = relationship(
        "DependencySnapshot",
        back_populates="repository",
        uselist=False,
        cascade="all, delete-orphan",
    )
    dependencies: Mapped[List["CodeDependency"]] = relationship(
        "CodeDependency",
        back_populates="repository",
        cascade="all, delete-orphan",
    )
    versions: Mapped[List["RepositoryVersion"]] = relationship(
        "RepositoryVersion",
        back_populates="repository",
        cascade="all, delete-orphan",
    )
    update_runs: Mapped[List["RepositoryUpdateRun"]] = relationship(
        "RepositoryUpdateRun",
        back_populates="repository",
        cascade="all, delete-orphan",
    )

