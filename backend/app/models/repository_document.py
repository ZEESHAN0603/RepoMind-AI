import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, utc_now

if TYPE_CHECKING:
    from app.models.repository import Repository


class RepositoryDocument(Base, TimestampMixin):
    """Stores generated, structured technical documentation for a repository."""

    __tablename__ = "repository_documents"

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
    doc_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # readme, architecture, module, api, execution_flow, dependencies, update_changelog, onboarding
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="draft",
        index=True,
    )  # draft, approved, stale, generating, failed
    confidence: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="verified",
    )  # verified, inferred
    source_evidence_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="{}",
    )  # JSON string of source citations, lines, symbol IDs
    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    last_generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    approved_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="documents")
    versions: Mapped[List["RepositoryDocumentVersion"]] = relationship(
        "RepositoryDocumentVersion",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="desc(RepositoryDocumentVersion.version_number)",
    )

    __table_args__ = (
        Index("ix_repository_documents_repo_type", "repository_id", "doc_type", unique=True),
    )


class RepositoryDocumentVersion(Base, TimestampMixin):
    """Historical version snapshot for a repository document."""

    __tablename__ = "repository_document_versions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repository_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    repository_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    change_summary: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    created_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    document: Mapped["RepositoryDocument"] = relationship("RepositoryDocument", back_populates="versions")

    __table_args__ = (
        Index("ix_repository_document_versions_doc_id", "document_id"),
        Index("ix_repository_document_versions_repo_id", "repository_id"),
        Index("ix_doc_versions_doc_num", "document_id", "version_number", unique=True),
        Index("ix_doc_versions_repo_time", "repository_id", "created_at"),
    )
