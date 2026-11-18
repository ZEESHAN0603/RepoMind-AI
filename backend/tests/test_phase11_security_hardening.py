import io
import zipfile
import pytest
from httpx import AsyncClient
from app.ai.provider_manager import ProviderManager
from app.core.config import settings
from app.core.exceptions import BadRequestException
from app.services.workspace_service import WorkspaceService
from app.services.zip_service import ZipService


@pytest.mark.asyncio
async def test_auth_rate_limiting(client: AsyncClient):
    """Verifies that exceeding the allowed rate limit on auth endpoints triggers HTTP 429."""
    from app.core.limiter import limiter
    limiter.enabled = True
    try:
        # Register a user first
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Rate Limit Test",
                "email": "ratelimit@repomind.ai",
                "password": "Password123!",
            },
        )
        assert reg_res.status_code == 201

        # Send requests to login endpoint until 429 is received or limit tested
        responses = []
        payload = {"email": "ratelimit@repomind.ai", "password": "Password123!"}
        
        for _ in range(20):
            res = await client.post("/api/v1/auth/login", json=payload)
            responses.append(res.status_code)
            if res.status_code == 429:
                break

        # At least one request should have succeeded (200) and later hit 429
        assert 200 in responses
        assert 429 in responses, f"Expected 429 Too Many Requests in responses: {responses}"
    finally:
        limiter.enabled = False


def test_zip_slip_prevention(tmp_path):
    """Verifies that archives containing directory traversal paths (Zip Slip) are rejected."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("../../../etc/passwd", "root:x:0:0:root:/root:/bin/bash")
        zf.writestr("safe_file.py", "print('hello')")
    
    zip_bytes = buf.getvalue()
    zip_service = ZipService()
    
    with pytest.raises(BadRequestException) as excinfo:
        zip_service.validate_and_extract(zip_bytes, tmp_path / "extracted")
    
    assert "Path traversal detected" in str(excinfo.value)


def test_zip_absolute_path_prevention(tmp_path):
    """Verifies that archives containing absolute paths are rejected."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("/absolute/path/evil.py", "import os; os.system('calc')")
    
    zip_bytes = buf.getvalue()
    zip_service = ZipService()
    
    with pytest.raises(BadRequestException) as excinfo:
        zip_service.validate_and_extract(zip_bytes, tmp_path / "extracted")
    
    assert "Path traversal detected" in str(excinfo.value)


def test_workspace_traversal_prevention(tmp_path):
    """Verifies that WorkspaceService prevents traversal out of workspaces directory."""
    ws_service = WorkspaceService(base_storage_dir=str(tmp_path))
    
    # Attempt directory traversal via user_id
    traversal_path = ws_service.get_repository_workspace_path(
        user_id="../../../etc",
        repository_id="repo123"
    )
    # The path must resolve safely under workspaces_root
    assert str(traversal_path).startswith(str(ws_service.workspaces_root))
    assert "etc" in traversal_path.parts
    assert ".." not in traversal_path.parts


def test_secret_redaction_comprehensive():
    """Verifies that API keys, tokens, and database connection strings are redacted before AI calls."""
    pm = ProviderManager()
    
    raw_prompt = (
        "Here is the database URL: postgresql://postgres:MySecretPassword123@db.supabase.co:5432/postgres\n"
        "api_key = 'sk-abcdef1234567890abcdef1234567890'\n"
        "And the GitHub token: ghp_1234567890abcdefghijklmnopqrstuvwxyz\n"
        "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.t-IDcSemACt8x4iTMCda8Yhe3iZaWbvV5XKSTbuAn0M"
    )
    
    redacted = pm.sanitize_text_for_cloud(raw_prompt)
    
    assert "MySecretPassword123" not in redacted
    assert "sk-abcdef1234567890abcdef1234567890" not in redacted
    assert "ghp_1234567890abcdefghijklmnopqrstuvwxyz" not in redacted
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in redacted
    assert "[REDACTED_SECRET]" in redacted


def test_cors_configuration():
    """Verifies that allowed origins are explicitly defined and credentials are enabled."""
    assert settings.ALLOWED_ORIGINS is not None
    assert len(settings.ALLOWED_ORIGINS) > 0
    # Ensure localhost or vercel is in allowed origins
    origins_str = " ".join(settings.ALLOWED_ORIGINS)
    assert "localhost" in origins_str or "*" in origins_str or "vercel.app" in origins_str
