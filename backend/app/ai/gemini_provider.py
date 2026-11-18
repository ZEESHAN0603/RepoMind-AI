import time
from typing import Any, Dict, List, Optional
import httpx


from app.ai.base import BaseLLMProvider
from app.ai.exceptions import (
    AIProviderError,
    ProviderResponseError,
    ProviderUnavailableError,
    ProviderTimeoutError,
    QuotaExceededError,
)
from app.ai.schemas import (
    ChatMessage,
    EmbeddingResult,
    GenerationResult,
    ProviderHealth,
    TokenUsage,
)
from app.core.config import settings
from app.core.logging import logger

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini API client (Free Tier Only) used strictly as a resilient fallback
    when primary inference (Ollama) encounters recoverable failure.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> None:
        self._api_key = api_key or settings.GEMINI_API_KEY
        self._model = model or settings.GEMINI_MODEL
        self._timeout_seconds = timeout_seconds or settings.GEMINI_TIMEOUT_SECONDS
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout=self._timeout_seconds, connect=10.0),
            headers={
                "x-goog-api-key": self._api_key,
                "Content-Type": "application/json",
            },
        )

    @property
    def provider_name(self) -> str:
        return "gemini"

    async def close(self) -> None:
        await self._client.aclose()

    async def check_health(self) -> ProviderHealth:
        if not self._api_key:
            return ProviderHealth(
                provider=self.provider_name,
                is_available=False,
                error_message="Gemini API key is not configured.",
            )

        start_t = time.perf_counter()
        try:
            url = f"{GEMINI_API_BASE}/models"
            resp = await self._client.get(url)
            latency_ms = (time.perf_counter() - start_t) * 1000

            if resp.status_code == 200:
                data = resp.json()
                models = [
                    m.get("name", "").replace("models/", "")
                    for m in data.get("models", [])
                    if "generateContent" in m.get("supportedGenerationMethods", [])
                ]
                return ProviderHealth(
                    provider=self.provider_name,
                    is_available=True,
                    has_generation_model=self._model in models,
                    has_embedding_model=False,
                    latency_ms=round(latency_ms, 2),
                    available_models=models[:10],
                )
            elif resp.status_code == 429:
                return ProviderHealth(
                    provider=self.provider_name,
                    is_available=False,
                    latency_ms=round(latency_ms, 2),
                    error_message="Gemini free-tier quota exceeded (HTTP 429).",
                )
            else:
                return ProviderHealth(
                    provider=self.provider_name,
                    is_available=False,
                    latency_ms=round(latency_ms, 2),
                    error_message=f"Gemini API returned status {resp.status_code}",
                )
        except Exception as ex:
            latency_ms = (time.perf_counter() - start_t) * 1000
            return ProviderHealth(
                provider=self.provider_name,
                is_available=False,
                latency_ms=round(latency_ms, 2),
                error_message=f"Gemini connection error: {type(ex).__name__}",
            )

    async def generate_chat(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
    ) -> GenerationResult:
        if not self._api_key:
            raise AIProviderError("Gemini fallback cannot be used: GEMINI_API_KEY is not configured.", provider=self.provider_name)

        target_model = model or self._model
        url = f"{GEMINI_API_BASE}/models/{target_model}:generateContent"

        # Convert ChatMessage list to Gemini contents structure
        contents: List[Dict[str, Any]] = []
        for msg in messages:
            role = "user" if msg.role == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg.content}],
            })

        body: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {},
        }
        if max_tokens:
            body["generationConfig"]["maxOutputTokens"] = max_tokens

        if system_prompt:
            body["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
            }

        start_t = time.perf_counter()
        try:
            resp = await self._client.post(url, json=body)
        except (httpx.ConnectError, httpx.ConnectTimeout) as ce:
            raise ProviderUnavailableError("Could not connect to Gemini API endpoint.", provider=self.provider_name) from ce
        except httpx.ReadTimeout as re:
            raise ProviderTimeoutError(
                f"Gemini API request timed out after {self._timeout_seconds}s.",
                provider=self.provider_name,
            ) from re
        except Exception as ex:
            raise ProviderUnavailableError(f"Gemini request failed: {type(ex).__name__}", provider=self.provider_name) from ex

        duration = time.perf_counter() - start_t

        if resp.status_code == 429:
            raise QuotaExceededError("Gemini free-tier quota limit reached. Please wait or check rate limits.", provider=self.provider_name)
        elif resp.status_code != 200:
            raise ProviderResponseError(f"Gemini API returned HTTP {resp.status_code}", provider=self.provider_name)

        try:
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise ProviderResponseError("Gemini returned empty candidate list.", provider=self.provider_name)

            first_cand = candidates[0]
            parts = first_cand.get("content", {}).get("parts", [])
            content_text = "".join(p.get("text", "") for p in parts)

            usage_metadata = data.get("usageMetadata", {})
            prompt_tokens = usage_metadata.get("promptTokenCount", 0)
            completion_tokens = usage_metadata.get("candidatesTokenCount", 0)

            return GenerationResult(
                content=content_text,
                provider=self.provider_name,
                model=target_model,
                usage=TokenUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                ),
                duration_seconds=round(duration, 3),
                finish_reason=first_cand.get("finishReason", "STOP"),
                raw_response={"finishReason": first_cand.get("finishReason")},
            )
        except AIProviderError:
            raise
        except Exception as ex:
            raise ProviderResponseError(f"Failed to parse Gemini response: {ex}", provider=self.provider_name) from ex

    async def generate_embedding(
        self,
        text: str,
        model: Optional[str] = None,
    ) -> EmbeddingResult:
        """
        Ollama is the primary and mandatory embedding provider.
        Gemini is not configured as embedding provider to ensure vector consistency.
        """
        raise NotImplementedError("Embeddings must be generated using Ollama nomic-embed-text for consistent dimensions.")

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        model: Optional[str] = None,
    ) -> List[EmbeddingResult]:
        """
        Batch embeddings are also blocked on Gemini for vector dimension integrity.
        """
        raise NotImplementedError("Embeddings must be generated using Ollama nomic-embed-text for consistent dimensions.")
