import uuid
from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.repository import Repository
    from app.models.repository_file import RepositoryFile


class ApiRouteEndpoint(Base, TimestampMixin):
    """Static API route endpoint declarations discovered across backend files."""

    __tablename__ = "api_route_endpoints"

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
    http_method: Mapped[str] = mapped_column(String(20), nullable=False)  # GET, POST, PUT, DELETE, etc.
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    handler_name: Mapped[str] = mapped_column(String(255), nullable=False)
    framework: Mapped[str] = mapped_column(String(50), nullable=False)  # FastAPI, Flask, Express, etc.
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), default="verified", nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="endpoints")
    file: Mapped["RepositoryFile"] = relationship("RepositoryFile", back_populates="endpoints")

    __table_args__ = (
        Index("ix_api_route_endpoints_repo_method", "repository_id", "http_method"),
        Index("ix_api_route_endpoints_repo_framework", "repository_id", "framework"),
    )

