import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.repository import Repository


class ArchitectureSnapshot(Base, TimestampMixin):
    """Stores precomputed architecture graph snapshot for rapid retrieval and view slicing."""

    __tablename__ = "architecture_snapshots"

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
    graph_data_json: Mapped[str] = mapped_column(Text, nullable=False)
    node_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    edge_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="architecture_snapshot")

    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            name="uq_architecture_snapshots_repository_id",
        ),
        Index("ix_architecture_snapshots_repo", "repository_id"),
    )
