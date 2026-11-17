import json
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized application settings using Pydantic Settings."""

    # Application Information
    APP_NAME: str = "RepoMind"
    APP_VERSION: str = "0.1.0"
    APP_TAGLINE: str = "Understand any codebase. Trace every connection. Explain every flow."
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "127.0.0.1"

    # URLs & CORS
    BACKEND_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:5173"
    ALLOWED_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    # Database Configuration
    # Uses asyncpg for PostgreSQL (including Supabase), or aiosqlite for local testing
    DATABASE_URL: str = "sqlite+aiosqlite:///./repomind.db"
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    # Supabase Specific Configuration (Phase 8)
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # Security & Authentication (JWT)
    JWT_SECRET: str = "repomind-super-secret-development-key-change-in-production-min-32-chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Logging
    LOG_LEVEL: str = "INFO"

    # Workspace & Storage Configuration
    STORAGE_DIR: str = "./storage"
    MAX_UPLOAD_SIZE_BYTES: int = 52428800  # 50 MB
    MAX_UNCOMPRESSED_SIZE_BYTES: int = 262144000  # 250 MB
    MAX_EXTRACT_FILE_COUNT: int = 10000

    # GitHub Integration
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_TOKEN_ENCRYPTION_KEY: str = ""  # If empty, derived safely from JWT_SECRET

    # File Discovery Exclusions
    DEFAULT_IGNORE_DIRS: List[str] = [
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        "dist",
        "build",
        ".next",
        "coverage",
        ".pytest_cache",
        ".idea",
        ".vscode",
    ]

    # AI & LLM Provider Configuration (Phase 5)
    AI_PRIMARY_PROVIDER: str = "ollama"  # "ollama" | "gemini"
    AI_FALLBACK_PROVIDER: str = "gemini"  # "gemini" | "none"

    # Ollama Configuration (Local dev default: http://localhost:11434; Production on InstaBox)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    PRODUCTION_OLLAMA_BASE_URL: str = ""
    OLLAMA_CHAT_ENDPOINT: str = "/api/chat"
    OLLAMA_EMBED_ENDPOINT: str = "/api/embed"
    OLLAMA_PORT: int = 11434
    OLLAMA_AUTH_REQUIRED: bool = False
    OLLAMA_ACCESS_TOKEN: str = ""  # Private port token (e.g. ibp_...)
    OLLAMA_API_KEY: str = ""       # Legacy or alternate bearer key
    OLLAMA_GENERATION_MODEL: str = "qwen3.5:4b"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    OLLAMA_CONTEXT_WINDOW: int = 4096  # Bounded context window for CPU-constrained InstaBox
    OLLAMA_TIMEOUT_SECONDS: float = 60.0
    OLLAMA_CONNECT_TIMEOUT_SECONDS: float = 10.0
    OLLAMA_MAX_RETRIES: int = 2

    # Gemini Fallback Configuration (Free Tier Only)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"
    GEMINI_ALLOW_CLOUD_FALLBACK: bool = True
    GEMINI_TIMEOUT_SECONDS: float = 30.0

    @property
    def effective_database_url(self) -> str:
        """
        Returns a normalized database URL compatible with SQLAlchemy 2.0 Async (asyncpg).
        Normalizes 'postgres://' or 'postgresql://' prefixes to 'postgresql+asyncpg://'.
        Preserves SQLite URLs and already-specified async driver schemes.
        """
        url = (self.DATABASE_URL or "").strip()
        if url.startswith("postgresql://"):
            return "postgresql+asyncpg://" + url[len("postgresql://"):]
        elif url.startswith("postgres://"):
            return "postgresql+asyncpg://" + url[len("postgres://"):]
        return url

    @property
    def effective_ollama_base_url(self) -> str:
        """Returns the appropriate Ollama base URL depending on deployment environment."""
        if self.APP_ENV == "production" and self.PRODUCTION_OLLAMA_BASE_URL.strip():
            return self.PRODUCTION_OLLAMA_BASE_URL.strip().rstrip("/")
        return self.OLLAMA_BASE_URL.strip().rstrip("/")

    @property
    def effective_ollama_access_token(self) -> str:
        """Returns the access token for InstaBox private port or reverse proxy."""
        return (self.OLLAMA_ACCESS_TOKEN or self.OLLAMA_API_KEY).strip()

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, str) and v.startswith("["):
            try:
                return json.loads(v)
            except Exception:
                return [v]
        elif isinstance(v, list):
            return v
        return []

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
