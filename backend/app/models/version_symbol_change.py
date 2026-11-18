import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.repository_update_run import RepositoryUpdateRun
    from app.models.version_file_change import VersionFileChange
    from app.models.version_impact_record import VersionImpactRecord


class VersionSymbolChange(Base, TimestampMixin):
    """Granular code symbol diff record for functions, methods, classes, and routes."""

    __tablename__ = "version_symbol_changes"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    update_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repository_update_runs.id", ondelete="CASCADE"),
        nullable=False
    )
    file_change_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("version_file_changes.id", ondelete="CASCADE"),
        nullable=True
    )
    symbol_name: Mapped[str] = mapped_column(String(255), nullable=False)
    symbol_type: Mapped[str] = mapped_column(String(50), nullable=False)  # function, method, class, interface, endpoint
    scope: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    change_type: Mapped[str] = mapped_column(String(20), nullable=False)  # added, modified, deleted, renamed
    old_signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)

    # Relationships
    update_run: Mapped["RepositoryUpdateRun"] = relationship("RepositoryUpdateRun", back_populates="symbol_changes")
    file_change: Mapped[Optional["VersionFileChange"]] = relationship("VersionFileChange", back_populates="symbol_changes")
    impact_records: Mapped[List["VersionImpactRecord"]] = relationship(
        "VersionImpactRecord",
        back_populates="source_change_symbol",
    )

    __table_args__ = (
        Index("ix_v_sym_changes_run_name", "update_run_id", "symbol_name"),
    )
