import math
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from app.ai.exceptions import (
    InvalidResponseError,
    ModelNotFoundError,
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderErrorCategory,
    ProviderServerError,
    ProviderTimeoutError,
)
from app.ai.ollama_provider import OllamaProvider
from app.ai.provider_manager import ProviderManager
from app.ai.schemas import ChatMessage, GenerationResult, HealthStatus
from app.core.config import Settings


# ---------------------------------------------------------
# Chat Tests
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_ollama_chat_valid_request_and_endpoint():
    """Verifies valid chat request uses POST /api/chat with model qwen3.5:4b and bounded context."""
    provider = OllamaProvider(
        base_url="https://11434-agq6j3olyzqnjz6i3vl5zgyvj4.instabox.tech",
        access_token="test_token_123",
        generation_model="qwen3.5:4b",
    )

    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {
        "message": {"role": "assistant", "content": "Analysis of repository structure."},
        "prompt_eval_count": 150,
        "eval_count": 60,
        "done_reason": "stop",
    }

    with patch.object(provider._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        messages = [
            ChatMessage(role="user", content="Explain main.py"),
        ]
        res = await provider.generate_chat(
            messages=messages,
            system_prompt="You are a code analyzer.",
            temperature=0.1,
        )

        assert res.content == "Analysis of repository structure."
        assert res.provider == "ollama"
        assert res.model == "qwen3.5:4b"
        assert res.usage.prompt_tokens == 150
        assert res.usage.completion_tokens == 60

        # Verify call arguments
        mock_post.assert_called_once()
        call_args, call_kwargs = mock_post.call_args
        assert call_args[0] == "/api/chat"
        payload = call_kwargs["json"]
        assert payload["model"] == "qwen3.5:4b"
        assert len(payload["messages"]) == 2  # system + user
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][1]["role"] == "user"
        assert payload["options"]["temperature"] == 0.1
        assert "num_ctx" in payload["options"]
        assert call_kwargs["params"] == {"_token": "test_token_123"}

    await provider.close()


@pytest.mark.asyncio
async def test_ollama_chat_auth_failure_401():
    """Verifies HTTP 401 raises ProviderAuthenticationError with AUTHENTICATION_ERROR category."""
    provider = OllamaProvider(
        base_url="https://11434-agq6j3olyzqnjz6i3vl5zgyvj4.instabox.tech",
        access_token="bad_token",
    )

    mock_resp = MagicMock(status_code=401, text="This URL is private.")
    with patch.object(provider._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        with pytest.raises(ProviderAuthenticationError) as exc_info:
            await provider.generate_chat([ChatMessage(role="user", content="hello")])

        err = exc_info.value
        assert err.category == ProviderErrorCategory.AUTHENTICATION_ERROR
        assert err.status_code == 401
        assert err.is_recoverable is False

    await provider.close()


@pytest.mark.asyncio
async def test_ollama_chat_auth_failure_403():
    """Verifies HTTP 403 raises ProviderAuthenticationError with AUTHENTICATION_ERROR category."""
    provider = OllamaProvider(
        base_url="https://11434-agq6j3olyzqnjz6i3vl5zgyvj4.instabox.tech",
        access_token="expired_token",
    )

    mock_resp = MagicMock(status_code=403, text="This link's token is not valid.")
    with patch.object(provider._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        with pytest.raises(ProviderAuthenticationError) as exc_info:
            await provider.generate_chat([ChatMessage(role="user", content="hello")])

        err = exc_info.value
        assert err.category == ProviderErrorCategory.AUTHENTICATION_ERROR
        assert err.status_code == 403
        assert err.is_recoverable is False

    await provider.close()


@pytest.mark.asyncio
async def test_ollama_chat_model_missing_404():
    """Verifies HTTP 404 raises ModelNotFoundError with MODEL_NOT_FOUND category."""
    provider = OllamaProvider(
        base_url="https://11434-agq6j3olyzqnjz6i3vl5zgyvj4.instabox.tech",
        generation_model="nonexistent:model",
    )

    mock_resp = MagicMock(status_code=404, text="model not found")
    with patch.object(provider._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        with pytest.raises(ModelNotFoundError) as exc_info:
            await provider.generate_chat([ChatMessage(role="user", content="hello")])

        assert exc_info.value.category == ProviderErrorCategory.MODEL_NOT_FOUND
        assert exc_info.value.is_recoverable is False

    await provider.close()


@pytest.mark.asyncio
async def test_ollama_chat_timeout():
    """Verifies timeout raises ProviderTimeoutError with TIMEOUT_ERROR category and is_recoverable."""
    provider = OllamaProvider(
        base_url="https://11434-agq6j3olyzqnjz6i3vl5zgyvj4.instabox.tech",
    )

    with patch.object(provider._client, "post", side_effect=httpx.ReadTimeout("Read timed out")):
        with pytest.raises(ProviderTimeoutError) as exc_info:
            await provider.generate_chat([ChatMessage(role="user", content="hello")])

        assert exc_info.value.category == ProviderErrorCategory.TIMEOUT_ERROR
        assert exc_info.value.is_recoverable is True

    await provider.close()


@pytest.mark.asyncio
async def test_ollama_chat_server_error_500():
    """Verifies 500 raises ProviderServerError with SERVER_ERROR category."""
    provider = OllamaProvider(
        base_url="https://11434-agq6j3olyzqnjz6i3vl5zgyvj4.instabox.tech",
    )

    mock_resp = MagicMock(status_code=500, text="Internal engine crash")
    with patch.object(provider._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        with pytest.raises(ProviderServerError) as exc_info:
            await provider.generate_chat([ChatMessage(role="user", content="hello")])

        assert exc_info.value.category == ProviderErrorCategory.SERVER_ERROR
        assert exc_info.value.is_recoverable is True

    await provider.close()


@pytest.mark.asyncio
async def test_ollama_chat_malformed_json():
    """Verifies malformed JSON payload raises InvalidResponseError."""
    provider = OllamaProvider(
        base_url="https://11434-agq6j3olyzqnjz6i3vl5zgyvj4.instabox.tech",
    )

    mock_resp = MagicMock(status_code=200)
    mock_resp.json.side_effect = ValueError("Invalid JSON")
    with patch.object(provider._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        with pytest.raises(InvalidResponseError):
            await provider.generate_chat([ChatMessage(role="user", content="hello")])

    await provider.close()


# ---------------------------------------------------------
# Embedding Tests
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_ollama_embedding_valid_single_and_batch():
    """Verifies embedding generation supports /api/embed and validates finite vectors."""
    provider = OllamaProvider(
        base_url="https://11434-agq6j3olyzqnjz6i3vl5zgyvj4.instabox.tech",
        access_token="test_token_123",
        embedding_model="nomic-embed-text",
    )

    vector1 = [0.1, -0.2, 0.3] + [0.0] * 765
    vector2 = [0.4, 0.5, -0.6] + [0.0] * 765
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"embeddings": [vector1, vector2]}

    with patch.object(provider._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        results = await provider.generate_embeddings_batch(
            texts=["def function_one(): pass", "def function_two(): pass"],
        )

        assert len(results) == 2
        assert results[0].dimension == 768
        assert results[1].dimension == 768
        assert results[0].model == "nomic-embed-text"

        call_args, call_kwargs = mock_post.call_args
        assert call_args[0] == "/api/embed"
        assert call_kwargs["params"] == {"_token": "test_token_123"}

    await provider.close()


@pytest.mark.asyncio
async def test_ollama_embedding_empty_input_rejected():
    """Verifies empty string or whitespace raises InvalidResponseError."""
    provider = OllamaProvider(base_url="https://11434-agq6j3olyzqnjz6i3vl5zgyvj4.instabox.tech")

    with pytest.raises(InvalidResponseError) as exc_info:
        await provider.generate_embedding("   ")
    assert "empty" in str(exc_info.value).lower()

    await provider.close()


@pytest.mark.asyncio
async def test_ollama_embedding_non_finite_values_rejected():
    """Verifies vectors with NaN or Inf are rejected."""
    provider = OllamaProvider(base_url="https://11434-agq6j3olyzqnjz6i3vl5zgyvj4.instabox.tech")

    corrupted_vector = [0.1, float("nan"), 0.3] + [0.0] * 765
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"embeddings": [corrupted_vector]}

    with patch.object(provider._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        with pytest.raises(InvalidResponseError) as exc_info:
            await provider.generate_embedding("def foo(): pass")
        assert "non-finite" in str(exc_info.value).lower()

    await provider.close()


@pytest.mark.asyncio
async def test_ollama_embedding_inconsistent_dimensions_rejected():
    """Verifies batch with inconsistent vector dimensions raises InvalidResponseError."""
    provider = OllamaProvider(base_url="https://11434-agq6j3olyzqnjz6i3vl5zgyvj4.instabox.tech")

    vec_768 = [0.1] * 768
    vec_512 = [0.2] * 512
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"embeddings": [vec_768, vec_512]}

    with patch.object(provider._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        with pytest.raises(InvalidResponseError) as exc_info:
            await provider.generate_embeddings_batch(["chunk1", "chunk2"])
        assert "inconsistent" in str(exc_info.value).lower()

    await provider.close()


# ---------------------------------------------------------
# Health Check Tests
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_ollama_health_connected_status():
    """Verifies connected status when models are present and server responds 200."""
    provider = OllamaProvider(
        base_url="https://11434-agq6j3olyzqnjz6i3vl5zgyvj4.instabox.tech",
        generation_model="qwen3.5:4b",
        embedding_model="nomic-embed-text",
    )

    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {
        "models": [
            {"name": "qwen3.5:4b"},
            {"name": "nomic-embed-text:latest"},
        ]
    }

    with patch.object(provider._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        health = await provider.check_health()
        assert health.is_available is True
        assert health.status == HealthStatus.CONNECTED
        assert health.has_generation_model is True
        assert health.has_embedding_model is True
        assert health.error_message is None

    await provider.close()


@pytest.mark.asyncio
async def test_ollama_health_auth_failed():
    """Verifies health check marks status as AUTHENTICATION_FAILED on 401/403."""
    provider = OllamaProvider(
        base_url="https://11434-agq6j3olyzqnjz6i3vl5zgyvj4.instabox.tech",
    )

    mock_resp = MagicMock(status_code=401, text="Unauthorized")
    with patch.object(provider._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        health = await provider.check_health()
        assert health.is_available is False
        assert health.status == HealthStatus.AUTHENTICATION_FAILED

    await provider.close()


@pytest.mark.asyncio
async def test_ollama_health_generation_model_missing():
    """Verifies status GENERATION_MODEL_MISSING when qwen3.5:4b is not in tags list."""
    provider = OllamaProvider(
        base_url="https://11434-agq6j3olyzqnjz6i3vl5zgyvj4.instabox.tech",
        generation_model="qwen3.5:4b",
        embedding_model="nomic-embed-text",
    )

    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {
        "models": [{"name": "nomic-embed-text:latest"}]  # Missing qwen3.5:4b
    }

    with patch.object(provider._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        health = await provider.check_health()
        assert health.status == HealthStatus.GENERATION_MODEL_MISSING
        assert health.has_generation_model is False
        assert health.has_embedding_model is True

    await provider.close()


@pytest.mark.asyncio
async def test_ollama_health_embedding_model_missing():
    """Verifies status EMBEDDING_MODEL_MISSING when nomic-embed-text is missing."""
    provider = OllamaProvider(
        base_url="https://11434-agq6j3olyzqnjz6i3vl5zgyvj4.instabox.tech",
        generation_model="qwen3.5:4b",
        embedding_model="nomic-embed-text",
    )

    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {
        "models": [{"name": "qwen3.5:4b"}]  # Missing nomic-embed-text
    }

    with patch.object(provider._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        health = await provider.check_health()
        assert health.status == HealthStatus.EMBEDDING_MODEL_MISSING
        assert health.has_generation_model is True
        assert health.has_embedding_model is False

    await provider.close()


@pytest.mark.asyncio
async def test_ollama_health_server_unavailable():
    """Verifies status SERVER_UNAVAILABLE when connection fails."""
    provider = OllamaProvider(base_url="https://11434-agq6j3olyzqnjz6i3vl5zgyvj4.instabox.tech")

    with patch.object(provider._client, "get", side_effect=httpx.ConnectError("Connection refused")):
        health = await provider.check_health()
        assert health.is_available is False
        assert health.status == HealthStatus.SERVER_UNAVAILABLE

    await provider.close()


@pytest.mark.asyncio
async def test_ollama_health_request_timed_out():
    """Verifies status REQUEST_TIMED_OUT when connection times out."""
    provider = OllamaProvider(base_url="https://11434-agq6j3olyzqnjz6i3vl5zgyvj4.instabox.tech")

    with patch.object(provider._client, "get", side_effect=httpx.ConnectTimeout("Connect timed out")):
        health = await provider.check_health()
        assert health.is_available is False
        assert health.status == HealthStatus.REQUEST_TIMED_OUT

    await provider.close()


# ---------------------------------------------------------
# Security & Fallback Policy Tests
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_authentication_error_never_triggers_fallback():
    """Verifies ProviderAuthenticationError from Ollama is NOT fallen back to Gemini."""
    mock_ollama = MagicMock(spec=OllamaProvider)
    mock_ollama.provider_name = "ollama"
    mock_ollama.generate_chat = AsyncMock(
        side_effect=ProviderAuthenticationError("Invalid port token", provider="ollama")
    )

    mock_gemini = MagicMock()
    mock_gemini.provider_name = "gemini"
    mock_gemini.generate_chat = AsyncMock()

    manager = ProviderManager(ollama_provider=mock_ollama, gemini_provider=mock_gemini)

    with pytest.raises(ProviderAuthenticationError):
        await manager.generate_chat([ChatMessage(role="user", content="hello")])

    mock_gemini.generate_chat.assert_not_called()


@pytest.mark.asyncio
async def test_token_redacted_in_errors():
    """Verifies private port token is never exposed in error text."""
    secret_token = "ibp_very_sensitive_private_key_12345"
    provider = OllamaProvider(
        base_url="https://11434-agq6j3olyzqnjz6i3vl5zgyvj4.instabox.tech",
        access_token=secret_token,
    )

    raw_err = f"Failed on endpoint with token {secret_token}"
    sanitized = provider._sanitize_error_text(raw_err)

    assert secret_token not in sanitized
    assert "[REDACTED_TOKEN]" in sanitized

    await provider.close()


def test_configuration_environment_selection():
    """Verifies Settings selects production InstaBox base URL in production."""
    prod_settings = Settings(
        APP_ENV="production",
        OLLAMA_BASE_URL="http://localhost:11434",
        PRODUCTION_OLLAMA_BASE_URL="https://11434-agq6j3olyzqnjz6i3vl5zgyvj4.instabox.tech",
    )
    assert prod_settings.effective_ollama_base_url == "https://11434-agq6j3olyzqnjz6i3vl5zgyvj4.instabox.tech"

    dev_settings = Settings(
        APP_ENV="development",
        OLLAMA_BASE_URL="http://localhost:11434",
        PRODUCTION_OLLAMA_BASE_URL="https://11434-agq6j3olyzqnjz6i3vl5zgyvj4.instabox.tech",
    )
    assert dev_settings.effective_ollama_base_url == "http://localhost:11434"
