from enum import Enum
from typing import Optional


class ProviderErrorCategory(str, Enum):
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    CONNECTION_ERROR = "CONNECTION_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    RATE_LIMITED = "RATE_LIMITED"
    SERVER_ERROR = "SERVER_ERROR"
    UNKNOWN_PROVIDER_ERROR = "UNKNOWN_PROVIDER_ERROR"


class AIProviderError(Exception):
    """Base exception for all AI provider operations."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        category: ProviderErrorCategory = ProviderErrorCategory.UNKNOWN_PROVIDER_ERROR,
        status_code: Optional[int] = None,
        is_recoverable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.category = category
        self.status_code = status_code
        self.is_recoverable = is_recoverable

    def __str__(self) -> str:
        prov = f"[{self.provider}] " if self.provider else ""
        return f"{prov}({self.category.value}): {self.message}"


class ProviderAuthenticationError(AIProviderError):
    """Raised when authentication fails (HTTP 401 / 403 on InstaBox or provider API)."""

    def __init__(self, message: str, provider: Optional[str] = None, status_code: int = 401) -> None:
        super().__init__(
            message=message,
            provider=provider,
            category=ProviderErrorCategory.AUTHENTICATION_ERROR,
            status_code=status_code,
            is_recoverable=False,  # Bad credentials cannot be recovered automatically
        )


class ProviderConnectionError(AIProviderError):
    """Raised when connection cannot be established (host unreachable, machine paused)."""

    def __init__(self, message: str, provider: Optional[str] = None) -> None:
        super().__init__(
            message=message,
            provider=provider,
            category=ProviderErrorCategory.CONNECTION_ERROR,
            is_recoverable=True,  # Transient network/machine sleep can fall back
        )


class ProviderTimeoutError(AIProviderError):
    """Raised when request or connect times out."""

    def __init__(self, message: str, provider: Optional[str] = None) -> None:
        super().__init__(
            message=message,
            provider=provider,
            category=ProviderErrorCategory.TIMEOUT_ERROR,
            is_recoverable=True,
        )


class ModelNotFoundError(AIProviderError):
    """Raised when target model is not installed or available (HTTP 404)."""

    def __init__(self, message: str, provider: Optional[str] = None) -> None:
        super().__init__(
            message=message,
            provider=provider,
            category=ProviderErrorCategory.MODEL_NOT_FOUND,
            status_code=404,
            is_recoverable=False,
        )


class InvalidResponseError(AIProviderError):
    """Raised when provider returns unparseable, malformed, or non-finite vector data."""

    def __init__(self, message: str, provider: Optional[str] = None) -> None:
        super().__init__(
            message=message,
            provider=provider,
            category=ProviderErrorCategory.INVALID_RESPONSE,
            is_recoverable=False,
        )


class RateLimitedError(AIProviderError):
    """Raised when rate limit or quota is exceeded (HTTP 429)."""

    def __init__(self, message: str, provider: Optional[str] = None) -> None:
        super().__init__(
            message=message,
            provider=provider,
            category=ProviderErrorCategory.RATE_LIMITED,
            status_code=429,
            is_recoverable=True,
        )


class ProviderServerError(AIProviderError):
    """Raised when provider returns HTTP 5xx internal server error."""

    def __init__(self, message: str, provider: Optional[str] = None, status_code: int = 500) -> None:
        super().__init__(
            message=message,
            provider=provider,
            category=ProviderErrorCategory.SERVER_ERROR,
            status_code=status_code,
            is_recoverable=True,
        )


class ContextLengthExceededError(AIProviderError):
    """Raised when prompt tokens exceed model context limit."""

    def __init__(self, message: str, provider: Optional[str] = None) -> None:
        super().__init__(
            message=message,
            provider=provider,
            category=ProviderErrorCategory.INVALID_RESPONSE,
            is_recoverable=False,
        )


# Backward-compatibility aliases for Milestone 5.2
ProviderUnavailableError = ProviderConnectionError
QuotaExceededError = RateLimitedError
ProviderResponseError = InvalidResponseError
UnknownProviderError = AIProviderError
