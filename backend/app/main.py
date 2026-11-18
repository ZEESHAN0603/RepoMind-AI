from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.error_handlers import register_exception_handlers
from app.core.limiter import limiter
from app.core.logging import logger, setup_logging
from app.core.middleware import RequestCorrelationMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import app.models  # Ensure all models are registered on Base.metadata
from app.db.base import Base
from app.db.session import check_db_health, engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle management."""
    setup_logging(settings.LOG_LEVEL)
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} ({settings.APP_ENV})")

    # Verify or initialize database schema
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        db_connected = await check_db_health()
        if db_connected:
            logger.info("Database connectivity established successfully.")
        else:
            logger.warning("Database connectivity check returned false.")
    except Exception as ex:
        logger.error(f"Error initializing database connection during startup: {ex}")

    yield

    logger.info(f"Shutting down {settings.APP_NAME}...")
    await engine.dispose()
    logger.info("Database connections closed.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Backend API for RepoMind — AI-Powered Repository Intelligence Platform.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Attach rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Correlation ID and Request Logging Middleware
app.add_middleware(RequestCorrelationMiddleware)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handlers
register_exception_handlers(app)

# Include API v1 router
app.include_router(api_v1_router, prefix="/api/v1")


class RootInfoResponse(BaseModel):
    app: str
    tagline: str
    version: str
    status: str
    docs_url: str
    api_v1_url: str


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str


@app.get(
    "/",
    response_model=RootInfoResponse,
    summary="Application Information",
    description="Returns metadata about the RepoMind backend application.",
    tags=["General"],
)
async def root() -> RootInfoResponse:
    return RootInfoResponse(
        app=settings.APP_NAME,
        tagline=settings.APP_TAGLINE,
        version=settings.APP_VERSION,
        status="running",
        docs_url="/docs",
        api_v1_url="/api/v1",
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Root Health Check",
    description="Confirms that the RepoMind backend service is active.",
    tags=["Health"],
)
async def health() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
    )
