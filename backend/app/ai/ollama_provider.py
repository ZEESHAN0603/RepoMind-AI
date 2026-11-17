import math
import time
from typing import Any, Dict, List, Optional
import httpx

from app.ai.base import BaseLLMProvider
from app.ai.exceptions import (
    InvalidResponseError,
    ModelNotFoundError,
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderServerError,
    ProviderTimeoutError,
)
from app.ai.schemas import (
    ChatMessage,
    EmbeddingResult,
    GenerationResult,
    HealthStatus,
    ProviderHealth,
    TokenUsage,
)
from app.core.config import settings
from app.core.logging import logger


class OllamaProvider(BaseLLMProvider):
    """
    Production-ready Ollama API provider supporting:
    - Local Ollama development server (http://localhost:11434)
    - Remote cloud InstaBox instance over HTTPS with private port token authentication.
    - Bounded timeouts, non-streaming chat generation, batch/single embedding extraction,
      and comprehensive error categorization.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        access_token: Optional[str] = None,
        chat_endpoint: Optional[str] = None,
        embed_endpoint: Optional[str] = None,
        generation_model: Optional[str] = None,
        embedding_model: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        connect_timeout_seconds: Optional[float] = None,
    ) -> None:
        self._base_url = (base_url or settings.effective_ollama_base_url).rstrip("/")
        self._access_token = (access_token if access_token is not None else settings.effective_ollama_access_token)
        self._chat_endpoint = chat_endpoint or settings.OLLAMA_CHAT_ENDPOINT
        self._embed_endpoint = embed_endpoint or settings.OLLAMA_EMBED_ENDPOINT
        self._generation_model = generation_model or settings.OLLAMA_GENERATION_MODEL
        self._embedding_model = embedding_model or settings.OLLAMA_EMBEDDING_MODEL
        self._timeout_seconds = timeout_seconds or settings.OLLAMA_TIMEOUT_SECONDS
        self._connect_timeout_seconds = connect_timeout_seconds or settings.OLLAMA_CONNECT_TIMEOUT_SECONDS

        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=httpx.Timeout(
                timeout=self._timeout_seconds,
                connect=self._connect_timeout_seconds,
            ),
            verify=True,  # Mandatory TLS certificate validation
        )

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def base_url(self) -> str:
        return self._base_url

    async def close(self) -> None:
        await self._client.aclose()

    def _get_auth_params(self) -> Dict[str, str]:
        """Returns query parameters including private port token if configured."""
        if self._access_token:
            return {"_token": self._access_token}
        return {}

    def _sanitize_error_text(self, text: str) -> str:
        """Removes sensitive tokens or internal URLs from exception strings."""
        sanitized = text
        if self._access_token and len(self._access_token) > 4:
            sanitized = sanitized.replace(self._access_token, "[REDACTED_TOKEN]")
        return sanitized[:200]

    def _validate_vector_values(self, vector: List[float], source_label: str = "vector") -> None:
        """Validates that all values in an embedding vector are numeric and finite."""
        if not vector or not isinstance(vector, list):
            raise InvalidResponseError(
                f"Embedding response for {source_label} is empty or not a list.",
                provider=self.provider_name,
            )
        for i, val in enumerate(vector):
            if not isinstance(val, (int, float)) or not math.isfinite(val):
                raise InvalidResponseError(
                    f"Non-finite or non-numeric vector component detected at index {i} in {source_label}.",
                    provider=self.provider_name,
                )

    async def check_health(self) -> ProviderHealth:
        """
        Executes a lightweight health check verifying:
        1. Endpoint reachable.
        2. Authentication succeeded (not 401/403).
        3. Ollama responds.
        4. Generation model is installed.
        5. Embedding model is installed.
        """
        start_t = time.perf_counter()
        try:
            resp = await self._client.get("/api/tags", params=self._get_auth_params())
            latency_ms = (time.perf_counter() - start_t) * 1000

            if resp.status_code in (401, 403):
                return ProviderHealth(
                    provider=self.provider_name,
                    is_available=False,
                    status=HealthStatus.AUTHENTICATION_FAILED,
                    latency_ms=round(latency_ms, 2),
                    error_message=f"Authentication failed (HTTP {resp.status_code}). Check OLLAMA_ACCESS_TOKEN.",
                )

            if resp.status_code != 200:
                return ProviderHealth(
                    provider=self.provider_name,
                    is_available=False,
                    status=HealthStatus.INVALID_RESPONSE,
                    latency_ms=round(latency_ms, 2),
                    error_message=f"Server returned HTTP {resp.status_code}: {self._sanitize_error_text(resp.text)}",
                )

            data = resp.json()
            models_list = data.get("models", [])
            installed_names = [m.get("name", "") for m in models_list if "name" in m]

            # Model presence checks (supports exact match or prefix before tag)
            gen_target = self._generation_model.lower()
            embed_target = self._embedding_model.lower()

            has_gen = any(
                m.lower() == gen_target or m.lower().startswith(gen_target.split(":")[0])
                for m in installed_names
            )
            has_embed = any(
                m.lower() == embed_target or m.lower().startswith(embed_target.split(":")[0])
                for m in installed_names
            )

            if not has_gen:
                return ProviderHealth(
                    provider=self.provider_name,
                    is_available=True,  # Server is up, but model missing
                    status=HealthStatus.GENERATION_MODEL_MISSING,
                    has_generation_model=False,
                    has_embedding_model=has_embed,
                    latency_ms=round(latency_ms, 2),
                    available_models=installed_names,
                    error_message=f"Generation model '{self._generation_model}' is not installed on Ollama server.",
                )

            if not has_embed:
                return ProviderHealth(
                    provider=self.provider_name,
                    is_available=True,
                    status=HealthStatus.EMBEDDING_MODEL_MISSING,
                    has_generation_model=True,
                    has_embedding_model=False,
                    latency_ms=round(latency_ms, 2),
                    available_models=installed_names,
                    error_message=f"Embedding model '{self._embedding_model}' is not installed on Ollama server.",
                )

            return ProviderHealth(
                provider=self.provider_name,
                is_available=True,
                status=HealthStatus.CONNECTED,
                has_generation_model=True,
                has_embedding_model=True,
                latency_ms=round(latency_ms, 2),
                available_models=installed_names,
            )

        except (httpx.ConnectTimeout, httpx.ReadTimeout):
            latency_ms = (time.perf_counter() - start_t) * 1000
            return ProviderHealth(
                provider=self.provider_name,
                is_available=False,
                status=HealthStatus.REQUEST_TIMED_OUT,
                latency_ms=round(latency_ms, 2),
                error_message=f"Connection timed out after {self._connect_timeout_seconds}s.",
            )
        except httpx.ConnectError:
            latency_ms = (time.perf_counter() - start_t) * 1000
            return ProviderHealth(
                provider=self.provider_name,
                is_available=False,
                status=HealthStatus.SERVER_UNAVAILABLE,
                latency_ms=round(latency_ms, 2),
                error_message="Could not establish connection to Ollama server (machine may be paused or down).",
            )
        except Exception as ex:
            latency_ms = (time.perf_counter() - start_t) * 1000
            return ProviderHealth(
                provider=self.provider_name,
                is_available=False,
                status=HealthStatus.UNKNOWN_FAILURE,
                latency_ms=round(latency_ms, 2),
                error_message=f"Health check failed with unexpected error: {type(ex).__name__}",
            )

    async def generate_chat(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
    ) -> GenerationResult:
        """
        Executes non-streaming chat generation via POST /api/chat.
        """
        target_model = model or self._generation_model
        payload_messages = []

        if system_prompt:
            payload_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            payload_messages.append(msg.to_dict())

        options: Dict[str, Any] = {
            "temperature": temperature,
            "num_ctx": settings.OLLAMA_CONTEXT_WINDOW,
        }
        if max_tokens:
            options["num_predict"] = max_tokens

        payload = {
            "model": target_model,
            "messages": payload_messages,
            "stream": False,
            "options": options,
        }

        endpoint = self._chat_endpoint or "/api/chat"
        start_t = time.perf_counter()

        try:
            resp = await self._client.post(
                endpoint,
                json=payload,
                params=self._get_auth_params(),
            )
        except httpx.ConnectTimeout as ct:
            raise ProviderTimeoutError(
                f"Connection to Ollama timed out after {self._connect_timeout_seconds}s.",
                provider=self.provider_name,
            ) from ct
        except httpx.ReadTimeout as rt:
            raise ProviderTimeoutError(
                f"Ollama generation inference timed out after {self._timeout_seconds}s.",
                provider=self.provider_name,
            ) from rt
        except httpx.ConnectError as ce:
            raise ProviderConnectionError(
                f"Ollama server is unavailable at {self._base_url}. The instance may be paused or offline.",
                provider=self.provider_name,
            ) from ce
        except Exception as ex:
            raise ProviderConnectionError(
                f"Network request to Ollama failed: {type(ex).__name__}",
                provider=self.provider_name,
            ) from ex

        duration = time.perf_counter() - start_t

        if resp.status_code in (401, 403):
            raise ProviderAuthenticationError(
                f"Ollama authentication failed (HTTP {resp.status_code}). Verify OLLAMA_ACCESS_TOKEN.",
                provider=self.provider_name,
                status_code=resp.status_code,
            )
        elif resp.status_code == 404:
            raise ModelNotFoundError(
                f"Ollama model '{target_model}' was not found. Please verify the model tag.",
                provider=self.provider_name,
            )
        elif 500 <= resp.status_code < 600:
            raise ProviderServerError(
                f"Ollama server error (HTTP {resp.status_code}): {self._sanitize_error_text(resp.text)}",
                provider=self.provider_name,
                status_code=resp.status_code,
            )
        elif resp.status_code != 200:
            raise InvalidResponseError(
                f"Ollama returned unexpected HTTP {resp.status_code}: {self._sanitize_error_text(resp.text)}",
                provider=self.provider_name,
            )

        try:
            data = resp.json()
            message_obj = data.get("message", {})
            content = message_obj.get("content", "")

            prompt_tokens = data.get("prompt_eval_count", 0)
            completion_tokens = data.get("eval_count", 0)

            return GenerationResult(
                content=content,
                provider=self.provider_name,
                model=target_model,
                usage=TokenUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                ),
                duration_seconds=round(duration, 3),
                finish_reason=data.get("done_reason", "stop"),
                raw_response={"done_reason": data.get("done_reason")},
            )
        except Exception as ex:
            raise InvalidResponseError(
                f"Failed to parse Ollama JSON chat response: {ex}",
                provider=self.provider_name,
            ) from ex

    async def generate_embedding(
        self,
        text: str,
        model: Optional[str] = None,
    ) -> EmbeddingResult:
        """
        Computes dense vector embedding for a single text chunk.
        """
        if not text or not text.strip():
            raise InvalidResponseError("Cannot generate embedding for empty or whitespace-only text.", provider=self.provider_name)

        target_model = model or self._embedding_model
        batch_res = await self.generate_embeddings_batch([text], model=target_model)
        if not batch_res:
            raise InvalidResponseError("No embedding vector returned for input text.", provider=self.provider_name)
        return batch_res[0]

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        model: Optional[str] = None,
    ) -> List[EmbeddingResult]:
        """
        Computes dense vector embeddings for a batch of text chunks using POST /api/embed
        (with graceful backward fallback to POST /api/embeddings if /api/embed is 404).
        """
        if not texts:
            return []

        target_model = model or self._embedding_model
        cleaned_texts = [t.strip() for t in texts]

        # Guard against empty entries
        for i, t in enumerate(cleaned_texts):
            if not t:
                raise InvalidResponseError(f"Batch item at index {i} is empty.", provider=self.provider_name)

        endpoint = self._embed_endpoint or "/api/embed"
        payload: Dict[str, Any] = {
            "model": target_model,
            "input": cleaned_texts if len(cleaned_texts) > 1 else cleaned_texts[0],
        }

        try:
            resp = await self._client.post(
                endpoint,
                json=payload,
                params=self._get_auth_params(),
            )
            # Fallback to legacy /api/embeddings endpoint if /api/embed is 404
            if resp.status_code == 404 and endpoint == "/api/embed":
                logger.info("Ollama endpoint /api/embed returned 404; retrying with /api/embeddings")
                legacy_results = []
                for t in cleaned_texts:
                    legacy_resp = await self._client.post(
                        "/api/embeddings",
                        json={"model": target_model, "prompt": t},
                        params=self._get_auth_params(),
                    )
                    if legacy_resp.status_code != 200:
                        raise InvalidResponseError(f"Legacy embeddings endpoint returned HTTP {legacy_resp.status_code}", provider=self.provider_name)
                    legacy_data = legacy_resp.json()
                    vec = legacy_data.get("embedding", [])
                    self._validate_vector_values(vec, "legacy single vector")
                    legacy_results.append(
                        EmbeddingResult(
                            embedding=vec,
                            provider=self.provider_name,
                            model=target_model,
                            dimension=len(vec),
                        )
                    )
                return legacy_results

        except httpx.ConnectTimeout as ct:
            raise ProviderTimeoutError(
                f"Embedding request connection timed out after {self._connect_timeout_seconds}s.",
                provider=self.provider_name,
            ) from ct
        except httpx.ReadTimeout as rt:
            raise ProviderTimeoutError(
                f"Ollama embedding computation timed out after {self._timeout_seconds}s.",
                provider=self.provider_name,
            ) from rt
        except httpx.ConnectError as ce:
            raise ProviderConnectionError(
                f"Ollama server is unavailable at {self._base_url}.",
                provider=self.provider_name,
            ) from ce
        except Exception as ex:
            if isinstance(ex, (InvalidResponseError, ProviderAuthenticationError, ModelNotFoundError, ProviderServerError)):
                raise
            raise ProviderConnectionError(
                f"Network failure during Ollama embedding: {type(ex).__name__}",
                provider=self.provider_name,
            ) from ex

        if resp.status_code in (401, 403):
            raise ProviderAuthenticationError(
                f"Ollama embedding authentication failed (HTTP {resp.status_code}).",
                provider=self.provider_name,
                status_code=resp.status_code,
            )
        elif resp.status_code == 404:
            raise ModelNotFoundError(
                f"Embedding model '{target_model}' was not found in Ollama.",
                provider=self.provider_name,
            )
        elif 500 <= resp.status_code < 600:
            raise ProviderServerError(
                f"Ollama embedding server error (HTTP {resp.status_code}): {self._sanitize_error_text(resp.text)}",
                provider=self.provider_name,
                status_code=resp.status_code,
            )
        elif resp.status_code != 200:
            raise InvalidResponseError(
                f"Ollama embedding failed with HTTP {resp.status_code}: {self._sanitize_error_text(resp.text)}",
                provider=self.provider_name,
            )

        try:
            data = resp.json()
            raw_embeddings = data.get("embeddings")

            # If response returned single 'embedding' key instead of 'embeddings' list
            if raw_embeddings is None and "embedding" in data:
                raw_embeddings = [data["embedding"]]

            if not raw_embeddings or not isinstance(raw_embeddings, list):
                raise InvalidResponseError("Ollama returned empty or missing embeddings list.", provider=self.provider_name)

            if len(raw_embeddings) != len(cleaned_texts):
                raise InvalidResponseError(
                    f"Mismatch between input count ({len(cleaned_texts)}) and returned embeddings ({len(raw_embeddings)}).",
                    provider=self.provider_name,
                )

            expected_dim: Optional[int] = None
            results: List[EmbeddingResult] = []

            for i, vec in enumerate(raw_embeddings):
                self._validate_vector_values(vec, f"chunk_{i}")
                dim = len(vec)
                if expected_dim is None:
                    expected_dim = dim
                elif dim != expected_dim:
                    raise InvalidResponseError(
                        f"Inconsistent vector dimensions in batch: expected {expected_dim}, got {dim} at index {i}.",
                        provider=self.provider_name,
                    )

                results.append(
                    EmbeddingResult(
                        embedding=vec,
                        provider=self.provider_name,
                        model=target_model,
                        dimension=dim,
                    )
                )

            return results

        except Exception as ex:
            if isinstance(ex, (InvalidResponseError, ProviderAuthenticationError, ModelNotFoundError, ProviderServerError)):
                raise
            raise InvalidResponseError(
                f"Failed to parse Ollama embedding response: {ex}",
                provider=self.provider_name,
            ) from ex
