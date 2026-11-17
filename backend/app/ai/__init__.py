"""
AI and LLM Provider Abstraction Package (Phase 5).
"""

from app.ai.base import BaseLLMProvider
from app.ai.exceptions import (
    AIProviderError,
    ContextLengthExceededError,
    InvalidResponseError,
    ModelNotFoundError,
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderErrorCategory,
    ProviderResponseError,
    ProviderServerError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    QuotaExceededError,
    RateLimitedError,
)
from app.ai.gemini_provider import GeminiProvider
from app.ai.ollama_provider import OllamaProvider
from app.ai.provider_manager import ProviderManager
from app.ai.schemas import (
    BatchEmbeddingResult,
    ChatMessage,
    EmbeddingResult,
    GenerationResult,
    HealthStatus,
    ProviderHealth,
    ProviderType,
    TokenUsage,
)

__all__ = [
    "BaseLLMProvider",
    "OllamaProvider",
    "GeminiProvider",
    "ProviderManager",
    "ChatMessage",
    "GenerationResult",
    "EmbeddingResult",
    "BatchEmbeddingResult",
    "ProviderHealth",
    "ProviderType",
    "HealthStatus",
    "TokenUsage",
    "AIProviderError",
    "ProviderErrorCategory",
    "ProviderAuthenticationError",
    "ProviderConnectionError",
    "ProviderTimeoutError",
    "ModelNotFoundError",
    "InvalidResponseError",
    "RateLimitedError",
    "ProviderServerError",
    "QuotaExceededError",
    "ContextLengthExceededError",
    "ProviderResponseError",
    "ProviderUnavailableError",
]
