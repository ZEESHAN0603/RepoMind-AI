from abc import ABC, abstractmethod
from typing import List, Optional

from app.ai.schemas import ChatMessage, EmbeddingResult, GenerationResult, ProviderHealth


class BaseLLMProvider(ABC):
    """Abstract interface defining required capabilities for any generation/embedding provider."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Identifier for the provider (e.g. 'ollama', 'gemini')."""
        pass

    @abstractmethod
    async def generate_chat(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
    ) -> GenerationResult:
        """Executes a chat completion request and returns standardized GenerationResult."""
        pass

    @abstractmethod
    async def generate_embedding(
        self,
        text: str,
        model: Optional[str] = None,
    ) -> EmbeddingResult:
        """Computes dense vector embeddings for input text."""
        pass

    @abstractmethod
    async def generate_embeddings_batch(
        self,
        texts: List[str],
        model: Optional[str] = None,
    ) -> List[EmbeddingResult]:
        """Computes dense vector embeddings for a batch of input texts."""
        pass

    @abstractmethod
    async def check_health(self) -> ProviderHealth:
        """Verifies server connectivity, measures latency, and discovers available models."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Releases underlying HTTP client connection resources."""
        pass
