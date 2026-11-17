import re
from typing import Dict, List, Optional

from app.ai.base import BaseLLMProvider
from app.ai.exceptions import (
    AIProviderError,
    ModelNotFoundError,
    ProviderUnavailableError,
    QuotaExceededError,
)
from app.ai.gemini_provider import GeminiProvider
from app.ai.ollama_provider import OllamaProvider
from app.ai.schemas import (
    ChatMessage,
    EmbeddingResult,
    GenerationResult,
    ProviderHealth,
)
from app.core.config import settings
from app.core.logging import logger

# Regex patterns and replacements for redacting sensitive values before any cloud provider dispatch
REDACTION_RULES = [
    # Key-value secret assignments: api_key = "...", token = "..."
    (re.compile(r'(?i)(api[_-]?key|secret|password|token|bearer|auth)["\']?\s*[:=]\s*["\']?[^\s,"\'\}]+', re.IGNORECASE), r'\1: [REDACTED_SECRET]'),
    # Database connection URLs with embedded passwords (e.g. postgresql://user:pass@host:port/db)
    (re.compile(r'://([^:]+):([^@]+)@', re.IGNORECASE), r'://\1:[REDACTED_SECRET]@'),
    # GitHub personal access tokens
    (re.compile(r'ghp_[A-Za-z0-9_]{30,}', re.IGNORECASE), '[REDACTED_SECRET]'),
    # JWT tokens
    (re.compile(r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9._-]{10,}', re.IGNORECASE), '[REDACTED_SECRET]'),
]


class ProviderManager:
    """
    Centralized coordinator managing primary and fallback AI generation and embeddings.
    Enforces the mandatory architectural rule:
    1. Primary generation provider: Ollama (localhost or InstaBox)
    2. Fallback generation provider: Gemini free tier (only when Ollama encounters recoverable failure)
    3. Mandatory embedding provider: Ollama (nomic-embed-text)
    """

    def __init__(
        self,
        ollama_provider: Optional[BaseLLMProvider] = None,
        gemini_provider: Optional[BaseLLMProvider] = None,
    ) -> None:
        self._ollama = ollama_provider or OllamaProvider()
        self._gemini = gemini_provider or GeminiProvider()
        self._primary_name = settings.AI_PRIMARY_PROVIDER.lower()
        self._fallback_name = settings.AI_FALLBACK_PROVIDER.lower()

    @property
    def primary_provider(self) -> BaseLLMProvider:
        if self._primary_name == "ollama":
            return self._ollama
        return self._gemini

    @property
    def fallback_provider(self) -> BaseLLMProvider:
        if self._fallback_name == "gemini":
            return self._gemini
        return self._ollama

    async def close(self) -> None:
        await self._ollama.close()
        await self._gemini.close()

    def sanitize_text_for_cloud(self, text: str) -> str:
        """Redacts obvious tokens, secrets, and API credentials before sending content to cloud fallback."""
        sanitized = text
        for pattern, replacement in REDACTION_RULES:
            sanitized = pattern.sub(replacement, sanitized)
        return sanitized

    async def generate_chat(
        self,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        model_override: Optional[str] = None,
        allow_fallback: bool = True,
    ) -> GenerationResult:
        """
        Attempts inference via primary provider (Ollama).
        If Ollama fails with recoverable connection/timeout/server errors and fallback is enabled,
        gracefully fails over to Gemini free tier with credential redaction.
        Authentication errors (401/403) and client input errors are NEVER fallen back.
        """
        primary = self.primary_provider
        fallback = self.fallback_provider

        try:
            logger.info("Dispatching chat generation to primary provider '%s'", primary.provider_name)
            result = await primary.generate_chat(
                messages=messages,
                model=model_override,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return result
        except AIProviderError as primary_err:
            # If the error is not recoverable (e.g. AuthenticationError, ModelNotFoundError, InvalidResponse), re-raise immediately
            if not getattr(primary_err, "is_recoverable", False):
                logger.warning(
                    "Primary AI provider '%s' raised non-recoverable error [%s]: %s. Fallback not triggered.",
                    primary.provider_name,
                    getattr(primary_err, "category", "ERROR"),
                    primary_err.message,
                )
                raise primary_err

            logger.warning(
                "Primary AI provider '%s' failed with recoverable error [%s]: %s",
                primary.provider_name,
                getattr(primary_err, "category", "ERROR"),
                primary_err.message,
            )

            # Check if fallback is permitted and configured
            can_fallback = (
                allow_fallback
                and settings.GEMINI_ALLOW_CLOUD_FALLBACK
                and self._fallback_name == "gemini"
                and bool(settings.GEMINI_API_KEY)
            )

            if not can_fallback:
                logger.error(
                    "Fallback provider not available or disabled (allow_fallback=%s, GEMINI_ALLOW_CLOUD_FALLBACK=%s). Raising error.",
                    allow_fallback,
                    settings.GEMINI_ALLOW_CLOUD_FALLBACK,
                )
                raise primary_err

            logger.info("Initiating cloud fallback to '%s' (Gemini Free Tier)", fallback.provider_name)

            # Sanitize messages before cloud dispatch
            sanitized_messages = [
                ChatMessage(
                    role=m.role,
                    content=self.sanitize_text_for_cloud(m.content),
                )
                for m in messages
            ]
            sanitized_system = (
                self.sanitize_text_for_cloud(system_prompt)
                if system_prompt
                else None
            )

            try:
                fallback_result = await fallback.generate_chat(
                    messages=sanitized_messages,
                    system_prompt=sanitized_system,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return fallback_result
            except QuotaExceededError as qe:
                logger.error("Gemini free-tier fallback quota exceeded: %s", qe.message)
                raise AIProviderError(
                    "Primary inference (Ollama) is unavailable, and Gemini fallback quota is exhausted.",
                    provider="gemini",
                ) from qe
            except Exception as fb_err:
                logger.error("Fallback provider '%s' also failed: %s", fallback.provider_name, fb_err)
                raise AIProviderError(
                    f"Both primary provider ({primary.provider_name}) and fallback provider ({fallback.provider_name}) failed.",
                    provider="multi-provider",
                ) from fb_err

    async def generate_embedding(
        self,
        text: str,
        model: Optional[str] = None,
    ) -> EmbeddingResult:
        """
        Embeddings are strictly generated through Ollama nomic-embed-text to guarantee
        vector dimension stability and local/cloud repository indexing consistency.
        Never falls back to Gemini.
        """
        return await self._ollama.generate_embedding(text=text, model=model)

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        model: Optional[str] = None,
    ) -> List[EmbeddingResult]:
        """
        Batch embeddings are strictly generated through Ollama nomic-embed-text.
        Never falls back to Gemini.
        """
        return await self._ollama.generate_embeddings_batch(texts=texts, model=model)

    async def check_health(self) -> Dict[str, ProviderHealth]:
        """Runs health checks on all configured providers."""
        ollama_health = await self._ollama.check_health()
        gemini_health = await self._gemini.check_health()
        return {
            "ollama": ollama_health,
            "gemini": gemini_health,
        }
