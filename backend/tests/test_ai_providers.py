import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from app.ai.base import BaseLLMProvider
from app.ai.exceptions import (
    AIProviderError,
    ModelNotFoundError,
    ProviderUnavailableError,
    QuotaExceededError,
)
from app.ai.gemini_provider import GeminiProvider
from app.ai.ollama_provider import OllamaProvider
from app.ai.provider_manager import ProviderManager
from app.ai.schemas import ChatMessage, GenerationResult, TokenUsage
from app.core.config import settings


@pytest.mark.asyncio
async def test_ollama_provider_generate_chat_success():
    """Verifies Ollama provider parses standard 200 chat response."""
    provider = OllamaProvider(base_url="http://mock-ollama:11434")

    mock_response = MagicMock(status_code=200)
    mock_response.json.return_value = {
        "message": {"role": "assistant", "content": "This is a function that parses code."},
        "prompt_eval_count": 42,
        "eval_count": 18,
        "done_reason": "stop",
    }

    with patch.object(provider._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        messages = [ChatMessage(role="user", content="Explain parse_source()")]
        res = await provider.generate_chat(messages, model="qwen3.5:4b")

        assert res.content == "This is a function that parses code."
        assert res.provider == "ollama"
        assert res.model == "qwen3.5:4b"
        assert res.usage.prompt_tokens == 42
        assert res.usage.completion_tokens == 18
        assert res.usage.total_tokens == 60

    await provider.close()


@pytest.mark.asyncio
async def test_ollama_provider_model_not_found():
    """Verifies 404 response translates to ModelNotFoundError."""
    provider = OllamaProvider(base_url="http://mock-ollama:11434")

    mock_response = MagicMock(status_code=404)
    with patch.object(provider._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        with pytest.raises(ModelNotFoundError) as exc:
            await provider.generate_chat([ChatMessage(role="user", content="hi")], model="nonexistent:model")
        assert "not found" in str(exc.value)

    await provider.close()


@pytest.mark.asyncio
async def test_ollama_provider_connection_unavailable():
    """Verifies network connection failure translates to ProviderUnavailableError."""
    provider = OllamaProvider(base_url="http://mock-ollama:11434")

    with patch.object(provider._client, "post", side_effect=httpx.ConnectError("Connection refused")):
        with pytest.raises(ProviderUnavailableError) as exc:
            await provider.generate_chat([ChatMessage(role="user", content="hi")])
        assert "unavailable" in str(exc.value).lower()

    await provider.close()


@pytest.mark.asyncio
async def test_ollama_provider_embeddings_success():
    """Verifies Ollama embedding retrieval and dimension validation."""
    provider = OllamaProvider(base_url="http://mock-ollama:11434")

    mock_response = MagicMock(status_code=200)
    mock_vector = [0.123, -0.456, 0.789] + [0.0] * 765  # 768 dimensions
    mock_response.json.return_value = {"embedding": mock_vector}

    with patch.object(provider._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        emb = await provider.generate_embedding("def calculate_metrics(): pass")
        assert emb.provider == "ollama"
        assert emb.dimension == 768
        assert len(emb.embedding) == 768

    await provider.close()


@pytest.mark.asyncio
async def test_gemini_provider_generate_chat_success():
    """Verifies Gemini candidate response parsing."""
    provider = GeminiProvider(api_key="test-gemini-key")

    mock_response = MagicMock(status_code=200)
    mock_response.json.return_value = {
        "candidates": [
            {
                "content": {"parts": [{"text": "Gemini fallback response."}]},
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 20,
            "candidatesTokenCount": 10,
        },
    }

    with patch.object(provider._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        messages = [ChatMessage(role="user", content="Hello")]
        res = await provider.generate_chat(messages)

        assert res.content == "Gemini fallback response."
        assert res.provider == "gemini"
        assert res.usage.prompt_tokens == 20
        assert res.usage.completion_tokens == 10

    await provider.close()


@pytest.mark.asyncio
async def test_gemini_provider_quota_exceeded():
    """Verifies HTTP 429 raises QuotaExceededError."""
    provider = GeminiProvider(api_key="test-gemini-key")

    mock_response = MagicMock(status_code=429)
    with patch.object(provider._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        with pytest.raises(QuotaExceededError):
            await provider.generate_chat([ChatMessage(role="user", content="Hello")])

    await provider.close()


@pytest.mark.asyncio
async def test_provider_manager_primary_ollama_success():
    """Verifies ProviderManager selects Ollama by default when available."""
    mock_ollama = MagicMock(spec=BaseLLMProvider)
    mock_ollama.provider_name = "ollama"
    mock_ollama.generate_chat = AsyncMock(
        return_value=GenerationResult(
            content="Ollama answer",
            provider="ollama",
            model="qwen3.5:4b",
        )
    )

    mock_gemini = MagicMock(spec=BaseLLMProvider)
    mock_gemini.provider_name = "gemini"

    manager = ProviderManager(ollama_provider=mock_ollama, gemini_provider=mock_gemini)
    res = await manager.generate_chat([ChatMessage(role="user", content="test")])

    assert res.provider == "ollama"
    assert res.content == "Ollama answer"
    mock_ollama.generate_chat.assert_called_once()
    mock_gemini.generate_chat.assert_not_called()


@pytest.mark.asyncio
async def test_provider_manager_fallback_on_ollama_failure(monkeypatch):
    """Verifies ProviderManager falls back to Gemini when Ollama is unavailable."""
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "real-mock-key")
    monkeypatch.setattr(settings, "GEMINI_ALLOW_CLOUD_FALLBACK", True)

    mock_ollama = MagicMock(spec=BaseLLMProvider)
    mock_ollama.provider_name = "ollama"
    mock_ollama.generate_chat = AsyncMock(
        side_effect=ProviderUnavailableError("Ollama machine is offline", provider="ollama")
    )

    mock_gemini = MagicMock(spec=BaseLLMProvider)
    mock_gemini.provider_name = "gemini"
    mock_gemini.generate_chat = AsyncMock(
        return_value=GenerationResult(
            content="Gemini fallback answer",
            provider="gemini",
            model="gemini-1.5-flash",
        )
    )

    manager = ProviderManager(ollama_provider=mock_ollama, gemini_provider=mock_gemini)
    res = await manager.generate_chat([ChatMessage(role="user", content="test")])

    assert res.provider == "gemini"
    assert res.content == "Gemini fallback answer"
    mock_ollama.generate_chat.assert_called_once()
    mock_gemini.generate_chat.assert_called_once()


@pytest.mark.asyncio
async def test_provider_manager_fallback_disabled(monkeypatch):
    """Verifies that if fallback is disabled, error is raised and Gemini is not contacted."""
    monkeypatch.setattr(settings, "GEMINI_ALLOW_CLOUD_FALLBACK", False)

    mock_ollama = MagicMock(spec=BaseLLMProvider)
    mock_ollama.provider_name = "ollama"
    mock_ollama.generate_chat = AsyncMock(
        side_effect=ProviderUnavailableError("Ollama down", provider="ollama")
    )

    mock_gemini = MagicMock(spec=BaseLLMProvider)
    mock_gemini.provider_name = "gemini"

    manager = ProviderManager(ollama_provider=mock_ollama, gemini_provider=mock_gemini)

    with pytest.raises(ProviderUnavailableError):
        await manager.generate_chat([ChatMessage(role="user", content="test")])

    mock_gemini.generate_chat.assert_not_called()


@pytest.mark.asyncio
async def test_secret_redaction_before_cloud_fallback(monkeypatch):
    """Verifies sensitive tokens/passwords are redacted before being dispatched to Gemini."""
    manager = ProviderManager()
    prompt = "Check my auth config: api_key='sk-1234567890abcdef' and token: ghp_111122223333444455556666777788889999"
    sanitized = manager.sanitize_text_for_cloud(prompt)

    assert "sk-1234567890abcdef" not in sanitized
    assert "ghp_111122223333444455556666777788889999" not in sanitized
    assert "[REDACTED_SECRET]" in sanitized
