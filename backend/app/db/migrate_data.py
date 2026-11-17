import argparse
import asyncio
from typing import Any, Dict, List
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.diagnostic import mask_database_url
from app.core.logging import logger

# Strictly ordered to satisfy foreign key constraints during copy
MIGRATION_TABLE_ORDER: List[str] = [
    "users",
    "refresh_tokens",
    "repositories",
    "github_connections",
    "repository_branches",
    "repository_files",
    "repository_languages",
    "repository_manifests",
    "repository_ingestion_jobs",
    "code_symbols",
    "code_imports_exports",
    "api_route_endpoints",
    "code_chunks",
    "code_calls",
    "execution_entry_points",
    "code_dependencies",
    "architecture_snapshots",
    "execution_snapshots",
    "dependency_snapshots",
    "chat_conversations",
    "chat_messages",
]


def _normalize_driver(url: str) -> str:
    url = url.strip()
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://"):]
    elif url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://"):]
    return url


async def copy_table_data(
    source_url: str,
    target_url: str,
    batch_size: int = 1000,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Safely copies records from source database to target Supabase database
    in strict topological foreign-key order. Reconciles row counts.
    """
    src_norm = _normalize_driver(source_url)
    tgt_norm = _normalize_driver(target_url)

    src_connect_args = {"check_same_thread": False} if "sqlite" in src_norm else {}
    tgt_connect_args = {"check_same_thread": False} if "sqlite" in tgt_norm else {}
    if ":6543" in tgt_norm or "pooler.supabase.com" in tgt_norm:
        tgt_connect_args["statement_cache_size"] = 0
        tgt_connect_args["prepared_statement_cache_size"] = 0
    if "supabase.co" in tgt_norm or "pooler.supabase.com" in tgt_norm:
        tgt_connect_args.setdefault("ssl", "require")

    src_engine = create_async_engine(
        src_norm,
        connect_args=src_connect_args,
        pool_pre_ping=True,
    )
    tgt_engine = create_async_engine(
        tgt_norm,
        connect_args=tgt_connect_args,
        pool_pre_ping=True,
    )

    reconciliation: Dict[str, Dict[str, int]] = {}

    try:
        async with src_engine.connect() as src_conn, tgt_engine.connect() as tgt_conn:
            # Discover existing tables in source
            if "sqlite" in src_norm:
                tbl_check = await src_conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            else:
                tbl_check = await src_conn.execute(
                    text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
                )
            existing_src_tables = set(row[0] for row in tbl_check.fetchall())

            for table_name in MIGRATION_TABLE_ORDER:
                if table_name not in existing_src_tables:
                    continue

                # 1. Fetch count and rows from source
                count_res = await src_conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                src_count = count_res.scalar() or 0

                reconciliation[table_name] = {"source_rows": src_count, "target_rows": 0}

                if src_count == 0:
                    continue

                # 2. Read all column names and rows from source
                rows_res = await src_conn.execute(text(f"SELECT * FROM {table_name}"))
                column_names = list(rows_res.keys())
                rows = rows_res.fetchall()

                if not dry_run and rows:
                    cols_str = ", ".join(column_names)
                    placeholders = ", ".join([f":{col}" for col in column_names])
                    insert_stmt = text(f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})")

                    # Batch insert into target
                    for i in range(0, len(rows), batch_size):
                        batch = [dict(zip(column_names, row)) for row in rows[i : i + batch_size]]
                        await tgt_conn.execute(insert_stmt, batch)
                    await tgt_conn.commit()

                # 3. Check target count
                tgt_count_res = await tgt_conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                reconciliation[table_name]["target_rows"] = tgt_count_res.scalar() or 0

        return {
            "status": "success",
            "dry_run": dry_run,
            "source": mask_database_url(source_url),
            "target": mask_database_url(target_url),
            "reconciliation": reconciliation,
        }
    except Exception as ex:
        logger.error("Data migration failed: %s", ex)
        return {
            "status": "failed",
            "error": str(ex),
            "source": mask_database_url(source_url),
            "target": mask_database_url(target_url),
            "reconciliation": reconciliation,
        }
    finally:
        await src_engine.dispose()
        await tgt_engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RepoMind Database Migration Tool")
    parser.add_argument("--source", required=True, help="Source database URL")
    parser.add_argument("--target", required=True, help="Target Supabase database URL")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without writing")
    args = parser.parse_args()

    result = asyncio.run(copy_table_data(args.source, args.target, dry_run=args.dry_run))
    print("\n--- RepoMind Data Migration Summary ---")
    print(f"Status: {result.get('status')}")
    print(f"Source: {result.get('source')}")
    print(f"Target: {result.get('target')}")
    for tbl, counts in result.get("reconciliation", {}).items():
        print(f"  {tbl}: source={counts['source_rows']}, target={counts['target_rows']}")
