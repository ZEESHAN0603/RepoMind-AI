import json
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.provider_manager import ProviderManager
from app.ai.schemas import EmbeddingResult
from app.core.config import settings
from app.core.exceptions import NotFoundException
from app.core.logging import logger
from app.models.code_chunk import CodeChunk
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.repository_repository import RepositoryRepository
from app.services.chunking_service import ChunkingService, CodeChunkData

EMBEDDING_BATCH_SIZE = 16


class EmbeddingService:
    """
    Orchestrates repository code chunking and vector embedding indexing
    using Ollama's nomic-embed-text model.
    """

    def __init__(
        self,
        provider_manager: Optional[ProviderManager] = None,
        chunking_service: Optional[ChunkingService] = None,
    ) -> None:
        self.provider_manager = provider_manager or ProviderManager()
        self.chunking_service = chunking_service or ChunkingService()

    async def index_repository_embeddings(
        self,
        session: AsyncSession,
        repository_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Extracts code chunks and computes dense embeddings, saving them to the database.
        Replaces previous embeddings cleanly on reindexing.
        """
        repo_repo = RepositoryRepository(session)
        chunk_repo = ChunkRepository(session)

        repo = await repo_repo.get_by_id(repository_id)
        if not repo:
            raise NotFoundException("Repository not found")

        # 1. Generate code chunks
        raw_chunks: List[CodeChunkData] = await self.chunking_service.generate_chunks_for_repository(
            session=session,
            repository_id=repository_id,
            user_id=user_id,
        )

        if not raw_chunks:
            logger.info("No code chunks generated for repository %s.", repository_id)
            await chunk_repo.delete_chunks_by_repo(repository_id)
            await session.commit()
            return {
                "repository_id": repository_id,
                "chunks_indexed": 0,
                "dimension": 0,
                "model": settings.OLLAMA_EMBEDDING_MODEL,
            }

        # 2. Compute embeddings in batches
        chunk_entities: List[CodeChunk] = []
        batch_texts: List[str] = []
        batch_chunks: List[CodeChunkData] = []
        target_model = settings.OLLAMA_EMBEDDING_MODEL

        for chunk_data in raw_chunks:
            batch_texts.append(chunk_data.content)
            batch_chunks.append(chunk_data)

            if len(batch_texts) >= EMBEDDING_BATCH_SIZE:
                embeddings = await self.provider_manager.generate_embeddings_batch(
                    texts=batch_texts,
                    model=target_model,
                )
                for c_data, emb in zip(batch_chunks, embeddings):
                    chunk_entities.append(
                        CodeChunk(
                            repository_id=repository_id,
                            file_id=c_data.file_id,
                            symbol_id=c_data.symbol_id,
                            chunk_index=c_data.chunk_index,
                            chunk_type=c_data.chunk_type,
                            content=c_data.content,
                            start_line=c_data.start_line,
                            end_line=c_data.end_line,
                            token_count=c_data.token_count,
                            embedding_json=json.dumps(emb.embedding),
                            embedding_model=emb.model,
                            dimension=emb.dimension,
                            metadata_json=json.dumps(c_data.metadata),
                        )
                    )
                batch_texts = []
                batch_chunks = []

        # Process remainder
        if batch_texts:
            embeddings = await self.provider_manager.generate_embeddings_batch(
                texts=batch_texts,
                model=target_model,
            )
            for c_data, emb in zip(batch_chunks, embeddings):
                chunk_entities.append(
                    CodeChunk(
                        repository_id=repository_id,
                        file_id=c_data.file_id,
                        symbol_id=c_data.symbol_id,
                        chunk_index=c_data.chunk_index,
                        chunk_type=c_data.chunk_type,
                        content=c_data.content,
                        start_line=c_data.start_line,
                        end_line=c_data.end_line,
                        token_count=c_data.token_count,
                        embedding_json=json.dumps(emb.embedding),
                        embedding_model=emb.model,
                        dimension=emb.dimension,
                        metadata_json=json.dumps(c_data.metadata),
                    )
                )

        # 3. Atomically replace previous chunks
        await chunk_repo.delete_chunks_by_repo(repository_id)
        if chunk_entities:
            await chunk_repo.save_chunks_batch(chunk_entities)

        await session.commit()
        sample_dim = chunk_entities[0].dimension if chunk_entities else 768

        logger.info(
            "Successfully indexed %d chunks for repo %s (dim=%d, model=%s)",
            len(chunk_entities),
            repository_id,
            sample_dim,
            target_model,
        )

        return {
            "repository_id": repository_id,
            "chunks_indexed": len(chunk_entities),
            "dimension": sample_dim,
            "model": target_model,
        }
