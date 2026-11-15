import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class GitHubConnection(Base, TimestampMixin):
    """Stores encrypted user GitHub OAuth tokens for private repository access."""

    __tablename__ = "github_connections"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    github_user_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    github_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    encrypted_access_token: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    scope: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="github_connection")

