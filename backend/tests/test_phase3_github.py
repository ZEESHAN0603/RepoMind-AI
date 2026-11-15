import pytest
from httpx import AsyncClient

from app.core.crypto import decrypt_secret, encrypt_secret
from app.services.github_service import GitHubService


def test_github_url_parsing():
    # Valid HTTPS variants
    owner, repo = GitHubService.parse_github_url("https://github.com/torvalds/linux")
    assert owner == "torvalds"
    assert repo == "linux"

    owner, repo = GitHubService.parse_github_url("https://github.com/tiangolo/fastapi.git")
    assert owner == "tiangolo"
    assert repo == "fastapi"

    owner, repo = GitHubService.parse_github_url("http://github.com/pallets/flask/")
    assert owner == "pallets"
    assert repo == "flask"

    # Valid SSH variant
    owner, repo = GitHubService.parse_github_url("git@github.com:rust-lang/rust.git")
    assert owner == "rust-lang"
    assert repo == "rust"

    # Invalid formats
    with pytest.raises(Exception):
        GitHubService.parse_github_url("https://gitlab.com/owner/repo")

    with pytest.raises(Exception):
        GitHubService.parse_github_url("not_a_url")

    with pytest.raises(Exception):
        GitHubService.parse_github_url("")


def test_token_encryption():
    secret_token = "ghp_VerySecretAccessToken123456789"
    encrypted = encrypt_secret(secret_token)
    assert encrypted != secret_token
    decrypted = decrypt_secret(encrypted)
    assert decrypted == secret_token


@pytest.mark.asyncio
async def test_github_oauth_endpoints(client: AsyncClient):
    # Register & login
    await client.post(
        "/api/v1/auth/register",
        json={"full_name": "GH User", "email": "ghuser@repomind.ai", "password": "Password123!"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "ghuser@repomind.ai", "password": "Password123!"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Check initial status -> not connected
    status_res = await client.get("/api/v1/auth/github/status", headers=headers)
    assert status_res.status_code == 200
    assert status_res.json()["is_connected"] is False

    # 2. Get connect URL
    connect_res = await client.get("/api/v1/auth/github/connect", headers=headers)
    assert connect_res.status_code == 200
    auth_url = connect_res.json()["authorization_url"]
    assert "github.com/login/oauth/authorize" in auth_url
    assert "scope=repo%2Cread%3Auser" in auth_url or "scope=repo,read:user" in auth_url

    # 3. Disconnect when not connected
    dc_res = await client.delete("/api/v1/auth/github/disconnect", headers=headers)
    assert dc_res.status_code == 200
    assert "No active GitHub connection" in dc_res.json()["message"]

