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

db_url = settings.effective_database_url
connect_args = {}

if "sqlite" in db_url:
    # SQLite requires check_same_thread=False (used in isolated unit tests)
    connect_args["check_same_thread"] = False
    engine_kwargs["connect_args"] = connect_args
    engine_kwargs["poolclass"] = NullPool
else:
    # Supabase / PostgreSQL connection pooling
    engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
    engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_recycle"] = settings.DB_POOL_RECYCLE
    engine_kwargs["pool_timeout"] = settings.DB_POOL_TIMEOUT

    # Supabase Transaction Pooler (Port 6543 / Supavisor) requires disabling statement caches
    if ":6543" in db_url or "pooler.supabase.com" in db_url:
        connect_args["statement_cache_size"] = 0
        connect_args["prepared_statement_cache_size"] = 0

    # Ensure secure SSL handshake for remote Supabase connections
    if "supabase.co" in db_url or "pooler.supabase.com" in db_url:
        connect_args.setdefault("ssl", "require")

    if connect_args:
        engine_kwargs["connect_args"] = connect_args

engine: AsyncEngine = create_async_engine(db_url, **engine_kwargs)

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

