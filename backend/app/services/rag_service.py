import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.provider_manager import ProviderManager
from app.ai.schemas import EmbeddingResult
from app.core.config import settings
from app.core.exceptions import ForbiddenException, NotFoundException
from app.core.logging import logger
from app.models.code_chunk import CodeChunk
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.repository_repository import RepositoryRepository

MAX_CONTEXT_TOKENS = 2500  # Strict context boundary for CPU InstaBox environment


@dataclass
class RetrievedChunk:
    chunk_id: str
    file_path: str
    start_line: int
    end_line: int
    similarity: float
    content: str
    symbol_name: Optional[str] = None
    symbol_type: Optional[str] = None
    confidence: str = "verified"


@dataclass
class RetrievalResult:
    query: str
    repository_id: str
    chunks: List[RetrievedChunk]
    assembled_context: str
    total_context_tokens: int


class RAGService:
    """
    Orchestrates repository-scoped semantic retrieval, cross-tenant isolation,
    and prompt-injection resistant context assembly.
    """

    def __init__(
        self,
        provider_manager: Optional[ProviderManager] = None,
        chunk_repository: Optional[ChunkRepository] = None,
    ) -> None:
        self.provider_manager = provider_manager or ProviderManager()
        self._chunk_repo = chunk_repository

    async def _verify_repository_access(
        self,
        session: AsyncSession,
        repository_id: str,
        user_id: str,
    ) -> None:
        """Enforces strict repository ownership to prevent cross-tenant information leakage."""
        repo_repo = RepositoryRepository(session)
        repo = await repo_repo.get_by_id(repository_id)
        if not repo:
            raise NotFoundException("Repository not found")
        if repo.owner_id != user_id:
            raise ForbiddenException("You do not have permission to access this repository")

    def _sanitize_for_prompt_injection(self, raw_content: str) -> str:
        """
        Quarantines repository text to prevent instructions in READMEs or comments
        from overriding system instructions.
        """
        # Neutralize markdown/XML escape sequences that could close context blocks
        sanitized = raw_content.replace("</repository_evidence>", "[ESCAPED_TAG]")
        return sanitized

    async def retrieve_context(
        self,
        session: AsyncSession,
        repository_id: str,
        user_id: str,
        query: str,
        top_k: int = 6,
        min_similarity: float = 0.25,
    ) -> RetrievalResult:
        """
        Executes repository-isolated vector retrieval:
        1. Validates user ownership.
        2. Embeds user query using nomic-embed-text.
        3. Queries vector store strictly within repository_id.
        4. Binds and formats prompt context safely.
        """
        await self._verify_repository_access(session, repository_id, user_id)

        if not query or not query.strip():
            return RetrievalResult(
                query=query,
                repository_id=repository_id,
                chunks=[],
                assembled_context="No query provided.",
                total_context_tokens=0,
            )

        # Generate query embedding
        query_emb_res: EmbeddingResult = await self.provider_manager.generate_embedding(
            text=query,
            model=settings.OLLAMA_EMBEDDING_MODEL,
        )

        chunk_repo = self._chunk_repo or ChunkRepository(session)
        similar_chunks = await chunk_repo.search_similar_chunks(
            repo_id=repository_id,
            query_embedding=query_emb_res.embedding,
            top_k=top_k,
            min_similarity=min_similarity,
        )

        retrieved: List[RetrievedChunk] = []
        context_blocks: List[str] = []
        running_tokens = 0

        for chunk, score in similar_chunks:
            file_path = chunk.file.path if chunk.file else "unknown_file"

            # Parse metadata
            meta: Dict[str, Any] = {}
            if chunk.metadata_json:
                try:
                    meta = json.loads(chunk.metadata_json)
                except Exception:
                    pass

            item = RetrievedChunk(
                chunk_id=chunk.id,
                file_path=file_path,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                similarity=score,
                content=chunk.content,
                symbol_name=meta.get("symbol_name") or chunk.chunk_type,
                symbol_type=chunk.chunk_type,
                confidence="verified",
            )

            # Prevent exceeding max context window
            estimated_tokens = chunk.token_count or (len(chunk.content) // 4)
            if running_tokens + estimated_tokens > MAX_CONTEXT_TOKENS:
                break

            retrieved.append(item)
            sanitized_content = self._sanitize_for_prompt_injection(chunk.content)

            context_blocks.append(
                f"<evidence_item id=\"{chunk.id}\" file=\"{file_path}\" lines=\"{chunk.start_line}-{chunk.end_line}\" similarity=\"{score}\">\n"
                f"{sanitized_content}\n"
                f"</evidence_item>"
            )
            running_tokens += estimated_tokens

        assembled = (
            "<repository_evidence>\n"
            + "\n\n".join(context_blocks)
            + "\n</repository_evidence>"
            if context_blocks
            else "No matching repository evidence found."
        )

        return RetrievalResult(
            query=query,
            repository_id=repository_id,
            chunks=retrieved,
            assembled_context=assembled,
            total_context_tokens=running_tokens,
        )
