import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.repository import Repository
    from app.models.repository_file import RepositoryFile


class CodeImportExport(Base, TimestampMixin):
    """Static import and export declarations discovered in source files."""

    __tablename__ = "code_imports_exports"

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
    statement_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "import" or "export"
    source_module: Mapped[str] = mapped_column(String(500), nullable=False)
    symbol_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    alias: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_relative: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="imports_exports")
    file: Mapped["RepositoryFile"] = relationship("RepositoryFile", back_populates="imports_exports")

    __table_args__ = (
        Index("ix_code_imports_exports_repo_type", "repository_id", "statement_type"),
        Index("ix_code_imports_exports_file_line", "file_id", "line_number"),
    )

