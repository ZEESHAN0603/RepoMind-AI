import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.repository import Repository
    from app.models.repository_version import RepositoryVersion
    from app.models.version_file_change import VersionFileChange
    from app.models.version_impact_record import VersionImpactRecord
    from app.models.version_symbol_change import VersionSymbolChange


class RepositoryUpdateRun(Base, TimestampMixin):
    """Historical update analysis comparing two repository versions or commits."""

    __tablename__ = "repository_update_runs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    repository_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    base_version_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("repository_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    target_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repository_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    base_commit_sha: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    target_commit_sha: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="completed", nullable=False)  # queued, analyzing, completed, failed
    total_files_changed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_symbols_changed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_additions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_deletions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    impact_summary_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    ai_summary_markdown: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_summary_status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)  # pending, generating, completed, failed
    analyzed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="update_runs")
    base_version: Mapped[Optional["RepositoryVersion"]] = relationship(
        "RepositoryVersion",
        foreign_keys=[base_version_id],
        back_populates="base_update_runs",
    )
    target_version: Mapped["RepositoryVersion"] = relationship(
        "RepositoryVersion",
        foreign_keys=[target_version_id],
        back_populates="target_update_runs",
    )
    file_changes: Mapped[List["VersionFileChange"]] = relationship(
        "VersionFileChange",
        back_populates="update_run",
        cascade="all, delete-orphan",
    )
    symbol_changes: Mapped[List["VersionSymbolChange"]] = relationship(
        "VersionSymbolChange",
        back_populates="update_run",
        cascade="all, delete-orphan",
    )
    impact_records: Mapped[List["VersionImpactRecord"]] = relationship(
        "VersionImpactRecord",
        back_populates="update_run",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_repository_update_runs_repo_time", "repository_id", "created_at"),
    )
