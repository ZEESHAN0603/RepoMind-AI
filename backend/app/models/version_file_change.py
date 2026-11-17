import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.repository_update_run import RepositoryUpdateRun
    from app.models.version_symbol_change import VersionSymbolChange


class VersionFileChange(Base, TimestampMixin):
    """File-level diff record for a repository update analysis run."""

    __tablename__ = "version_file_changes"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    update_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repository_update_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    path: Mapped[str] = mapped_column(String(1000), nullable=False)
    old_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    change_type: Mapped[str] = mapped_column(String(20), default="modified", nullable=False)  # added, modified, deleted, renamed
    file_category: Mapped[str] = mapped_column(String(30), default="source", nullable=False)  # source, config, manifest, documentation, other
    additions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deletions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    old_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    new_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    old_content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    new_content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    diff_patch: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    update_run: Mapped["RepositoryUpdateRun"] = relationship("RepositoryUpdateRun", back_populates="file_changes")
    symbol_changes: Mapped[List["VersionSymbolChange"]] = relationship(
        "VersionSymbolChange",
        back_populates="file_change",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_v_file_changes_run_type", "update_run_id", "change_type"),
        Index("ix_v_file_changes_run_path", "update_run_id", "path"),
    )
