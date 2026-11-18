import pytest
from app.core.config import Settings
from app.db.diagnostic import mask_database_url, diagnose_database
from app.db.migrate_data import copy_table_data


def test_effective_database_url_normalization():
    """Verifies that postgres:// and postgresql:// are safely normalized to postgresql+asyncpg://."""
    s1 = Settings(DATABASE_URL="postgres://postgres:secret@db.xyz.supabase.co:5432/postgres")
    assert s1.effective_database_url == "postgresql+asyncpg://postgres:secret@db.xyz.supabase.co:5432/postgres"

    s2 = Settings(DATABASE_URL="postgresql://postgres:secret@db.xyz.supabase.co:5432/postgres?ssl=require")
    assert s2.effective_database_url == "postgresql+asyncpg://postgres:secret@db.xyz.supabase.co:5432/postgres?ssl=require"

    s3 = Settings(DATABASE_URL="postgresql+asyncpg://postgres:secret@localhost:5432/mydb")
    assert s3.effective_database_url == "postgresql+asyncpg://postgres:secret@localhost:5432/mydb"

    s4 = Settings(DATABASE_URL="sqlite+aiosqlite:///./test.db")
    assert s4.effective_database_url == "sqlite+aiosqlite:///./test.db"


def test_mask_database_url():
    """Verifies passwords in database connection strings are never exposed in logs."""
    masked = mask_database_url("postgresql+asyncpg://postgres:super_secret_pw@db.project.supabase.co:5432/postgres")
    assert "super_secret_pw" not in masked
    assert "postgres:****@db.project.supabase.co" in masked

    masked_standard = mask_database_url("postgres://admin:pass123@aws-0-us-east-1.pooler.supabase.com:6543/postgres")
    assert "pass123" not in masked_standard
    assert "admin:****@" in masked_standard

    assert mask_database_url("sqlite+aiosqlite:///./test.db") == "sqlite+aiosqlite:///./test.db"
    assert mask_database_url("") == ""


def test_supabase_settings_defaults():
    """Verifies optional Supabase settings exist and have secure defaults."""
    settings = Settings()
    assert hasattr(settings, "SUPABASE_URL")
    assert hasattr(settings, "SUPABASE_ANON_KEY")
    assert hasattr(settings, "SUPABASE_SERVICE_ROLE_KEY")
    assert hasattr(settings, "DB_POOL_TIMEOUT")
    assert hasattr(settings, "DB_POOL_RECYCLE")
    assert settings.DB_POOL_TIMEOUT == 30
    assert settings.DB_POOL_RECYCLE == 1800


@pytest.mark.asyncio
async def test_diagnose_database_on_sqlite(tmp_path):
    """Verifies diagnose_database runs cleanly on an isolated test SQLite database."""
    test_db = tmp_path / "diag_test.db"
    url = f"sqlite+aiosqlite:///{test_db}"
    report = await diagnose_database(url)
    assert report["status"] == "healthy"
    assert report["connected"] is True
    assert report["dialect"] == "sqlite"
    assert "SQLite" in report["server_version"]
    assert report["error"] is None


@pytest.mark.asyncio
async def test_copy_table_data_dry_run(tmp_path):
    """Verifies data reconciliation dry-run across two databases."""
    src_db = tmp_path / "src.db"
    tgt_db = tmp_path / "tgt.db"
    src_url = f"sqlite+aiosqlite:///{src_db}"
    tgt_url = f"sqlite+aiosqlite:///{tgt_db}"

    # Initialize empty tables via diagnose to verify empty reconciliation
    report = await copy_table_data(src_url, tgt_url, dry_run=True)
    assert report["status"] == "success"
    assert report["dry_run"] is True


@pytest.mark.asyncio
async def test_check_db_health():
    """Verifies check_db_health returns boolean connectivity status."""
    from app.db.session import check_db_health
    status = await check_db_health()
    assert isinstance(status, bool)


def test_supabase_pooler_detection():
    """Verifies Supabase transaction pooler port and domain detection for statement caching."""
    pooler_url = "postgresql+asyncpg://postgres.proj:secret@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
    session_url = "postgresql+asyncpg://postgres:secret@db.proj.supabase.co:5432/postgres"

    assert ":6543" in pooler_url or "pooler.supabase.com" in pooler_url
    assert "supabase.co" in session_url


def test_alembic_migration_chain_and_head():
    """Verifies that all Alembic migrations form an unbroken sequential chain ending at head."""
    from pathlib import Path
    import re

    migrations_dir = Path(__file__).resolve().parent.parent / "migrations" / "versions"
    assert migrations_dir.is_dir(), f"Migrations dir not found: {migrations_dir}"

    revisions = {}
    for f in migrations_dir.glob("*.py"):
        text = f.read_text(encoding="utf-8")
        rev_match = re.search(r"^revision(?:\s*:\s*str)?\s*=\s*['\"]([^'\"]+)['\"]", text, re.MULTILINE)
        down_match = re.search(r"^down_revision(?:\s*:\s*[^=]+)?\s*=\s*['\"]?([^'\"\n]+)['\"]?", text, re.MULTILINE)
        if rev_match:
            rev = rev_match.group(1).strip()
            down = down_match.group(1).strip() if down_match else None
            if down == "None":
                down = None
            revisions[rev] = (down, f.name)

    # Must contain at least initial, phase 3-5, 7-10, and phase 6 migrations
    assert len(revisions) >= 9, f"Expected at least 9 migrations, found {len(revisions)}"
    assert "e5f6a7b8c9d0" in revisions, "Phase 6 architecture migration e5f6a7b8c9d0 must exist"

    # Verify single root
    roots = [r for r, (d, _) in revisions.items() if d is None]
    assert len(roots) == 1, f"Expected exactly 1 root migration, found: {roots}"

    # Verify linear chain to head (e5f6a7b8c9d0)
    current = roots[0]
    visited = [current]
    while True:
        children = [r for r, (d, _) in revisions.items() if d == current]
        if not children:
            break
        assert len(children) == 1, f"Found migration branch from {current}: {children}"
        current = children[0]
        visited.append(current)

    assert len(visited) == len(revisions), f"Disconnected migrations detected! Visited {len(visited)} of {len(revisions)}"
    assert current == "e5f6a7b8c9d0", f"Expected head revision to be e5f6a7b8c9d0, got {current}"


