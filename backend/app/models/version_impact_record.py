import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.repository_update_run import RepositoryUpdateRun
    from app.models.version_symbol_change import VersionSymbolChange


class VersionImpactRecord(Base, TimestampMixin):
    """Blast radius impact record indicating affected caller, dependent, or endpoint."""

    __tablename__ = "version_impact_records"

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
    affected_type: Mapped[str] = mapped_column(String(50), nullable=False)  # symbol, file, endpoint, architecture_component
    affected_identifier: Mapped[str] = mapped_column(String(500), nullable=False)
    affected_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    impact_level: Mapped[str] = mapped_column(String(30), nullable=False)  # directly_changed, directly_affected, indirectly_affected, potentially_affected, unknown
    evidence_reason: Mapped[str] = mapped_column(Text, nullable=False)
    source_change_symbol_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("version_symbol_changes.id", ondelete="SET NULL"),
        nullable=True,
    )
    depth: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    update_run: Mapped["RepositoryUpdateRun"] = relationship("RepositoryUpdateRun", back_populates="impact_records")
    source_change_symbol: Mapped[Optional["VersionSymbolChange"]] = relationship(
        "VersionSymbolChange",
        back_populates="impact_records",
    )

    __table_args__ = (
        Index("ix_v_impact_run_level", "update_run_id", "impact_level"),
        Index("ix_v_impact_run_ident", "update_run_id", "affected_identifier"),
    )
