import json
import math
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.code_chunk import CodeChunk
from app.models.repository_file import RepositoryFile


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Computes exact cosine similarity between two numeric vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0

    dot_product = 0.0
    norm_a = 0.0
    norm_b = 0.0

    for a, b in zip(vec_a, vec_b):
        dot_product += a * b
        norm_a += a * a
        norm_b += b * b

    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0

    return dot_product / (math.sqrt(norm_a) * math.sqrt(norm_b))


class ChunkRepository:
    """Data access repository for code chunks and vector search."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_chunks_batch(self, chunks: List[CodeChunk]) -> None:
        self.session.add_all(chunks)
        await self.session.flush()

    async def delete_chunks_by_repo(self, repo_id: str) -> None:
        await self.session.execute(
            delete(CodeChunk).where(CodeChunk.repository_id == repo_id)
        )
        await self.session.flush()

    async def count_chunks_by_repo(self, repo_id: str) -> int:
        query = select(func.count(CodeChunk.id)).where(CodeChunk.repository_id == repo_id)
        res = await self.session.execute(query)
        return res.scalar_one()

    async def list_chunks_by_repo(
        self,
        repo_id: str,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[CodeChunk]:
        query = (
            select(CodeChunk)
            .where(CodeChunk.repository_id == repo_id)
            .order_by(CodeChunk.chunk_index.asc())
            .offset(offset)
            .limit(limit)
        )
        res = await self.session.execute(query)
        return list(res.scalars().all())

    async def search_similar_chunks(
        self,
        repo_id: str,
        query_embedding: List[float],
        top_k: int = 8,
        min_similarity: float = 0.25,
    ) -> List[Tuple[CodeChunk, float]]:
        """
        Retrieves chunks strictly scoped to repo_id, ranks them by cosine similarity
        against query_embedding, and returns the top_k results above min_similarity.
        Guarantees complete repository isolation.
        """
        # Load all chunks for this repository with file relationship eagerly loaded
        query = (
            select(CodeChunk)
            .options(selectinload(CodeChunk.file))
            .where(CodeChunk.repository_id == repo_id)
        )
        res = await self.session.execute(query)
        chunks = list(res.scalars().all())

        scored_chunks: List[Tuple[CodeChunk, float]] = []
        for chunk in chunks:
            chunk_vec = chunk.embedding_vector
            if not chunk_vec:
                continue

            sim = cosine_similarity(query_embedding, chunk_vec)
            if sim >= min_similarity:
                scored_chunks.append((chunk, round(sim, 4)))

        # Sort descending by similarity
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        return scored_chunks[:top_k]
