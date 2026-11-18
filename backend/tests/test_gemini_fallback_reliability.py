import pytest
from unittest.mock import AsyncMock, MagicMock
import httpx

from app.ai.base import BaseLLMProvider
from app.ai.gemini_provider import GeminiProvider
from app.ai.exceptions import (
    AIProviderError,
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderTimeoutError,
    ProviderErrorCategory,
    QuotaExceededError,
)
from app.ai.provider_manager import ProviderManager
from app.ai.schemas import ChatMessage, GenerationResult
from app.core.config import settings


@pytest.mark.asyncio
async def test_gemini_fallback_activated_on_connection_error(monkeypatch):
    """Verifies that recoverable Ollama ConnectionError triggers Gemini fallback with provider attribution."""
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "mock-gemini-key")
    monkeypatch.setattr(settings, "GEMINI_ALLOW_CLOUD_FALLBACK", True)

    mock_ollama = MagicMock(spec=BaseLLMProvider)
    mock_ollama.provider_name = "ollama"
    mock_ollama.generate_chat = AsyncMock(
        side_effect=ProviderConnectionError("InstaBox server is offline / connection refused", provider="ollama")
    )

    mock_gemini = MagicMock(spec=BaseLLMProvider)
    mock_gemini.provider_name = "gemini"
    mock_gemini.generate_chat = AsyncMock(
        return_value=GenerationResult(
            content="This is the answer from Gemini fallback.",
            provider="gemini",
            model="gemini-1.5-flash",
        )
    )

    manager = ProviderManager(ollama_provider=mock_ollama, gemini_provider=mock_gemini)
    res = await manager.generate_chat([ChatMessage(role="user", content="Explain repo architecture")])

    assert res.provider == "gemini"
    assert res.model == "gemini-1.5-flash"
    assert "Gemini fallback" in res.content
    mock_ollama.generate_chat.assert_called_once()
    mock_gemini.generate_chat.assert_called_once()


@pytest.mark.asyncio
async def test_gemini_fallback_strictly_blocked_on_auth_error(monkeypatch):
    """Verifies that ProviderAuthenticationError NEVER triggers cloud fallback."""
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "mock-gemini-key")
    monkeypatch.setattr(settings, "GEMINI_ALLOW_CLOUD_FALLBACK", True)

    mock_ollama = MagicMock(spec=BaseLLMProvider)
    mock_ollama.provider_name = "ollama"
    mock_ollama.generate_chat = AsyncMock(
        side_effect=ProviderAuthenticationError("Invalid port token (HTTP 401)", provider="ollama")
    )

    mock_gemini = MagicMock(spec=BaseLLMProvider)
    mock_gemini.provider_name = "gemini"
    mock_gemini.generate_chat = AsyncMock()

    manager = ProviderManager(ollama_provider=mock_ollama, gemini_provider=mock_gemini)

    with pytest.raises(ProviderAuthenticationError):
        await manager.generate_chat([ChatMessage(role="user", content="hello")])

    mock_gemini.generate_chat.assert_not_called()


@pytest.mark.asyncio
async def test_gemini_fallback_blocked_when_flag_disabled(monkeypatch):
    """Verifies that setting GEMINI_ALLOW_CLOUD_FALLBACK = False disables cloud failover."""
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "mock-gemini-key")
    monkeypatch.setattr(settings, "GEMINI_ALLOW_CLOUD_FALLBACK", False)

    mock_ollama = MagicMock(spec=BaseLLMProvider)
    mock_ollama.provider_name = "ollama"
    mock_ollama.generate_chat = AsyncMock(
        side_effect=ProviderConnectionError("Ollama connection timed out", provider="ollama")
    )

    mock_gemini = MagicMock(spec=BaseLLMProvider)
    mock_gemini.generate_chat = AsyncMock()

    manager = ProviderManager(ollama_provider=mock_ollama, gemini_provider=mock_gemini)

    with pytest.raises(ProviderConnectionError):
        await manager.generate_chat([ChatMessage(role="user", content="hello")])

    mock_gemini.generate_chat.assert_not_called()


@pytest.mark.asyncio
async def test_gemini_quota_exhausted_error(monkeypatch):
    """Verifies that HTTP 429 quota exhaustion from Gemini surfaces a clear user error."""
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "mock-gemini-key")
    monkeypatch.setattr(settings, "GEMINI_ALLOW_CLOUD_FALLBACK", True)

    mock_ollama = MagicMock(spec=BaseLLMProvider)
    mock_ollama.provider_name = "ollama"
    mock_ollama.generate_chat = AsyncMock(
        side_effect=ProviderConnectionError("Ollama down", provider="ollama")
    )

    mock_gemini = MagicMock(spec=BaseLLMProvider)
    mock_gemini.provider_name = "gemini"
    mock_gemini.generate_chat = AsyncMock(
        side_effect=QuotaExceededError("Rate limit exceeded 429", provider="gemini")
    )

    manager = ProviderManager(ollama_provider=mock_ollama, gemini_provider=mock_gemini)

    with pytest.raises(AIProviderError) as exc_info:
        await manager.generate_chat([ChatMessage(role="user", content="hello")])

    assert "quota is exhausted" in str(exc_info.value).lower()


def test_sensitive_secret_redaction_before_cloud():
    """Verifies that passwords, API keys, and auth headers are redacted prior to cloud dispatch."""
    manager = ProviderManager()
    prompt = (
        "Here is the database URL: postgresql://postgres:SuperSecretPassword123@localhost:5432/repomind "
        "and client_secret = 'super_secret_token_abc' with authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.t-IDNac"
    )

    sanitized = manager.sanitize_text_for_cloud(prompt)

    assert "SuperSecretPassword123" not in sanitized
    assert "super_secret_token_abc" not in sanitized
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in sanitized
    assert "[REDACTED_SECRET]" in sanitized
@pytest.mark.asyncio
async def test_gemini_read_timeout_raises_timeout_error(monkeypatch):
    """Verifies Gemini read timeouts are classified as recoverable timeout errors."""
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "mock-gemini-key")

    provider = GeminiProvider(
        api_key="mock-gemini-key",
        model="gemini-3.8-flash",
        timeout_seconds=5,
    )

    try:
        with pytest.raises(ProviderTimeoutError) as exc_info:
            async def mock_post(*args, **kwargs):
                raise httpx.ReadTimeout("Read timed out")

            monkeypatch.setattr(provider._client, "post", mock_post)

            await provider.generate_chat(
                messages=[ChatMessage(role="user", content="Hello")]
            )

        assert exc_info.value.category == ProviderErrorCategory.TIMEOUT_ERROR
        assert exc_info.value.is_recoverable is True
    finally:
        await provider._client.aclose()
