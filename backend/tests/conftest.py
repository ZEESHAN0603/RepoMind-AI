from typing import AsyncGenerator
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # Ensure all models are registered on Base.metadata
from app.db.base import Base
import app.db.session as session_module
import app.services.ingestion_service as ingestion_service_module
from app.db.session import get_db
from app.main import app

# In-memory SQLite engine isolated for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)

# Monkeypatch session maker for background task workers in tests
session_module.async_session_maker = TestingSessionLocal
ingestion_service_module.async_session_maker = TestingSessionLocal

# Disable rate limiter by default in test suite to prevent IP-level exhaustion across tests
from app.core.limiter import limiter
limiter.enabled = False


@pytest_asyncio.fixture(scope="function", autouse=True)
def mock_github_service(monkeypatch):
    """Mocks GitHub API calls to prevent external network requests during tests."""
    import io
    import zipfile
    from pathlib import Path
    from app.services.github_service import GitHubService

    def create_dummy_zip_bytes() -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("repo-main/README.md", "# Test Repo\nSample codebase for tests.")
            zf.writestr("repo-main/main.py", "from fastapi import FastAPI\napp = FastAPI()\n")
            zf.writestr("repo-main/requirements.txt", "fastapi>=0.100.0\npytest>=8.0.0\n")
            zf.writestr("repo-main/package.json", '{"name": "test-repo", "dependencies": {"react": "^18.0.0"}}')
        return buf.getvalue()

    async def mock_download_archive(owner, repo, branch, destination_zip_path, access_token=None):
        destination_zip_path = Path(destination_zip_path)
        destination_zip_path.parent.mkdir(parents=True, exist_ok=True)
        with open(destination_zip_path, "wb") as f:
            f.write(create_dummy_zip_bytes())
        return destination_zip_path

    async def mock_get_metadata(owner, repo, access_token=None):
        return {
            "name": repo,
            "owner": owner,
            "full_name": f"{owner}/{repo}",
            "default_branch": "master",
            "visibility": "public",
            "is_private": False,
            "is_archived": False,
            "description": "Mocked test repository",
            "size_kb": 128,
            "html_url": f"https://github.com/{owner}/{repo}",
        }

    async def mock_get_branches(owner, repo, access_token=None):
        return [
            {"name": "main", "commit_sha": "1111111111111111111111111111111111111111"},
            {"name": "master", "commit_sha": "2222222222222222222222222222222222222222"},
        ]

    async def mock_get_commit_sha(owner, repo, branch, access_token=None):
        return "2222222222222222222222222222222222222222"

    monkeypatch.setattr(GitHubService, "download_archive", mock_download_archive)
    monkeypatch.setattr(GitHubService, "get_repository_metadata", mock_get_metadata)
    monkeypatch.setattr(GitHubService, "get_repository_branches", mock_get_branches)
    monkeypatch.setattr(GitHubService, "get_latest_commit_sha", mock_get_commit_sha)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def prepare_database():
    """Create all database tables before each test and drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides a fresh transactional session for each test function."""
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Test client overriding the get_db dependency with test database session."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
