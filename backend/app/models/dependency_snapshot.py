import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, utc_now

if TYPE_CHECKING:
    from app.models.repository import Repository


class DependencySnapshot(Base, TimestampMixin):
    """
    Cached, pre-synthesized dependency graph analysis snapshot for a repository.
    Enables instant dashboard loads and sub-millisecond query responses.
    """

    __tablename__ = "dependency_snapshots"

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
    total_modules: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_imports: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    internal_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    external_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    circular_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unresolved_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    __table_args__ = (
        UniqueConstraint("repository_id"),
    )

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="dependency_snapshot")
