import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.repository import Repository
    from app.models.code_symbol import CodeSymbol


class ExecutionEntryPoint(Base, TimestampMixin):
    """Represents a discovered execution entry point for repository applications."""

    __tablename__ = "execution_entry_points"

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
    symbol_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("code_symbols.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    file_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("repository_files.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    symbol_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    route_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    http_method: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False, default="verified")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="entry_points")

    __table_args__ = (
        Index("ix_execution_entry_points_repo_type", "repository_id", "entry_type"),
    )
