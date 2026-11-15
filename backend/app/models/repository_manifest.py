import uuid
from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.repository import Repository


class RepositoryDependencyManifest(Base, TimestampMixin):
    """Dependency manifest detected in a repository (e.g. package.json, requirements.txt)."""

    __tablename__ = "repository_manifests"

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
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    ecosystem: Mapped[str] = mapped_column(String(50), nullable=False)
    manifest_type: Mapped[str] = mapped_column(String(50), nullable=False)
    detected_frameworks: Mapped[str] = mapped_column(Text, default="[]", nullable=False)  # JSON array

    # Relationship
    repository: Mapped["Repository"] = relationship("Repository", back_populates="manifests")

