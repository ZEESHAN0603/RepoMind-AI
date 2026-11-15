from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.logging import logger

# Configure engine arguments depending on DB dialect
engine_kwargs = {
    "echo": settings.DB_ECHO,
    "future": True,
}

if "sqlite" in settings.DATABASE_URL:
    # SQLite requires check_same_thread=False
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    engine_kwargs["poolclass"] = NullPool
else:
    # PostgreSQL connection pooling
    engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
    engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
    engine_kwargs["pool_pre_ping"] = True

engine: AsyncEngine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency provider for request-scoped database sessions."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception as ex:
            await session.rollback()
            logger.error("Database transaction rolled back due to error: %s", ex)
            raise
        finally:
            await session.close()


async def check_db_health() -> bool:
    """Performs a lightweight query to verify database connectivity."""
    try:
        async with async_session_maker() as session:
            result = await session.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as ex:
        logger.warning("Database health check failed: %s", ex)
        return False

