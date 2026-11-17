import json
import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.code_symbol import CodeSymbol
    from app.models.repository import Repository
    from app.models.repository_file import RepositoryFile


class CodeChunk(Base, TimestampMixin):
    """
    Code chunk entity holding code text, source boundaries, and dense vector embeddings.
    Designed to work seamlessly on SQLite and PostgreSQL.
    """

    __tablename__ = "code_chunks"

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
    symbol_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("code_symbols.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_type: Mapped[str] = mapped_column(String(30), default="symbol", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    embedding_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-encoded List[float]
    embedding_model: Mapped[str] = mapped_column(String(100), default="nomic-embed-text", nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, default=768, nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="chunks")
    file: Mapped["RepositoryFile"] = relationship("RepositoryFile", back_populates="chunks")
    symbol: Mapped[Optional["CodeSymbol"]] = relationship("CodeSymbol", back_populates="chunks")

    @property
    def embedding_vector(self) -> List[float]:
        try:
            return json.loads(self.embedding_json)
        except Exception:
            return []

    @embedding_vector.setter
    def embedding_vector(self, vec: List[float]) -> None:
        self.embedding_json = json.dumps(vec)
        self.dimension = len(vec)

    __table_args__ = (
        Index("ix_code_chunks_repo_type", "repository_id", "chunk_type"),
        Index("ix_code_chunks_file_idx", "file_id", "chunk_index"),
    )
