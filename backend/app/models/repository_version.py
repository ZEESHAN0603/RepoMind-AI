import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, utc_now

if TYPE_CHECKING:
    from app.models.repository import Repository
    from app.models.repository_update_run import RepositoryUpdateRun


class RepositoryVersion(Base, TimestampMixin):
    """Tracks historical commits or uploaded snapshots for a repository."""

    __tablename__ = "repository_versions"

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
    version_tag: Mapped[str] = mapped_column(String(100), nullable=False)
    commit_sha: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    commit_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    author_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    author_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    commit_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), default="github_commit", nullable=False)

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="versions")
    target_update_runs: Mapped[List["RepositoryUpdateRun"]] = relationship(
        "RepositoryUpdateRun",
        foreign_keys="RepositoryUpdateRun.target_version_id",
        back_populates="target_version",
        cascade="all, delete-orphan",
    )
    base_update_runs: Mapped[List["RepositoryUpdateRun"]] = relationship(
        "RepositoryUpdateRun",
        foreign_keys="RepositoryUpdateRun.base_version_id",
        back_populates="base_version",
    )

    __table_args__ = (
        Index("ix_repository_versions_repo_time", "repository_id", "created_at"),
    )
