import asyncio
import os
import re
from typing import Any, Dict, List, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.core.logging import logger


def mask_database_url(url: str) -> str:
    """Masks database password in connection string for safe logging and output."""
    if not url:
        return ""
    # Matches :password@ in connection URLs
    return re.sub(r":([^@/]+)@", r":****@", url)


async def diagnose_database(target_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Performs a non-destructive diagnostic connectivity check against a database.
    Verifies connection handshake, engine dialect, server version, and table discovery.
    """
    raw_url = target_url or settings.effective_database_url
    # Ensure async driver normalization
    if raw_url.startswith("postgresql://"):
        raw_url = "postgresql+asyncpg://" + raw_url[len("postgresql://"):]
    elif raw_url.startswith("postgres://"):
        raw_url = "postgresql+asyncpg://" + raw_url[len("postgres://"):]

    masked_url = mask_database_url(raw_url)
    dialect = "sqlite" if "sqlite" in raw_url else "postgresql"

    engine_kwargs: Dict[str, Any] = {"echo": False, "future": True}
    if dialect == "sqlite":
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    else:
        engine_kwargs["pool_pre_ping"] = True
        engine_kwargs["pool_timeout"] = 15
        diag_connect_args: Dict[str, Any] = {}
        if ":6543" in raw_url or "pooler.supabase.com" in raw_url:
            diag_connect_args["statement_cache_size"] = 0
            diag_connect_args["prepared_statement_cache_size"] = 0
        if "supabase.co" in raw_url or "pooler.supabase.com" in raw_url:
            diag_connect_args.setdefault("ssl", "require")
        if diag_connect_args:
            engine_kwargs["connect_args"] = diag_connect_args

    engine = create_async_engine(raw_url, **engine_kwargs)

    report: Dict[str, Any] = {
        "status": "pending",
        "url": masked_url,
        "dialect": dialect,
        "is_supabase": "supabase.co" in raw_url or "pooler.supabase.com" in raw_url,
        "connected": False,
        "server_version": None,
        "tables": [],
        "alembic_version": None,
        "error": None,
    }

    try:
        async with engine.connect() as conn:
            # 1. Handshake check
            handshake = await conn.execute(text("SELECT 1"))
            if handshake.scalar() != 1:
                raise RuntimeError("Handshake query did not return 1")
            report["connected"] = True

            # 2. Version check
            if dialect == "sqlite":
                ver_res = await conn.execute(text("SELECT sqlite_version()"))
                report["server_version"] = f"SQLite {ver_res.scalar()}"
                tbl_query = text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            else:
                ver_res = await conn.execute(text("SELECT version()"))
                report["server_version"] = str(ver_res.scalar())
                tbl_query = text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public' ORDER BY table_name"
                )

            # 3. Tables check
            tbl_res = await conn.execute(tbl_query)
            tables = [row[0] for row in tbl_res.fetchall()]
            report["tables"] = tables

            # 4. Alembic version
            if "alembic_version" in tables:
                alem_res = await conn.execute(text("SELECT version_num FROM alembic_version"))
                rows = alem_res.fetchall()
                report["alembic_version"] = [r[0] for r in rows] if rows else None

            report["status"] = "healthy"

    except Exception as ex:
        report["status"] = "failed"
        report["error"] = str(ex)
        logger.error("Database diagnostic failed for %s: %s", masked_url, ex)
    finally:
        await engine.dispose()

    return report


if __name__ == "__main__":
    url_to_test = os.environ.get("DIAGNOSTIC_DB_URL") or None
    result = asyncio.run(diagnose_database(url_to_test))
    print("\n--- RepoMind Database Diagnostic Report ---")
    for key, val in result.items():
        print(f"  {key}: {val}")
