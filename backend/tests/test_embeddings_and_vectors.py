import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.ai.base import BaseLLMProvider
from app.ai.provider_manager import ProviderManager
from app.ai.schemas import EmbeddingResult
from app.models.code_chunk import CodeChunk
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.models.user import User
from app.repositories.chunk_repository import ChunkRepository, cosine_similarity
from app.services.chunking_service import ChunkingService, CodeChunkData
from app.services.embedding_service import EmbeddingService


def test_cosine_similarity_math():
    """Verifies cosine similarity calculations across vectors."""
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]
    v4 = [-1.0, 0.0, 0.0]

    assert pytest.approx(cosine_similarity(v1, v2)) == 1.0
    assert pytest.approx(cosine_similarity(v1, v3)) == 0.0
    assert pytest.approx(cosine_similarity(v1, v4)) == -1.0
    assert cosine_similarity([], v1) == 0.0
    assert cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0


@pytest.mark.asyncio
async def test_chunk_repository_vector_search_and_isolation(db_session):
    """Verifies repository boundary isolation during vector similarity search."""
    # Create test user and two distinct repositories
    user = User(email="vector_test@repomind.dev", password_hash="pw", full_name="Vector Tester")
    db_session.add(user)
    await db_session.flush()

    repo_a = Repository(id="repo-a", owner_id=user.id, name="RepoA", owner="tester", repository_url="https://github.com/tester/a")
    repo_b = Repository(id="repo-b", owner_id=user.id, name="RepoB", owner="tester", repository_url="https://github.com/tester/b")
    db_session.add_all([repo_a, repo_b])
    await db_session.flush()

    file_a = RepositoryFile(id="file-a", repository_id="repo-a", path="main.py", name="main.py", file_type="file")
    file_b = RepositoryFile(id="file-b", repository_id="repo-b", path="main.py", name="main.py", file_type="file")
    db_session.add_all([file_a, file_b])
    await db_session.flush()

    target_vec = [1.0, 0.5, 0.0]
    unrelated_vec = [0.0, 0.0, 1.0]

    chunk_repo = ChunkRepository(db_session)
    # Add matching chunk to Repo A
    chunk_a = CodeChunk(
        id="chunk-a1",
        repository_id="repo-a",
        file_id="file-a",
        chunk_index=0,
        content="def calculate(): pass",
        start_line=1,
        end_line=5,
        token_count=10,
        embedding_json=json.dumps(target_vec),
        dimension=3,
    )
    # Add identical vector to Repo B (must NOT leak into Repo A queries)
    chunk_b = CodeChunk(
        id="chunk-b1",
        repository_id="repo-b",
        file_id="file-b",
        chunk_index=0,
        content="secret data in repo B",
        start_line=1,
        end_line=5,
        token_count=10,
        embedding_json=json.dumps(target_vec),
        dimension=3,
    )
    await chunk_repo.save_chunks_batch([chunk_a, chunk_b])
    await db_session.commit()

    # Query strictly for Repo A
    results = await chunk_repo.search_similar_chunks(
        repo_id="repo-a",
        query_embedding=target_vec,
        top_k=5,
        min_similarity=0.5,
    )

    assert len(results) == 1
    found_chunk, score = results[0]
    assert found_chunk.id == "chunk-a1"
    assert found_chunk.repository_id == "repo-a"
    assert score >= 0.99
    # Ensure Repo B chunk was never returned
    assert not any(c.id == "chunk-b1" for c, _ in results)


@pytest.mark.asyncio
async def test_embedding_service_indexing_flow(db_session):
    """Verifies embedding service orchestrates chunking, vector generation, and persistence."""
    user = User(email="embed_svc@repomind.dev", password_hash="pw", full_name="Embedder")
    db_session.add(user)
    await db_session.flush()

    repo = Repository(id="repo-embed", owner_id=user.id, name="RepoEmbed", owner="tester", repository_url="https://github.com/tester/embed")
    db_session.add(repo)
    await db_session.flush()

    file_ent = RepositoryFile(id="f1", repository_id="repo-embed", path="auth.py", name="auth.py", file_type="file")
    db_session.add(file_ent)
    await db_session.flush()

    # Mock chunking service
    mock_chunker = MagicMock(spec=ChunkingService)
    mock_chunker.generate_chunks_for_repository = AsyncMock(
        return_value=[
            CodeChunkData(
                chunk_index=0,
                file_id="f1",
                file_path="auth.py",
                symbol_id=None,
                symbol_name="login",
                symbol_type="function",
                scope=None,
                chunk_type="symbol",
                content="def login(): pass",
                start_line=1,
                end_line=10,
                token_count=15,
                language="Python",
            )
        ]
    )

    # Mock provider manager
    mock_pm = MagicMock(spec=ProviderManager)
    mock_pm.generate_embeddings_batch = AsyncMock(
        return_value=[
            EmbeddingResult(
                embedding=[0.1] * 768,
                provider="ollama",
                model="nomic-embed-text",
                dimension=768,
            )
        ]
    )

    service = EmbeddingService(provider_manager=mock_pm, chunking_service=mock_chunker)
    res = await service.index_repository_embeddings(db_session, "repo-embed", user.id)

    assert res["chunks_indexed"] == 1
    assert res["dimension"] == 768
    assert res["model"] == "nomic-embed-text"

    # Verify persisted in database
    chunk_repo = ChunkRepository(db_session)
    count = await chunk_repo.count_chunks_by_repo("repo-embed")
    assert count == 1
