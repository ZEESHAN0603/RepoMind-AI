import uuid
from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.repository import Repository


class RepositoryLanguage(Base, TimestampMixin):
    """Aggregate language statistics discovered in a repository."""

    __tablename__ = "repository_languages"

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
    language: Mapped[str] = mapped_column(String(100), nullable=False)
    byte_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    percentage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    color: Mapped[str] = mapped_column(String(30), default="#888888", nullable=False)

    # Relationship
    repository: Mapped["Repository"] = relationship("Repository", back_populates="languages")

