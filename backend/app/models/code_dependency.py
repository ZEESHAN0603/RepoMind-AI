import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.repository import Repository
    from app.models.repository_file import RepositoryFile


class CodeDependency(Base, TimestampMixin):
    """
    Normalized relational dependency edge representing a direct, resolved, or external
    dependency relationship between source files, modules, or packages.
    """

    __tablename__ = "code_dependencies"

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
    source_file_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repository_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_file_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("repository_files.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_path: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    target_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, index=True)
    target_module: Mapped[str] = mapped_column(String(500), nullable=False)
    dependency_type: Mapped[str] = mapped_column(String(50), default="file", nullable=False)  # "file", "module", "package"
    category: Mapped[str] = mapped_column(String(20), default="internal", nullable=False)  # "internal", "external", "unresolved"
    statement_type: Mapped[str] = mapped_column(String(20), default="import", nullable=False)  # "import", "require", "export"
    imported_symbols_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)  # JSON array
    line_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_circular: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), default="verified", nullable=False)

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="dependencies")
    source_file: Mapped["RepositoryFile"] = relationship(
        "RepositoryFile",
        foreign_keys=[source_file_id],
        back_populates="outgoing_dependencies",
    )
    target_file: Mapped[Optional["RepositoryFile"]] = relationship(
        "RepositoryFile",
        foreign_keys=[target_file_id],
        back_populates="incoming_dependencies",
    )

    __table_args__ = (
        Index("ix_code_dependencies_repo_cat", "repository_id", "category"),
        Index("ix_code_dependencies_repo_circular", "repository_id", "is_circular"),
        Index("ix_code_dependencies_source_target", "source_path", "target_path"),
    )
