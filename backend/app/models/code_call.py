import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.repository import Repository
    from app.models.repository_file import RepositoryFile
    from app.models.code_symbol import CodeSymbol


class CodeCall(Base, TimestampMixin):
    """Represents a discovered function or method invocation relationship."""

    __tablename__ = "code_calls"

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
    caller_symbol_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("code_symbols.id", ondelete="SET NULL"),
        nullable=True
    )
    callee_symbol_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("code_symbols.id", ondelete="SET NULL"),
        nullable=True
    )
    caller_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    callee_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    caller_file_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("repository_files.id", ondelete="CASCADE"),
        nullable=True
    )
    callee_file_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("repository_files.id", ondelete="SET NULL"),
        nullable=True
    )
    caller_file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    callee_file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    call_type: Mapped[str] = mapped_column(String(50), nullable=False, default="function_call")
    resolution_status: Mapped[str] = mapped_column(String(50), nullable=False, default="unresolved")
    confidence: Mapped[str] = mapped_column(String(20), nullable=False, default="verified")
    arguments_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    evidence: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="calls")

    __table_args__ = (
        Index("ix_code_calls_repo_caller", "repository_id", "caller_symbol_id"),
        Index("ix_code_calls_repo_callee", "repository_id", "callee_symbol_id"),
        Index("ix_code_calls_repo_status", "repository_id", "resolution_status"),
    )
