from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.ai.provider_manager import ProviderManager
from app.core.config import settings
from app.db.session import check_db_health

router = APIRouter()
provider_manager = ProviderManager()


class HealthCheckResponse(BaseModel):
    status: str
    app: str
    version: str
    environment: str
    database: str


class ProviderStatusItem(BaseModel):
    provider: str
    status: str
    is_available: bool
    latency_ms: float
    error_message: Optional[str] = None
    available_models: List[str] = []


class AIProvidersHealthResponse(BaseModel):
    primary_provider: str
    fallback_provider: str
    providers: Dict[str, ProviderStatusItem]


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="API v1 Health Check",
    description="Check the operational status of the RepoMind v1 API and database.",
)
async def api_v1_health(response: Response) -> HealthCheckResponse:
    db_ok = await check_db_health()
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthCheckResponse(
        status="healthy" if db_ok else "degraded",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        database="connected" if db_ok else "disconnected",
    )


@router.get(
    "/health/ai-providers",
    response_model=AIProvidersHealthResponse,
    summary="AI Providers Health Check",
    description="Inspect connectivity, latency, and model availability for primary (Ollama) and fallback (Gemini) providers without exposing credentials.",
)
async def ai_providers_health() -> AIProvidersHealthResponse:
    health_dict = await provider_manager.check_health()
    items = {
        name: ProviderStatusItem(
            provider=h.provider,
            status=getattr(h, "status", "connected"),
            is_available=h.is_available,
            latency_ms=h.latency_ms,
            error_message=h.error_message,
            available_models=h.available_models,
        )
        for name, h in health_dict.items()
    }
    return AIProvidersHealthResponse(
        primary_provider=settings.AI_PRIMARY_PROVIDER,
        fallback_provider=settings.AI_FALLBACK_PROVIDER,
        providers=items,
    )
