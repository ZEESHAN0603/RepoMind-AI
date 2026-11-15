import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class Repository(Base, TimestampMixin):
    """Repository database model for ingested GitHub or ZIP codebases."""

    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    owner_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    owner: Mapped[str] = mapped_column(String(100), nullable=False)
    repository_url: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), default="github_public", nullable=False)
    default_branch: Mapped[str] = mapped_column(String(100), default="main", nullable=False)
    current_commit_sha: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    visibility: Mapped[str] = mapped_column(String(20), default="public", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="connected", nullable=False)
    last_analyzed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="repositories")

