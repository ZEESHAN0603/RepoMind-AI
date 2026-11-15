import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.repository import Repository


class RepositoryFile(Base, TimestampMixin):
    """File metadata entity indexing the repository file hierarchy."""

    __tablename__ = "repository_files"

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
    path: Mapped[str] = mapped_column(String(1000), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    extension: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), default="file", nullable=False)  # file or folder
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    is_binary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    language: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Relationship
    repository: Mapped["Repository"] = relationship("Repository", back_populates="files")

    __table_args__ = (
        Index("ix_repository_files_repo_path", "repository_id", "path"),
    )

