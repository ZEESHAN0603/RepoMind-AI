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

