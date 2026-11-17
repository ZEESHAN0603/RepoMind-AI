import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.ai.provider_manager import ProviderManager
from app.ai.schemas import EmbeddingResult, GenerationResult, TokenUsage
from app.models.code_chunk import CodeChunk
from app.models.code_symbol import CodeSymbol
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.models.user import User
from app.services.chat_service import ChatService
from app.services.rag_service import RAGService


@pytest.mark.asyncio
async def test_create_and_list_conversations(db_session):
    """Verifies conversation lifecycle and user association."""
    user = User(email="chat_user@repomind.dev", password_hash="pw", full_name="Chat User")
    db_session.add(user)
    await db_session.flush()

    repo = Repository(id="repo-chat-1", owner_id=user.id, name="ChatRepo", owner="user", repository_url="https://github.com/u/c")
    db_session.add(repo)
    await db_session.commit()

    service = ChatService()
    conv = await service.create_conversation(db_session, "repo-chat-1", user.id, title="Auth Investigation")
    assert conv.id is not None
    assert conv.title == "Auth Investigation"

    convs = await service.list_conversations(db_session, "repo-chat-1", user.id)
    assert len(convs) == 1
    assert convs[0].id == conv.id


@pytest.mark.asyncio
async def test_send_message_grounded_answer_with_citations(db_session):
    """Verifies that sending a message generates grounded answers with accurate citations."""
    user = User(email="grounding_user@repomind.dev", password_hash="pw", full_name="Grounder")
    db_session.add(user)
    await db_session.flush()

    repo = Repository(id="repo-ground", owner_id=user.id, name="GroundRepo", owner="user", repository_url="https://github.com/u/g")
    db_session.add(repo)
    await db_session.flush()

    file_ent = RepositoryFile(id="f-ground", repository_id="repo-ground", path="backend/app/main.py", name="main.py", file_type="file")
    db_session.add(file_ent)
    await db_session.flush()

    chunk_vec = [1.0, 0.0]
    chunk = CodeChunk(
        id="c-ground-1",
        repository_id="repo-ground",
        file_id="f-ground",
        chunk_index=0,
        content="app = FastAPI(title='RepoMind', version='0.1.0')",
        start_line=42,
        end_line=50,
        token_count=10,
        embedding_json=json.dumps(chunk_vec),
        dimension=2,
    )
    db_session.add(chunk)
    await db_session.commit()

    # Mock ProviderManager
    mock_pm = MagicMock(spec=ProviderManager)
    mock_pm.generate_embedding = AsyncMock(
        return_value=EmbeddingResult(embedding=chunk_vec, provider="ollama", model="nomic-embed-text", dimension=2)
    )
    mock_pm.generate_chat = AsyncMock(
        return_value=GenerationResult(
            content="FastAPI is initialized in backend/app/main.py on line 42 with title RepoMind.",
            provider="ollama",
            model="qwen3.5:4b",
            usage=TokenUsage(prompt_tokens=50, completion_tokens=25, total_tokens=75),
        )
    )

    rag = RAGService(provider_manager=mock_pm)
    chat_svc = ChatService(rag_service=rag, provider_manager=mock_pm)

    assistant_msg = await chat_svc.send_message(
        session=db_session,
        repository_id="repo-ground",
        conversation_id="conv-test-1",
        user_id=user.id,
        prompt="Where is FastAPI initialized?",
    )

    assert assistant_msg.role == "assistant"
    assert assistant_msg.confidence == "verified"
    assert "backend/app/main.py" in assistant_msg.content
    assert assistant_msg.provider == "ollama"

    # Verify citations strictly match chunk metadata
    citations = assistant_msg.citations
    assert len(citations) == 1
    assert citations[0]["filePath"] == "backend/app/main.py"
    assert citations[0]["startLine"] == 42
    assert citations[0]["endLine"] == 50


@pytest.mark.asyncio
async def test_send_message_insufficient_evidence_unknown(db_session):
    """Verifies that missing evidence classifies response as unknown without hallucinating citations."""
    user = User(email="unknown_test@repomind.dev", password_hash="pw", full_name="Unknown Tester")
    db_session.add(user)
    await db_session.flush()

    repo = Repository(id="repo-empty", owner_id=user.id, name="EmptyRepo", owner="user", repository_url="https://github.com/u/e")
    db_session.add(repo)
    await db_session.commit()

    mock_pm = MagicMock(spec=ProviderManager)
    mock_pm.generate_embedding = AsyncMock(
        return_value=EmbeddingResult(embedding=[0.0, 0.0], provider="ollama", model="nomic-embed-text", dimension=2)
    )
    mock_pm.generate_chat = AsyncMock(
        return_value=GenerationResult(
            content="The repository does not contain this information. Database credentials are unknown.",
            provider="ollama",
            model="qwen3.5:4b",
        )
    )

    rag = RAGService(provider_manager=mock_pm)
    chat_svc = ChatService(rag_service=rag, provider_manager=mock_pm)

    assistant_msg = await chat_svc.send_message(
        session=db_session,
        repository_id="repo-empty",
        conversation_id="conv-empty-1",
        user_id=user.id,
        prompt="What is the production root password?",
    )

    assert assistant_msg.confidence == "unknown"
    assert len(assistant_msg.citations) == 0


@pytest.mark.asyncio
async def test_chat_suggestions_dynamic(db_session):
    """Verifies dynamic suggested questions are generated from repository static analysis symbols."""
    user = User(email="sugg_user@repomind.dev", password_hash="pw", full_name="Sugg User")
    db_session.add(user)
    await db_session.flush()

    repo = Repository(id="repo-sugg", owner_id=user.id, name="SuggRepo", owner="user", repository_url="https://github.com/u/s")
    db_session.add(repo)
    await db_session.flush()

    file_ent = RepositoryFile(id="f-sugg", repository_id="repo-sugg", path="app/main.py", name="main.py", file_type="file")
    db_session.add(file_ent)
    await db_session.flush()

    sym = CodeSymbol(
        repository_id="repo-sugg",
        file_id="f-sugg",
        name="authenticate_client",
        symbol_type="function",
        start_line=1,
        end_line=10,
    )
    db_session.add(sym)
    await db_session.commit()

    chat_svc = ChatService()
    suggestions = await chat_svc.get_suggested_questions(db_session, "repo-sugg", user.id)

    assert len(suggestions) >= 2
    assert any("authenticate_client" in s for s in suggestions)
