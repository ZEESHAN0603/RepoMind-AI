from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
from app.db.session import check_db_health

router = APIRouter()


class HealthCheckResponse(BaseModel):
    status: str
    app: str
    version: str
    environment: str
    database: str


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="API v1 Health Check",
    description="Check the operational status of the RepoMind v1 API and database.",
)
async def api_v1_health() -> HealthCheckResponse:
    db_ok = await check_db_health()
    return HealthCheckResponse(
        status="healthy" if db_ok else "degraded",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        database="connected" if db_ok else "disconnected",
    )
