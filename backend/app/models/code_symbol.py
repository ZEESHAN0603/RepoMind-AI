import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.repository import Repository
    from app.models.repository_file import RepositoryFile


class CodeSymbol(Base, TimestampMixin):
    """Extracted code symbol representing functions, methods, classes, interfaces, or types."""

    __tablename__ = "code_symbols"

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
    file_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repository_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    symbol_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    scope: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    signature: Mapped[str] = mapped_column(Text, nullable=False, default="")
    docstring: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    start_column: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    end_column: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_async: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_exported: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    visibility: Mapped[str] = mapped_column(String(20), default="public", nullable=False)
    parameters: Mapped[str] = mapped_column(Text, default="[]", nullable=False)  # JSON
    return_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    decorators: Mapped[str] = mapped_column(Text, default="[]", nullable=False)  # JSON
    bases_or_interfaces: Mapped[str] = mapped_column(Text, default="[]", nullable=False)  # JSON
    confidence: Mapped[str] = mapped_column(String(20), default="verified", nullable=False)

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="symbols")
    file: Mapped["RepositoryFile"] = relationship("RepositoryFile", back_populates="symbols")

    __table_args__ = (
        Index("ix_code_symbols_repo_type", "repository_id", "symbol_type"),
        Index("ix_code_symbols_repo_name", "repository_id", "name"),
        Index("ix_code_symbols_file_lines", "file_id", "start_line"),
    )

