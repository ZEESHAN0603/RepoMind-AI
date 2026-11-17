import pytest
from unittest.mock import AsyncMock, MagicMock

from app.models.code_symbol import CodeSymbol
from app.models.repository_file import RepositoryFile
from app.services.chunking_service import ChunkingService, CodeChunkData


def test_should_index_file_exclusions():
    """Verifies binaries, lockfiles, and environment secrets are excluded."""
    service = ChunkingService()

    file_valid = RepositoryFile(id="1", repository_id="r1", path="src/main.py", file_type="file", is_binary=False)
    file_env = RepositoryFile(id="2", repository_id="r1", path=".env", file_type="file", is_binary=False)
    file_env_prod = RepositoryFile(id="3", repository_id="r1", path="config/.env.production", file_type="file", is_binary=False)
    file_lock = RepositoryFile(id="4", repository_id="r1", path="package-lock.json", file_type="file", is_binary=False)
    file_png = RepositoryFile(id="5", repository_id="r1", path="assets/logo.png", file_type="file", is_binary=True)

    assert service.should_index_file(file_valid) is True
    assert service.should_index_file(file_env) is False
    assert service.should_index_file(file_env_prod) is False
    assert service.should_index_file(file_lock) is False
    assert service.should_index_file(file_png) is False


@pytest.mark.asyncio
async def test_chunk_content_formatting():
    """Verifies chunk format includes file path, lines, and contextual symbol info."""
    service = ChunkingService()
    formatted = service._format_chunk_content(
        file_path="app/core/security.py",
        start_line=15,
        end_line=30,
        raw_code="def decode_token(token: str) -> dict:\n    return jwt.decode(token)",
        symbol_name="decode_token",
        symbol_type="function",
        scope="security",
        imports_summary="pyjwt, argon2",
    )

    assert "File: app/core/security.py" in formatted
    assert "Lines: 15-30" in formatted
    assert "function: decode_token" in formatted
    assert "Scope: security" in formatted
    assert "Contextual Imports: pyjwt, argon2" in formatted
    assert "def decode_token" in formatted
