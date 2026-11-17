from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ProviderType(str, Enum):
    OLLAMA = "ollama"
    GEMINI = "gemini"


class HealthStatus(str, Enum):
    CONNECTED = "connected"
    AUTHENTICATION_FAILED = "authentication_failed"
    SERVER_UNAVAILABLE = "server_unavailable"
    REQUEST_TIMED_OUT = "request_timed_out"
    GENERATION_MODEL_MISSING = "generation_model_missing"
    EMBEDDING_MODEL_MISSING = "embedding_model_missing"
    INVALID_RESPONSE = "invalid_response"
    UNKNOWN_FAILURE = "unknown_failure"


@dataclass
class ChatMessage:
    role: str  # "system", "user", "assistant"
    content: str

    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class GenerationResult:
    content: str
    provider: str
    model: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    duration_seconds: float = 0.0
    finish_reason: Optional[str] = "stop"
    raw_response: Optional[Dict[str, Any]] = None


@dataclass
class EmbeddingResult:
    embedding: List[float]
    provider: str
    model: str
    dimension: int


@dataclass
class BatchEmbeddingResult:
    embeddings: List[List[float]]
    provider: str
    model: str
    dimension: int
    total_chunks: int


@dataclass
class ProviderHealth:
    provider: str
    is_available: bool
    status: HealthStatus = HealthStatus.CONNECTED
    has_generation_model: bool = False
    has_embedding_model: bool = False
    latency_ms: float = 0.0
    error_message: Optional[str] = None
    available_models: List[str] = field(default_factory=list)
